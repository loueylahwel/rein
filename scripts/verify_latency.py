"""Measure cursor latency: time from a move_rel message to the frame that
shows the result, on an idle desktop (the user's 'laggy when idle' bug).

With wake-on-input this should be well under 250ms (previously up to a full
idle tick + encode, ~400ms+).
"""

import asyncio
import json
import time
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((Path.home() / "AppData/Roaming/PCocket/config.json").read_text())


async def main():
    frames = asyncio.Queue()

    async with websockets.connect(CFG["relay"], max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "pair"}))
        hello = json.loads(await ws.recv())
        assert hello.get("type") == "paired", hello

        async def reader():
            async for raw in ws:
                if isinstance(raw, bytes):
                    await frames.put(time.monotonic())

        rt = asyncio.create_task(reader())
        await ws.send(json.dumps({
            "id": "s1", "cmd": "screen.start",
            "fps": 10, "max_width": 960, "quality": 50, "binary": True}))

        # let the stream go idle (idle rate ~2-3 fps)
        await asyncio.sleep(3)
        while not frames.empty():
            frames.get_nowait()

        latencies = []
        for i in range(5):
            await ws.send(json.dumps(
                {"cmd": "input", "action": "move_rel", "dx": 0.01, "dy": 0}))
            t = time.monotonic()
            frame_at = await asyncio.wait_for(frames.get(), timeout=2)
            latencies.append(frame_at - t)
            await asyncio.sleep(1.2)  # let it go idle-ish again

        await ws.send(json.dumps({"id": "s2", "cmd": "screen.stop"}))
        rt.cancel()

        ms = [round(x * 1000) for x in latencies]
        print(f"cursor->frame latencies: {ms} ms")
        avg = sum(latencies) / len(latencies)
        print(f"average: {avg * 1000:.0f} ms")
        assert avg < 0.25, "still laggy!"
        print("LATENCY OK")


if __name__ == "__main__":
    asyncio.run(main())
