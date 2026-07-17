"""Verify the stream wakes on PHYSICAL mouse movement too (cursor_watcher),
not just on phone input. Simulates physical moves via pynput from this
script (indistinguishable from real mouse movement to the agent), after
letting the stream go idle.
"""

import asyncio
import json
import time
from pathlib import Path

import websockets
from pynput.mouse import Controller as MouseController

CFG = json.loads(
    (Path.home() / "AppData/Roaming/PCocket/config.json").read_text())
mouse = MouseController()


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

        await asyncio.sleep(3)  # let the stream go idle
        while not frames.empty():
            frames.get_nowait()

        lat = []
        for _ in range(4):
            x0, y0 = mouse.position
            mouse.position = (x0 + 15, y0)  # "physical" move
            t = time.monotonic()
            frame_at = await asyncio.wait_for(frames.get(), timeout=2)
            lat.append(frame_at - t)
            await asyncio.sleep(1.2)

        await ws.send(json.dumps({"id": "s2", "cmd": "screen.stop"}))
        rt.cancel()

        ms = [round(x * 1000) for x in lat]
        print(f"physical-mouse -> frame latencies: {ms} ms")
        avg = sum(lat) / len(lat)
        print(f"average: {avg * 1000:.0f} ms")
        assert avg < 0.3, "physical mouse wake is too slow"
        print("PHYSICAL WAKE OK")


if __name__ == "__main__":
    asyncio.run(main())
