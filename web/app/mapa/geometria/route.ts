import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { Readable } from 'node:stream';
import { createGunzip } from 'node:zlib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  for (const file of [path.join(process.cwd(), '..', 'mapa', 'mapa-estratos-bogota.html'), path.join(process.cwd(), 'mapa', 'mapa-estratos-bogota.html')]) {
    try {
      // El archivo se incluye explícitamente en next.config.ts.
      const html = await readFile(/* turbopackIgnore: true */ file, 'utf8');
      const match = html.match(/<script\b[^>]*\bid="geometry-gzip"[^>]*>([\s\S]*?)<\/script>/i);
      if (!match) return new Response('Geometría no disponible.', { status: 404 });
      const body = Readable.toWeb(Readable.from([Buffer.from(match[1].trim(), 'base64')]).pipe(createGunzip())) as ReadableStream<Uint8Array>;
      return new Response(body, { headers: {
        'Content-Type': 'application/geo+json; charset=utf-8',
        'Cache-Control': 'public, max-age=3600',
        'X-Content-Type-Options': 'nosniff',
      } });
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
  }
  return new Response('Geometría no disponible.', { status: 404 });
}
