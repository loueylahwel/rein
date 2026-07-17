// pc-remote relay server
//
// Bridges PC agents and mobile clients over a single public WebSocket endpoint.
// Both sides connect OUTBOUND to this relay, so neither needs port forwarding.
//
// Rooms are keyed by the agent's pairing code:
//   agent  -> { type: "register", code, deviceId, name }
//   client -> { type: "pair", code }
// After pairing, the relay tags client messages with `from` (a client id) and
// forwards them to the agent; the agent replies with `to: <clientId>` and the
// relay routes the response back. Agent messages without `to` are broadcast
// to all paired clients (events: clipboard.changed, agent stats, ...).

const http = require('http');
const crypto = require('crypto');
const { WebSocketServer, WebSocket } = require('ws');

const PORT = process.env.PORT || 8080;

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'content-type': 'text/plain' });
  res.end('pc-remote relay ok\n');
});

const wss = new WebSocketServer({ server });

// code -> { agent: WebSocket|null, deviceId, name, clients: Map<clientId, WebSocket> }
const devices = new Map();

function send(ws, obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    // Buffers go out as raw binary frames; everything else is JSON.
    ws.send(Buffer.isBuffer(obj) ? obj : JSON.stringify(obj));
  }
}

function broadcastClients(dev, obj, exceptId) {
  for (const [id, client] of dev.clients) {
    if (id !== exceptId) send(client, obj);
  }
}

wss.on('connection', (ws) => {
  ws.id = crypto.randomUUID();
  ws.role = null; // 'agent' | 'client'
  ws.code = null;
  ws.isAlive = true;
  ws.on('pong', () => { ws.isAlive = true; });

  ws.on('message', (data, isBinary) => {
    // Binary frames carry screen video packets (PJF1). They can't hold JSON
    // routing fields: agent->client packets are broadcast to the room's
    // clients; client->agent packets (phone screen share) go to the agent.
    if (isBinary) {
      const dev = devices.get(ws.code);
      if (!dev) return;
      if (ws.role === 'agent') {
        broadcastClients(dev, data);
      } else if (ws.role === 'client' && dev.agent &&
                 dev.agent.readyState === WebSocket.OPEN) {
        dev.agent.send(data);
      }
      return;
    }

    let msg;
    try { msg = JSON.parse(data); } catch { return; }
    if (typeof msg !== 'object' || msg === null) return;

    // ---- handshake (first message decides the role) ----
    if (!ws.role) {
      if (msg.type === 'register') {
        const code = String(msg.code || '').toUpperCase().trim();
        if (!code) return send(ws, { type: 'error', error: 'missing code' });
        let dev = devices.get(code);
        if (!dev) { dev = { agent: null, clients: new Map() }; devices.set(code, dev); }
        // Newer agent connection for the same code wins.
        if (dev.agent && dev.agent !== ws) {
          try { dev.agent.close(); } catch {}
          broadcastClients(dev, { type: 'agent.offline' });
        }
        dev.agent = ws;
        dev.deviceId = msg.deviceId || null;
        dev.name = String(msg.name || 'PC');
        ws.role = 'agent';
        ws.code = code;
        send(ws, { type: 'registered', code });
        broadcastClients(dev, { type: 'agent.online', name: dev.name, deviceId: dev.deviceId });
        console.log(`[agent] registered code=${code} name=${dev.name}`);
      } else if (msg.type === 'pair') {
        let code = String(msg.code || '').toUpperCase().trim();
        if (!code) {
          // Codeless pair: only unambiguous when exactly one agent is online.
          const online = [...devices.entries()].filter(
            ([, d]) => d.agent && d.agent.readyState === WebSocket.OPEN);
          if (online.length === 1) {
            code = online[0][0];
          } else if (online.length === 0) {
            return send(ws, { type: 'error', error: 'no device online' });
          } else {
            return send(ws, {
              type: 'choose',
              devices: online.map(([c, d]) => ({ code: c, name: d.name })),
            });
          }
        }
        const dev = devices.get(code);
        if (!dev || !dev.agent || dev.agent.readyState !== WebSocket.OPEN) {
          return send(ws, { type: 'error', error: 'no online device for that code' });
        }
        ws.role = 'client';
        ws.code = code;
        dev.clients.set(ws.id, ws);
        send(ws, { type: 'paired', deviceId: dev.deviceId, name: dev.name, clientId: ws.id });
        console.log(`[client] paired code=${code} client=${ws.id.slice(0, 8)}`);
      } else {
        send(ws, { type: 'error', error: 'first message must be register or pair' });
      }
      return;
    }

    // ---- routing ----
    const dev = devices.get(ws.code);
    if (!dev) return;

    if (ws.role === 'client') {
      if (dev.agent && dev.agent.readyState === WebSocket.OPEN) {
        msg.from = ws.id;
        dev.agent.send(JSON.stringify(msg));
      } else {
        send(ws, { type: 'agent.offline' });
      }
    } else {
      // agent -> client(s). `to` selects one client; absent `to` broadcasts.
      const to = msg.to;
      delete msg.to;
      if (to) {
        const client = dev.clients.get(to);
        if (client) send(client, msg);
      } else {
        broadcastClients(dev, msg);
      }
    }
  });

  ws.on('close', () => {
    if (ws.role === 'agent') {
      const dev = devices.get(ws.code);
      if (dev && dev.agent === ws) {
        dev.agent = null;
        broadcastClients(dev, { type: 'agent.offline' });
        console.log(`[agent] offline code=${ws.code}`);
      }
    } else if (ws.role === 'client') {
      const dev = devices.get(ws.code);
      if (dev) {
        dev.clients.delete(ws.id);
        // Let the agent release per-client resources (streams, viewers).
        if (dev.agent && dev.agent.readyState === WebSocket.OPEN) {
          send(dev.agent, { type: 'client.gone', clientId: ws.id });
        }
      }
    }
  });

  ws.on('error', () => {});
});

// Drop dead connections (agents behind NATs need this to notice disconnects).
const heartbeat = setInterval(() => {
  for (const ws of wss.clients) {
    if (!ws.isAlive) { ws.terminate(); continue; }
    ws.isAlive = false;
    try { ws.ping(); } catch {}
  }
}, 30000);

wss.on('close', () => clearInterval(heartbeat));

server.listen(PORT, () => console.log(`pc-remote relay listening on :${PORT}`));
