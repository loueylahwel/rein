"""Verify binary screen streaming end-to-end through the relay.

Pairs as a client, starts streaming with binary:true, expects PJF1 binary
packets, and saves the first JPEG to scripts/frame_binary.jpg.
"""

import asyncio
import json
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "agent" / "config.json").read_text())
if not (ROOT / "agent" / "config.json").exists():
    CFG = json.loads(
        (Path.home() / "AppData/Roaming/PCocket/config.json").read_text())


async def main():
    async with websockets.connect(CFG["relay"], max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "pair", "code": CFG["code"]}))
        hello = json.loads(await ws.recv())
        assert hello.get("type") == "paired", hello
        print("paired")

        await ws.send(json.dumps({
            "id": "s1", "cmd": "screen.start",
            "fps": 5, "max_width": 640, "quality": 40, "binary": True}))

        frames = 0
        async def reader():
            nonlocal frames
            async for raw in ws:
                if isinstance(raw, bytes):
                    assert raw[:4] == b"PJF1", raw[:8]
                    hlen = int.from_bytes(raw[4:8], "little")
                    header = json.loads(raw[8:8 + hlen])
                    jpeg = raw[8 + hlen:]
                    frames += 1
                    if frames == 1:
                        (ROOT / "scripts" / "frame_binary.jpg").write_bytes(jpeg)
                        print(f"first PJF1 frame: {header}, {len(jpeg)} bytes")
                else:
                    msg = json.loads(raw)
                    if msg.get("id") == "s1":
                        print("screen.start ->", msg)

        rt = asyncio.create_task(reader())
        await asyncio.sleep(3)
        await ws.send(json.dumps({"id": "s2", "cmd": "screen.stop"}))
        await asyncio.sleep(0.5)
        rt.cancel()
        print(f"received {frames} binary frames")
        assert frames >= 1, "no binary frames received"
        print("BINARY STREAMING OK")


if __name__ == "__main__":
    asyncio.run(main())
