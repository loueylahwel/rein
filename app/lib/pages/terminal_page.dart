import 'dart:async';

import 'package:flutter/material.dart';

import '../relay_client.dart';
import '../util.dart';

class _TermEntry {
  _TermEntry(this.cmd);

  final String cmd;
  String? stdout;
  String? stderr;
  int? code;
  bool running = true;
}

class TerminalPage extends StatefulWidget {
  const TerminalPage({super.key, required this.client});

  final RelayClient client;

  @override
  State<TerminalPage> createState() => _TerminalPageState();
}

class _TerminalPageState extends State<TerminalPage> {
  final _cmdCtrl = TextEditingController();
  final _cwdCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final List<_TermEntry> _history = [];
  bool _busy = false;

  @override
  void dispose() {
    _cmdCtrl.dispose();
    _cwdCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _run() async {
    final cmd = _cmdCtrl.text.trim();
    if (cmd.isEmpty || _busy) return;
    _cmdCtrl.clear();
    final entry = _TermEntry(cmd);
    setState(() {
      _history.add(entry);
      _busy = true;
    });
    _scrollToEnd();
    try {
      final data = await widget.client.request('sys.exec', {
        'command': cmd,
        'cwd': _cwdCtrl.text.trim(),
        'timeout': 60,
      });
      entry.stdout = data['stdout'] as String? ?? '';
      entry.stderr = data['stderr'] as String? ?? '';
      entry.code = (data['code'] as num?)?.toInt();
    } catch (e) {
      entry.stderr = '$e';
      entry.code = -1;
    } finally {
      entry.running = false;
      if (mounted) {
        setState(() => _busy = false);
        _scrollToEnd();
      }
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.jumpTo(_scrollCtrl.position.maxScrollExtent);
      }
    });
  }

  void _showProcesses() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.7,
        builder: (ctx, scrollCtrl) =>
            ProcessesSheet(client: widget.client, scrollController: scrollCtrl),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Terminal'),
        actions: [
          IconButton(
            tooltip: 'Processes',
            icon: const Icon(Icons.memory),
            onPressed: _showProcesses,
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: _history.isEmpty
                ? const Center(child: Text('Run a command to get started'))
                : ListView.builder(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.all(12),
                    itemCount: _history.length,
                    itemBuilder: (context, i) {
                      final e = _history[i];
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('> ${e.cmd}',
                                style: TextStyle(
                                  fontFamily: 'monospace',
                                  color: theme.colorScheme.primary,
                                  fontWeight: FontWeight.bold,
                                )),
                            if (e.running)
                              const Padding(
                                padding: EdgeInsets.symmetric(vertical: 4),
                                child: SizedBox(
                                  width: 16,
                                  height: 16,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2),
                                ),
                              )
                            else ...[
                              if (e.stdout != null && e.stdout!.isNotEmpty)
                                SelectableText(e.stdout!.trimRight(),
                                    style: const TextStyle(
                                        fontFamily: 'monospace')),
                              if (e.stderr != null && e.stderr!.isNotEmpty)
                                SelectableText(
                                  e.stderr!.trimRight(),
                                  style: TextStyle(
                                    fontFamily: 'monospace',
                                    color: theme.colorScheme.error,
                                  ),
                                ),
                              Text('exit code: ${e.code ?? '?'}',
                                  style: theme.textTheme.bodySmall),
                            ],
                          ],
                        ),
                      );
                    },
                  ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: TextField(
              controller: _cwdCtrl,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
              decoration: const InputDecoration(
                isDense: true,
                labelText: 'Working directory (optional)',
                hintText: r'C:\Users\you',
                border: OutlineInputBorder(),
              ),
            ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _cmdCtrl,
                      style: const TextStyle(fontFamily: 'monospace'),
                      decoration: const InputDecoration(
                        hintText: 'Command',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onSubmitted: (_) => unawaited(_run()),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    onPressed: _busy ? null : () => unawaited(_run()),
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ProcessesSheet extends StatefulWidget {
  const ProcessesSheet({
    super.key,
    required this.client,
    required this.scrollController,
  });

  final RelayClient client;
  final ScrollController scrollController;

  @override
  State<ProcessesSheet> createState() => _ProcessesSheetState();
}

class _ProcessesSheetState extends State<ProcessesSheet> {
  List<Map<String, dynamic>>? _processes;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    try {
      final data = await widget.client.request('sys.ps');
      final list = (data['processes'] as List? ?? [])
          .map((e) => (e as Map).cast<String, dynamic>())
          .toList();
      if (!mounted) return;
      setState(() {
        _processes = list;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    }
  }

  Future<void> _kill(Map<String, dynamic> proc) async {
    final pid = (proc['pid'] as num?)?.toInt();
    if (pid == null) return;
    final name = '${proc['name'] ?? '?'}';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Kill $name?'),
        content: Text('Terminate process $name (pid $pid)?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Kill'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await widget.client.request('sys.kill', {'pid': pid});
      if (mounted) {
        showMessage(context, 'Killed $name');
        unawaited(_load());
      }
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final procs = _processes;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Text('Processes', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              IconButton(
                tooltip: 'Refresh',
                icon: const Icon(Icons.refresh),
                onPressed: () => unawaited(_load()),
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: _error != null
              ? Center(child: Text(_error!))
              : procs == null
                  ? const Center(child: CircularProgressIndicator())
                  : ListView.builder(
                      controller: widget.scrollController,
                      itemCount: procs.length,
                      itemBuilder: (context, i) {
                        final p = procs[i];
                        return ListTile(
                          dense: true,
                          title: Text('${p['name'] ?? '?'}',
                              overflow: TextOverflow.ellipsis),
                          subtitle: Text(
                              'pid ${p['pid']} · ${formatBytes((p['mem'] as num?) ?? 0)}'),
                          trailing: IconButton(
                            icon: const Icon(Icons.close),
                            tooltip: 'Kill',
                            onPressed: () => unawaited(_kill(p)),
                          ),
                        );
                      },
                    ),
        ),
      ],
    );
  }
}
