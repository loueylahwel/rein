import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../client_registry.dart';
import '../relay_client.dart';

/// Read-only webcam viewer: starts `camera.start` on open and renders the
/// incoming `src: "camera"` PJF1 frames. No gesture/input handling — the PC
/// camera is view only.
class CameraPage extends StatefulWidget {
  const CameraPage({super.key, required this.client});

  final RelayClient client;

  @override
  State<CameraPage> createState() => _CameraPageState();
}

class _CameraPageState extends State<CameraPage> {
  // The client frames currently flow over. Swapped for the registry's client
  // when HomePage's auto-reconnect replaces it, so the page keeps working
  // instead of staying bound to a dead client.
  late RelayClient _client = widget.client;
  StreamSubscription<RelayClient>? _registrySub;
  StreamSubscription<RelayEvent>? _eventSub;
  StreamSubscription<ScreenFrame>? _frameSub;
  StreamSubscription<bool>? _connSub;
  // The last camera frame received. Never cleared while the page is open:
  // the agent skips unchanged frames, so the UI must keep showing the last
  // frame indefinitely.
  Uint8List? _frame;
  int _frameW = 4;
  int _frameH = 3;
  bool _streaming = false;
  // True from socket loss until the stream is back (first frame after
  // reconnection, or `agent.online`). Drives the reconnecting overlay.
  bool _connectionLost = false;
  // Reentrancy guard for _startStream (agent.online and socket reconnect
  // can both trigger it).
  bool _starting = false;
  // Inline camera failure (from the `camera.error` event or a failed
  // `camera.start` request); null while the camera is working.
  String? _error;

  @override
  void initState() {
    super.initState();
    _bindClient(_client);
    _registrySub = ClientRegistry.instance.onChange.listen(_onRegistryClient);
    // If a reconnect already replaced the client before this page opened,
    // the passed-in one is stale: switch to the registry's live one.
    final current = ClientRegistry.instance.client;
    if (current != null) _onRegistryClient(current);
    _startStream();
  }

  @override
  void dispose() {
    _registrySub?.cancel();
    _eventSub?.cancel();
    _frameSub?.cancel();
    _connSub?.cancel();
    _client.send('camera.stop');
    super.dispose();
  }

  /// Points the event/frame/connection subscriptions at [client].
  void _bindClient(RelayClient client) {
    _eventSub?.cancel();
    _frameSub?.cancel();
    _connSub?.cancel();
    _client = client;
    _eventSub = client.events.listen(_onEvent);
    _frameSub = client.screenFrames.listen(_onFrame);
    _connSub = client.connectionState.listen(_onConnectionState);
  }

  /// Handles a replacement client from the registry (auto-reconnect). The
  /// new client's socket is already up, so the stream is restarted right
  /// away.
  void _onRegistryClient(RelayClient client) {
    if (identical(client, _client)) return;
    _bindClient(client);
    _startStream();
  }

  Future<void> _startStream() async {
    if (_starting) return; // a camera.start is already in flight
    _starting = true;
    try {
      await _client.request(
          'camera.start', {'fps': 10, 'max_width': 640, 'binary': true});
      if (mounted) {
        setState(() {
          _streaming = true;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      _starting = false;
    }
  }

  void _onConnectionState(bool connected) {
    if (!mounted) return;
    if (connected) {
      // Socket is back: restart the stream (idempotent — the agent replaces
      // any old streamer server-side).
      _startStream();
    } else {
      setState(() {
        _connectionLost = true;
        _streaming = false;
      });
    }
  }

  void _onFrame(ScreenFrame frame) {
    if (!mounted) return;
    // The shared frame stream also carries desktop captures; this page only
    // renders webcam frames.
    if (frame.src != 'camera') return;
    setState(() {
      _frame = frame.jpegBytes;
      if (frame.w > 0) _frameW = frame.w;
      if (frame.h > 0) _frameH = frame.h;
      // First frame after a reconnect: the stream is back, hide the overlay.
      _connectionLost = false;
    });
  }

  void _onEvent(RelayEvent event) {
    if (!mounted) return;
    if (event.name == 'agent.online') {
      // Agent (re)connected: hide the overlay and restart the stream.
      setState(() => _connectionLost = false);
      _startStream();
      return;
    }
    if (event.name == 'camera.error') {
      setState(() {
        _streaming = false;
        _error = '${event.data['error'] ?? 'Camera error'}';
      });
    }
  }

  void _retry() {
    setState(() => _error = null);
    _startStream();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('PC Camera')),
      body: Container(
        color: Colors.black,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final aspect = _frameW / _frameH;
            var w = constraints.maxWidth;
            var h = w / aspect;
            if (h > constraints.maxHeight) {
              h = constraints.maxHeight;
              w = h * aspect;
            }
            final imageRect = Rect.fromLTWH(
              (constraints.maxWidth - w) / 2,
              (constraints.maxHeight - h) / 2,
              w,
              h,
            );
            return Stack(
              children: [
                Positioned.fromRect(
                  rect: imageRect,
                  child: _error != null
                      ? _buildError()
                      : _frame != null
                          ? Image.memory(
                              _frame!,
                              gaplessPlayback: true,
                              fit: BoxFit.fill,
                            )
                          : Center(
                              child: Text(
                                _streaming
                                    ? 'Waiting for frames…'
                                    : 'Starting camera…',
                                style: const TextStyle(color: Colors.white54),
                              ),
                            ),
                ),
                if (_connectionLost)
                  Positioned.fill(
                    child: AbsorbPointer(
                      child: Container(
                        color: Colors.black54,
                        child: const Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              CircularProgressIndicator(),
                              SizedBox(height: 12),
                              Text(
                                'Connection lost — reconnecting…',
                                style: TextStyle(color: Colors.white70),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.videocam_off, color: Colors.white54, size: 48),
            const SizedBox(height: 12),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white70),
            ),
            const SizedBox(height: 6),
            const Text(
              'No camera found, the camera is busy, or it is not supported.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white38, fontSize: 12),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _retry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}
