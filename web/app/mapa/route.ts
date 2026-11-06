import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import path from 'node:path';
import { Readable } from 'node:stream';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const filename = 'mapa-estratos-bogota.html';

export async function GET() {
  // El mapa es un único HTML autocontenido. No se aceptan rutas de la solicitud.
  const candidates = [
    path.join(process.cwd(), '..', 'mapa', filename),
    path.join(process.cwd(), 'mapa', filename),
  ];
  for (const file of candidates) {
    try {
      // next.config.ts incluye explícitamente el HTML; evita trazar todo el repositorio.
      if (!(await stat(/* turbopackIgnore: true */ file)).isFile()) continue;
      const body = Readable.toWeb(createReadStream(/* turbopackIgnore: true */ file)) as ReadableStream<Uint8Array>;
      return new Response(body, { headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=0, must-revalidate',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
      } });
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
  }
  return new Response('El mapa no está disponible en este servidor.', { status: 404 });
}
