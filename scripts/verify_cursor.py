"""Verify that cursor-only movement triggers screen frames.

Starts a binary stream on an otherwise idle desktop, sends small move_rel
deltas, and counts frames. Before the fix, cursor-only movement changed
nothing in the coarse thumb, so frames were skipped (cursor looked frozen).
Now the quantized cursor position is part of the change key, so every
~4px of movement yields a frame.
"""

import asyncio
import json
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "agent" / "config.json").read_text())


async def main():
    frames = 0

    async with websockets.connect(CFG["relay"], max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "pair", "code": CFG["code"]}))
        hello = json.loads(await ws.recv())
        assert hello.get("type") == "paired", hello

        async def reader():
            nonlocal frames
            async for raw in ws:
                if isinstance(raw, bytes):
                    frames += 1

        rt = asyncio.create_task(reader())
        await ws.send(json.dumps({
            "id": "s1", "cmd": "screen.start",
            "fps": 10, "max_width": 640, "quality": 40, "binary": True}))
        await asyncio.sleep(1)
        baseline = frames

        # small cursor wiggle — this is what used to produce ZERO frames
        for i in range(10):
            dx = 0.004 if i % 2 == 0 else -0.004
            await ws.send(json.dumps(
                {"cmd": "input", "action": "move_rel", "dx": dx, "dy": 0}))
            await asyncio.sleep(0.12)
        await asyncio.sleep(0.5)
        moved = frames - baseline

        await ws.send(json.dumps({"id": "s2", "cmd": "screen.stop"}))
        await asyncio.sleep(0.3)
        rt.cancel()

        print(f"baseline frames (1s idle): {baseline}")
        print(f"frames during cursor wiggle: {moved}")
        assert moved >= 5, "cursor movement did not trigger frames!"
        print("CURSOR VISIBILITY OK")


if __name__ == "__main__":
    asyncio.run(main())
