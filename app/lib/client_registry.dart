import 'dart:async';

import 'relay_client.dart';

/// App-wide holder for the current [RelayClient].
///
/// HomePage replaces the client on every successful (re)connect via [set] and
/// withdraws it on teardown via [clear]. Long-lived consumers (the phone
/// share controller, the PC screen page) subscribe to [onChange] so that,
/// after an automatic reconnect, they rebind to the fresh client instead of
/// staying bound to a dead one.
class ClientRegistry {
  ClientRegistry._();

  static final ClientRegistry instance = ClientRegistry._();

  final StreamController<RelayClient> _ctrl =
      StreamController<RelayClient>.broadcast();
  RelayClient? _client;

  /// The current client, or null while disconnected.
  RelayClient? get client => _client;

  /// Emits each new client as it replaces the previous one. Never emits null:
  /// a teardown simply produces no events until the next successful connect.
  Stream<RelayClient> get onChange => _ctrl.stream;

  /// Publishes [client] as the current one. No-op when it already is.
  void set(RelayClient client) {
    if (identical(_client, client)) return;
    _client = client;
    _ctrl.add(client);
  }

  /// Withdraws [client] when it is the current one (ignored otherwise, so a
  /// stale teardown cannot clear a newer client).
  void clear(RelayClient client) {
    if (identical(_client, client)) _client = null;
  }
}
