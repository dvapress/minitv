import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

const String apiBase = String.fromEnvironment('API_BASE', defaultValue: 'http://127.0.0.1:18110');

const _gateCookieName = 'leapdrama_v2_gate';
const _csrfCookieName = 'leapdrama_v2_csrf';
const _gatePrefKey = 'leapdrama_v2_gate_cookie';
String? _gateCookie;

String? get gateCookie => _gateCookie;

Future<void> initGateCookie() async {
  final prefs = await SharedPreferences.getInstance();
  final saved = prefs.getString(_gatePrefKey);
  if (saved != null && saved.isNotEmpty) {
    _gateCookie = saved;
  }
}

Future<void> setGateCookie(String? value) async {
  final clean = value?.trim();
  _gateCookie = (clean == null || clean.isEmpty) ? null : clean;
  try {
    final prefs = await SharedPreferences.getInstance();
    if (_gateCookie == null) {
      await prefs.remove(_gatePrefKey);
    } else {
      await prefs.setString(_gatePrefKey, _gateCookie!);
    }
  } catch (_) {
    // Keep in-memory cookie even if persistent storage fails.
  }
}

/// Resolves server-relative paths (e.g. `/covers/1.jpg`) against [apiBase].
String resolveApiUrl(String? url) {
  if (url == null || url.isEmpty) return '';
  if (url.startsWith('/')) {
    final base = apiBase.replaceFirst(RegExp(r'/+$'), '');
    return '$base$url';
  }
  return url;
}

bool isSameApiOrigin(String url) {
  final target = Uri.tryParse(url);
  final base = Uri.tryParse(apiBase);
  if (target == null || base == null) return false;
  if (!target.hasScheme || !base.hasScheme) return false;
  return target.scheme == base.scheme && target.host == base.host && target.port == base.port;
}

/// Attaches the staging gate cookie only when [url] targets the same origin as [apiBase].
Map<String, String> apiCookieHeaders(String url, {Map<String, String>? base}) {
  final headers = <String, String>{...?base};
  final cookie = _gateCookie;
  if (cookie != null && cookie.isNotEmpty && isSameApiOrigin(url)) {
    headers[HttpHeaders.cookieHeader] = '$_gateCookieName=$cookie';
  }
  return headers;
}

/// Authenticates against the staging gateway (`/__gate` + `/__gate/login`) and
/// persists the resulting signed gate cookie for subsequent API/media requests.
Future<void> unlockGate(String passcode) async {
  final base = apiBase.replaceFirst(RegExp(r'/+$'), '');
  final baseUri = Uri.parse(base);
  final origin = '${baseUri.scheme}://${baseUri.host}${baseUri.hasPort ? ':${baseUri.port}' : ''}';
  final client = HttpClient();
  try {
    final getReq = await client.getUrl(Uri.parse('$base/__gate'));
    getReq.followRedirects = false;
    final getResp = await getReq.close();
    await getResp.drain<void>();

    // If the server already accepted the session, store the cookie if rotated.
    for (final c in getResp.cookies) {
      if (c.name == _gateCookieName && c.value.isNotEmpty) {
        await setGateCookie(c.value);
        return;
      }
    }

    String? csrf;
    for (final c in getResp.cookies) {
      if (c.name == _csrfCookieName && c.value.isNotEmpty) {
        csrf = c.value;
        break;
      }
    }
    if (csrf == null || csrf.isEmpty) {
      throw ApiException(getResp.statusCode, 'gate_csrf_missing');
    }

    final postReq = await client.postUrl(Uri.parse('$base/__gate/login'));
    postReq.followRedirects = false;
    postReq.headers.set(HttpHeaders.contentTypeHeader, 'application/x-www-form-urlencoded');
    postReq.headers.set('Origin', origin);
    postReq.headers.set('Referer', '$base/__gate');
    postReq.headers.set(HttpHeaders.cookieHeader, '$_csrfCookieName=$csrf');
    final formBody = 'csrf=${Uri.encodeQueryComponent(csrf)}'
        '&passcode=${Uri.encodeQueryComponent(passcode.trim())}'
        '&next=%2F';
    postReq.add(utf8.encode(formBody));

    final postResp = await postReq.close();
    await postResp.drain<void>();

    for (final c in postResp.cookies) {
      if (c.name == _gateCookieName && c.value.isNotEmpty) {
        await setGateCookie(c.value);
        return;
      }
    }
    if (postResp.statusCode == 401) {
      throw ApiException(401, 'invalid_passcode');
    }
    if (postResp.statusCode == 429) {
      throw ApiException(429, 'rate_limited');
    }
    throw ApiException(postResp.statusCode, 'gate_failed');
  } on ApiException {
    rethrow;
  } catch (error) {
    debugPrint('[gate] unlock failed: $error');
    throw ApiException(0, 'network: $error');
  } finally {
    client.close();
  }
}

