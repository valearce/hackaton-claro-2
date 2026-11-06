import type { NextConfig } from 'next';
import path from 'node:path';

const config: NextConfig = {
  poweredByHeader: false,
  images: { qualities: [75, 90] },
  outputFileTracingRoot: path.join(__dirname, '..'),
  outputFileTracingIncludes: { '/mapa': ['../mapa/mapa-estratos-bogota.html'], '/mapa/geometria': ['../mapa/mapa-estratos-bogota.html'] },
  async rewrites() {
    if (process.env.VERCEL) return [];
    return [{ source: '/api/:path*', destination: `${process.env.NBA_API_URL || 'http://127.0.0.1:8001'}/api/:path*` }];
  },
};
export default config;
