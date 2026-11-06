// OmniFix Cloudflare Worker.
//
// Two modes:
// 1. Guard mode (default): if OMNIFIX_ORIGIN is not configured, serve a static
//    notice so a misconnected Workers Builds integration does not fail.
// 2. Reverse-proxy mode: if OMNIFIX_ORIGIN is configured, forward requests to an
//    already-running OmniFix deployment (Docker + Nginx, usually behind a
//    Cloudflare Tunnel). The Worker is NOT the Python backend; it only proxies.
//
// Required variable for proxy mode:
//   OMNIFIX_ORIGIN = "https://scanner.example.com"   (no path, HTTPS)
//
// Optional variables if the origin is protected by Cloudflare Access:
//   CF_ACCESS_CLIENT_ID
//   CF_ACCESS_CLIENT_SECRET
//
// IMPORTANT: if you use Access service-token headers here, also protect the
// Worker itself with Cloudflare Access. Otherwise anyone who can reach the
// Worker can reach the origin through the service token.

const HOP_BY_HOP_HEADERS = [
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'proxy-connection',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
];

function jsonResponse(status, code, message) {
  return new Response(JSON.stringify({ error: { code, message } }), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
    },
  });
}

function parseOrigin(raw) {
  if (!raw || typeof raw !== 'string') return null;
  let parsed;
  try {
    parsed = new URL(raw.trim());
  } catch {
    return null;
  }
  const isLocalHttp =
    parsed.protocol === 'http:' &&
    ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname);
  if (parsed.protocol !== 'https:' && !isLocalHttp) return null;
  if (parsed.username || parsed.password) return null;
  if (parsed.pathname !== '/' && parsed.pathname !== '') return null;
  if (parsed.search || parsed.hash) return null;
  parsed.pathname = '';
  return parsed;
}

function rewriteSetCookie(cookie) {
  // Let the browser scope cookies to the Worker hostname, not the origin host.
  return cookie.replace(/;\s*Domain=[^;]*/i, '');
}

async function serveNotice(request, env) {
  const url = new URL(request.url);
  if (url.pathname.startsWith('/api/')) {
    return jsonResponse(
      501,
      'not_deployed_here',
      'The OmniFix API is not deployed on Cloudflare Workers. Set OMNIFIX_ORIGIN to proxy an existing OmniFix deployment, or run the full app with Docker and Cloudflare Tunnel.',
    );
  }
  return env.ASSETS.fetch(request);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = parseOrigin(env.OMNIFIX_ORIGIN);

    if (!origin) {
      return serveNotice(request, env);
    }

    const workerOrigin = url.origin;
    const originOrigin = origin.origin;
    const method = request.method.toUpperCase();
    const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(method);

    // Basic cross-site request guard at the proxy edge. The backend still
    // enforces CSRF/session checks; this prevents the proxy from silently
    // accepting foreign browser origins and rewriting them as same-origin.
    if (unsafe) {
      const requestOrigin = request.headers.get('Origin');
      const referer = request.headers.get('Referer');
      if (requestOrigin && requestOrigin !== workerOrigin) {
        return jsonResponse(403, 'origin_rejected', 'Cross-origin request rejected.');
      }
      if (!requestOrigin && referer && !referer.startsWith(workerOrigin + '/')) {
        return jsonResponse(403, 'origin_rejected', 'Cross-origin request rejected.');
      }
    }

    // Build the target by assigning path/search on the fixed origin. Do not
    // resolve a potentially scheme-relative path (//evil.example) against the
    // origin, which could change the target host.
    const target = new URL(originOrigin);
    target.pathname = url.pathname;
    target.search = url.search;
    const headers = new Headers(request.headers);
    for (const name of HOP_BY_HOP_HEADERS) headers.delete(name);
    headers.delete('host');
    headers.set('x-forwarded-host', url.host);
    headers.set('x-forwarded-proto', url.protocol.replace(':', ''));
    // Ask the origin for uncompressed bytes so the proxy can forward the body
    // without rewriting Content-Encoding/Content-Length incorrectly.
    headers.set('accept-encoding', 'identity');

    if (unsafe) {
      // The backend requires a same-origin Origin header for unsafe API calls.
      // From the browser's perspective the Worker is the same origin; rewrite
      // the header to the upstream origin after the edge guard above.
      headers.set('origin', originOrigin);
      if (headers.has('referer')) {
        headers.set('referer', originOrigin + url.pathname + url.search);
      }
    }

    if (env.CF_ACCESS_CLIENT_ID && env.CF_ACCESS_CLIENT_SECRET) {
      headers.set('CF-Access-Client-Id', env.CF_ACCESS_CLIENT_ID);
      headers.set('CF-Access-Client-Secret', env.CF_ACCESS_CLIENT_SECRET);
    }

    const hasBody = !['GET', 'HEAD'].includes(method);
    let upstream;
    try {
      upstream = await fetch(target.toString(), {
        method,
        headers,
        ...(hasBody ? { body: request.body, duplex: 'half' } : {}),
        redirect: 'manual',
      });
    } catch (err) {
      if (url.pathname.startsWith('/api/')) {
        return jsonResponse(502, 'origin_unreachable', 'The configured OmniFix origin is unreachable.');
      }
      return new Response(
        '<!doctype html><meta charset="utf-8"><title>OmniFix origin unreachable</title><body style="font-family:system-ui;background:#0b0f14;color:#e6edf3;padding:40px"><h1>OmniFix origin unreachable</h1><p>The Worker is configured to proxy an OmniFix origin, but that origin did not respond.</p><p>Check the Docker stack, Cloudflare Tunnel, and OMNIFIX_ORIGIN.</p></body>',
        { status: 502, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' } },
      );
    }

    const responseHeaders = new Headers(upstream.headers);
    for (const name of HOP_BY_HOP_HEADERS) responseHeaders.delete(name);

    // Rewrite upstream redirects back to the Worker hostname.
    const location = responseHeaders.get('location');
    if (location) {
      try {
        const absolute = new URL(location, originOrigin);
        if (absolute.origin === originOrigin) {
          responseHeaders.set(
            'location',
            workerOrigin + absolute.pathname + absolute.search + absolute.hash,
          );
        }
      } catch {
        // Leave malformed/relative locations untouched.
      }
    }

    // Rewrite cookies so they are valid on the Worker hostname.
    const setCookies =
      typeof upstream.headers.getSetCookie === 'function'
        ? upstream.headers.getSetCookie()
        : [];
    if (setCookies.length > 0) {
      responseHeaders.delete('set-cookie');
      for (const cookie of setCookies) {
        responseHeaders.append('set-cookie', rewriteSetCookie(cookie));
      }
    }

    // Do not allow shared caches to store private documents or auth responses.
    responseHeaders.set('cache-control', 'no-store');

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  },
};