/// Identifies the install for guest sessions so feed de-duplication still
/// works before the viewer signs in. Persisted on first launch — call
/// [initDeviceId] before runApp.
const _deviceKey = 'leapdrama_app_device';
String? _deviceId;

Future<void> initDeviceId() async {
  final prefs = await SharedPreferences.getInstance();
  final saved = prefs.getString(_deviceKey);
  if (saved != null && saved.isNotEmpty) {
    _deviceId = saved;
    return;
  }
  _deviceId = 'app-${DateTime.now().microsecondsSinceEpoch.toRadixString(36)}';
  await prefs.setString(_deviceKey, _deviceId!);
}

String get deviceId => _deviceId ??= 'app-${DateTime.now().microsecondsSinceEpoch.toRadixString(36)}';

class ApiException implements Exception {
  ApiException(this.status, this.message, [this.data]);

  /// HTTP status; 0 means the request never reached the server.
  final int status;
  final String message;

  /// Parsed error body — e.g. the {need, have} map behind a 402.
  final Object? data;

  @override
  String toString() => message;
}

class MiniApi {
  MiniApi({this.token});
  String? token;

  /// The session layer hooks this so a dead token flips the app back to guest.
  static void Function()? onUnauthorized;

  /// Triggered when the reverse-proxy access gate rejects an unauthenticated request.
  static void Function()? onGateRequired;

  Future<Map<String, dynamic>> getJson(String path) => _send('GET', path, null, null);

  Future<Map<String, dynamic>> postJson(String path, Map<String, dynamic> body, {Map<String, String>? headers}) =>
      _send('POST', path, body, headers);

  Future<Map<String, dynamic>> patchJson(String path, Map<String, dynamic> body) => _send('PATCH', path, body, null);

  Future<Map<String, dynamic>> _send(String method, String path, Map<String, dynamic>? body, Map<String, String>? headers) async {
    final client = HttpClient();
    try {
      final request = await client.openUrl(method, Uri.parse('$apiBase$path'));
      request.headers.set(HttpHeaders.contentTypeHeader, 'application/json');
      request.headers.set('X-Device-Id', deviceId);
      final gate = _gateCookie;
      if (gate != null && gate.isNotEmpty) {
        request.headers.set(HttpHeaders.cookieHeader, '$_gateCookieName=$gate');
      }
      if (token != null) request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      headers?.forEach(request.headers.set);
      if (body != null) request.add(utf8.encode(jsonEncode(body)));
      final response = await request.close();
      final text = await response.transform(utf8.decoder).join();
      Object? payload;
      try {
        payload = jsonDecode(text);
      } catch (_) {
        /* not JSON */
      }
      if (response.statusCode >= 400) {
        String detail = 'HTTP ${response.statusCode}';
        if (payload is Map && payload['detail'] is String) detail = payload['detail'] as String;
        if (response.statusCode == 401 && detail == 'Gate authentication required') {
          unawaited(setGateCookie(null));
          onGateRequired?.call();
          throw ApiException(response.statusCode, detail, payload);
        }
        // A dead session flips the app to guest; a wrong code (401 on /v1/auth/) must not.
        if (response.statusCode == 401 && !path.startsWith('/v1/auth/')) onUnauthorized?.call();
        throw ApiException(response.statusCode, detail, payload);
      }
      if (payload is Map<String, dynamic>) return payload;
      return {'data': payload};
    } on ApiException {
      rethrow;
    } catch (error) {
      // Status 0 means the request never reached the server. Keep the reason in
      // the log — `err_network` alone hides DNS/TLS/VPN split-tunnel failures.
      debugPrint('[api] $method $path failed: $error');
      throw ApiException(0, 'network: $error');
    } finally {
      client.close();
    }
  }
}
