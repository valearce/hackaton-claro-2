import type { NextConfig } from 'next';

const config: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    if (process.env.VERCEL) return [];
    return [{ source: '/api/:path*', destination: `${process.env.NBA_API_URL || 'http://127.0.0.1:8001'}/api/:path*` }];
  },
};
export default config;
