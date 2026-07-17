"""Local end-to-end smoke test for pc-remote.

Prereqs: relay running on :8080 and agent running (same venv as agent).
Only exercises SAFE commands: ping, sys.info, fs.list, clipboard.get,
screen.start/stop. Never touches power/input/media.

Usage: python scripts/smoke_test.py
"""

import asyncio
import json
import sys
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "agent" / "config.json").read_text())
RELAY = CFG["relay"]
CODE = CFG["code"]

passed, failed = 0, 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name} {extra}")
    else:
        failed += 1
        print(f"  FAIL  {name} {extra}")


async def main():
    req_id = 0
    pending = {}
    frames = []

    async with websockets.connect(RELAY, max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "pair", "code": CODE}))
        hello = json.loads(await ws.recv())
        check("pair", hello.get("type") == "paired", f"({hello.get('name')})")
        if hello.get("type") != "paired":
            return

        async def request(cmd, **params):
            nonlocal req_id
            req_id += 1
            rid = f"t{req_id}"
            fut = asyncio.get_event_loop().create_future()
            pending[rid] = fut
            await ws.send(json.dumps({"id": rid, "cmd": cmd, **params}))
            return await asyncio.wait_for(fut, timeout=15)

        async def receiver():
            async for raw in ws:
                msg = json.loads(raw)
                rid = msg.get("id")
                if rid and rid in pending:
                    pending.pop(rid).set_result(msg)
                elif msg.get("event") == "screen.frame":
                    frames.append(msg["data"])

        rt = asyncio.create_task(receiver())
        try:
            r = await request("ping")
            check("ping", r.get("ok") and r["data"].get("pong"))

            r = await request("sys.info")
            d = r.get("data", {})
            check("sys.info", r.get("ok") and "screen" in d,
                  f"({d.get('platform')}, {d.get('screen')})")

            r = await request("fs.list", path=str(ROOT))
            entries = r.get("data", {}).get("entries", [])
            check("fs.list", r.get("ok") and len(entries) > 0,
                  f"({len(entries)} entries)")

            r = await request("fs.list", path="")
            check("fs.list drives", r.get("ok"),
                  f"({len(r.get('data', {}).get('entries', []))} drives)")

            r = await request("clipboard.get")
            check("clipboard.get", r.get("ok") and "text" in r.get("data", {}))

            r = await request("screen.start", fps=5, max_width=640, quality=40)
            check("screen.start", r.get("ok") and r["data"].get("streaming"))
            await asyncio.sleep(2.5)
            check("screen frames", len(frames) >= 5,
                  f"({len(frames)} frames, {frames[0]['w']}x{frames[0]['h']})"
                  if frames else "(none)")
            r = await request("screen.stop")
            check("screen.stop", r.get("ok"))

            r = await request("notify.subscribe")
            check("notify unsupported (expected)", r.get("ok") is False)
        finally:
            rt.cancel()

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
