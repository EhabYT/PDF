/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    if (process.env.NODE_ENV === 'development') {
      return [{ source: '/api/:path*', destination: `${process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8000'}/api/:path*` }];
    }
    return [];
  },
};
export default nextConfig;
