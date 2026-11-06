import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Orquestador NBA · Claro', description: 'Configura campañas, simula la siguiente mejor acción y revisa el cumplimiento de las reglas.', icons: { icon: '/claro.png' } };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es"><body>{children}</body></html>;
}
