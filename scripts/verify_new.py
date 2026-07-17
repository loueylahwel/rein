"""Verify the new PCocket agent features through the configured relay.

Checks: fs.shortcuts, screen frames (saves one to scripts/frame.jpg so the
cursor overlay can be inspected), and input move_rel (compares local cursor
position before/after).
"""

import asyncio
import base64
import json
from pathlib import Path

import websockets
from pynput.mouse import Controller as MouseController

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "agent" / "config.json").read_text())
mouse = MouseController()


async def main():
    pending = {}
    frames = []
    req_id = 0

    async with websockets.connect(CFG["relay"], max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "pair", "code": CFG["code"]}))
        hello = json.loads(await ws.recv())
        assert hello.get("type") == "paired", hello
        print(f"paired via {CFG['relay']}")

        async def request(cmd, **params):
            nonlocal req_id
            req_id += 1
            rid = f"v{req_id}"
            fut = asyncio.get_event_loop().create_future()
            pending[rid] = fut
            await ws.send(json.dumps({"id": rid, "cmd": cmd, **params}))
            return await asyncio.wait_for(fut, timeout=20)

        async def receiver():
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("id") in pending:
                    pending.pop(msg["id"]).set_result(msg)
                elif msg.get("event") == "screen.frame":
                    frames.append(msg["data"])

        rt = asyncio.create_task(receiver())
        try:
            r = await request("fs.shortcuts")
            names = [s["name"] for s in r["data"]["shortcuts"]]
            print("fs.shortcuts:", names)
            assert "Home" in names and "Drives" in names

            await request("screen.start", fps=2, max_width=960, quality=50)
            await asyncio.sleep(2)
            await request("screen.stop")
            assert frames, "no frames"
            out = ROOT / "scripts" / "frame.jpg"
            out.write_bytes(base64.b64decode(frames[-1]["jpeg"]))
            print(f"saved frame: {out} ({frames[-1]['w']}x{frames[-1]['h']})")

            x0, y0 = mouse.position
            await ws.send(json.dumps(
                {"cmd": "input", "action": "move_rel", "dx": 0.05, "dy": 0.05}))
            await asyncio.sleep(0.5)
            x1, y1 = mouse.position
            print(f"cursor: ({x0},{y0}) -> ({x1},{y1})")
            assert x1 > x0 and y1 > y0, "cursor did not move"
            print("ALL NEW FEATURES OK")
        finally:
            rt.cancel()


if __name__ == "__main__":
    asyncio.run(main())
