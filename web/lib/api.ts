export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal, cache: 'no-store' });
  if (!response.ok) {
    const result = await response.json().catch(() => ({ detail: `No se pudo completar la operación (${response.status})` }));
    throw new Error(typeof result.detail === 'string' ? result.detail : 'Revisa los valores de la configuración');
  }
  return response.json() as Promise<T>;
}
export const nf = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });
export const value = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 4 });
export const percent = new Intl.NumberFormat('es-CO', { style: 'percent', maximumFractionDigits: 2 });
const names: Record<string, string> = { asesor: 'Asesor', whatsapp: 'WhatsApp', correo: 'Correo', sms: 'SMS' };
export const channelName = (id: string) => names[id] || id;
