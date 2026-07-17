# Rein

Your PC, on a short leash. Control your Windows PC from your Android phone
over your local network — no accounts, no cloud, nothing to configure.

- **Screen streaming** with live cursor — drag to move, tap to click
- **PC webcam view** on your phone
- **Files** — browse, download to your phone, upload to your PC
- **Media & volume** control, **clipboard** sync
- **Power**: lock / sleep / restart / shutdown (with confirmations)
- **Shell** commands and process list/kill

## Setup (2 minutes)

**On your PC (Windows 10/11):**

1. Download **`Rein-Service.exe`** from the
   [latest release](https://github.com/loueylahwel/rein/releases/latest)
2. Run it once. That's it — it's invisible, adds itself to startup, and
   starts at every boot. (Windows may ask to allow it through the firewall —
   say yes, it's how your phone finds the PC.)

**On your phone (Android 10+):**

1. Download **`rein.apk`** from the same release and install it
   (allow "install unknown apps" when Android asks)
2. Make sure phone and PC are on the **same Wi-Fi**
3. Open Rein → **Find my PC** → your PC's name pops up → tap it
4. Connected. From now on the app reconnects by itself every time.

the PC broadcasts a tiny "I'm here" beacon that the
app listens for. If the PC's IP changes, the app re-finds it by name.

> **Security note:** tap-to-connect with no code means *anyone on your
> Wi-Fi with the app can connect to your PC*. That's the deliberate
> trade-off for zero-friction pairing on a trusted home network. The PC
> agent also exposes full file and shell access by design — run it only on
> machines you own.

## Optional: Rein-Agent.exe (GUI)

Also in the release: `Rein-Agent.exe` shows a little window with live
status and a QR for manual pairing (handy if you ever want the code flow or
to run the agent on demand instead of at boot). You don't need it for the
normal setup above.

## How it works

```
 Rein-Service.exe (PC)                Rein app (phone)
 ┌─────────────────────┐   ws :8080   ┌────────────────┐
 │ relay (embedded)     │ ◀────────── │ Find my PC      │
 │ screen/camera stream │ ──────────▶ │ (UDP discovery) │
 │ input, files, shell  │   frames    │                 │
 └─────────────────────┘              └────────────────┘
```

The phone and PC talk directly over WebSocket on port 8080 — nothing leaves
your network. PC discovery uses a UDP beacon on port 47809.

## Building from source

| part | stack | build |
|---|---|---|
| `agent/` | Python 3.11+ | `pip install -r requirements.txt`, then PyInstaller (see `agent/README` commands in repo history) |
| `relay/` | Node.js 18+ | only needed for internet/remote mode — `npm install && npm start` |
| `app/` | Flutter 3.3+ | `flutter pub get && flutter build apk --release` |

Repo layout: `agent/` (PC service + GUI, Python), `app/` (Flutter phone
app), `relay/` (optional standalone Node relay for remote access),
`docs/protocol.md` (wire protocol), `scripts/` (verification utilities).

## Roadmap

- PC notification mirroring
- Remote (internet) access mode via the standalone relay
