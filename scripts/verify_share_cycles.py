"""Stress the phone-share viewer lifecycle: several start/frames/stop cycles
on ONE paired connection. The old cross-thread Tk calls crashed the agent
process on close (Tcl_AsyncDelete) — with the queue-based viewer the process
must survive every cycle.
"""

import asyncio
import io
import json
import sys
from pathlib import Path

import websockets
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
from phone_viewer import make_pjf1  # noqa: E402

CFG = json.loads((Path.home() / "AppData/Roaming/PCocket/config.json").read_text())


def frame(i):
    img = Image.new("RGB", (540, 960), (24, 20, 31))
    ImageDraw.Draw(img).text((40, 450), f"cycle frame {i}", fill="white")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=40)
    return buf.getvalue()


async def main():
    async with websockets.connect(CFG["relay"], max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "pair"}))
        hello = json.loads(await ws.recv())
        assert hello.get("type") == "paired", hello
        print("paired -- one connection for all cycles")

        req = 0

        async def request(cmd, **params):
            nonlocal req
            req += 1
            rid = f"c{req}"
            await ws.send(json.dumps({"id": rid, "cmd": cmd, **params}))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                if isinstance(raw, str):
                    msg = json.loads(raw)
                    if msg.get("id") == rid:
                        assert msg.get("ok"), msg
                        return msg

        for cycle in range(1, 4):
            await request("phone.share.start", name="CycleTest")
            for i in range(6):
                await ws.send(make_pjf1(frame(i), 540, 960))
                await asyncio.sleep(0.1)
            await request("phone.share.stop")
            print(f"cycle {cycle}: start -> 6 frames -> stop OK")
            await asyncio.sleep(0.5)

        r = await request("ping")
        assert r["data"].get("pong")
        print("agent still alive and responsive after 3 cycles — SURVIVED")


if __name__ == "__main__":
    asyncio.run(main())
