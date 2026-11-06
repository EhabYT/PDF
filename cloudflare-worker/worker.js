// Static notice Worker for misconnected Cloudflare Workers Builds.
// This is intentionally NOT the OmniFix application backend.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname.startsWith('/api/')) {
      return new Response(
        JSON.stringify({
          error: {
            code: 'not_deployed_here',
            message:
              'The OmniFix API is not deployed on Cloudflare Workers. Run the full app with Docker and expose it through Cloudflare Tunnel.',
          },
        }),
        {
          status: 501,
          headers: {
            'content-type': 'application/json; charset=utf-8',
            'cache-control': 'no-store',
          },
        },
      );
    }

    return env.ASSETS.fetch(request);
  },
};
