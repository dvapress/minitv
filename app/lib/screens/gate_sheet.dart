import 'package:flutter/material.dart';

import '../api.dart';
import '../session.dart';
import '../ui.dart';

/// Full-screen overlay prompting for the staging demo gateway passcode when the
/// server responds with `401 Gate authentication required`.
class GateSheet extends StatefulWidget {
  const GateSheet({super.key, required this.session, required this.language});
  final Session session;
  final String language;

  @override
  State<GateSheet> createState() => _GateSheetState();
}

class _GateSheetState extends State<GateSheet> {
  final controller = TextEditingController();
  bool submitting = false;
  String? error;

  bool get zh => widget.language == 'zh';

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final code = controller.text.trim();
    if (code.isEmpty || submitting) return;
    setState(() {
      submitting = true;
      error = null;
    });
    try {
      await unlockGate(code);
      if (!mounted) return;
      widget.session.completeGateUnlock();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        submitting = false;
        if (e.message == 'invalid_passcode') {
          error = zh ? '口令错误，请重试。' : 'Incorrect passcode. Please try again.';
        } else if (e.message == 'rate_limited') {
          error = zh ? '尝试次数过多，请稍后再试。' : 'Too many attempts. Try again later.';
        } else {
          error = zh ? '连接失败，请检查网络后重试。' : 'Connection failed. Check network and retry.';
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        submitting = false;
        error = zh ? '连接失败，请重试。' : 'Connection failed. Please try again.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: const Color(0xE60C0A0B),
      child: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 360),
              child: Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: sheet,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.white12),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      zh ? 'LeapDrama 访问验证' : 'LeapDrama Access Gate',
                      style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      zh ? '请输入演示环境访问口令以加载内容。' : 'Enter the demo access passcode to load content.',
                      style: const TextStyle(color: Colors.white60, fontSize: 13, height: 1.4),
                    ),
                    const SizedBox(height: 20),
                    TextField(
                      controller: controller,
                      obscureText: true,
                      autofocus: true,
                      enabled: !submitting,
                      style: const TextStyle(color: Colors.white, fontSize: 16),
                      textInputAction: TextInputAction.done,
                      onSubmitted: (_) => _submit(),
                      decoration: InputDecoration(
                        hintText: zh ? '输入访问口令' : 'Enter passcode',
                        hintStyle: const TextStyle(color: Colors.white38),
                        filled: true,
                        fillColor: bg,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: const BorderSide(color: Colors.white24),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: const BorderSide(color: Colors.white24),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: const BorderSide(color: red),
                        ),
                      ),
                    ),
                    if (error != null) ...[
                      const SizedBox(height: 10),
                      Text(error!, style: const TextStyle(color: Color(0xFFFF7B93), fontSize: 13)),
                    ],
                    const SizedBox(height: 16),
                    SizedBox(
                      height: 46,
                      child: ElevatedButton(
                        onPressed: submitting ? null : _submit,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: red,
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: red.withValues(alpha: 0.5),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        child: submitting
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : Text(
                                zh ? '进入' : 'Continue',
                                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                              ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
