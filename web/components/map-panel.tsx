export default function MapPanel() {
  const source = '/mapa#map';
  return <section className="cl-card" aria-labelledby="mapa-titulo">
    <span className="cl-eyebrow">Bogotá</span>
    <h2 id="mapa-titulo">Estratos, clientes y cobertura</h2>
    <p className="cl-q" id="mapa-descripcion">Explora las manzanas por estrato, los agregados de clientes y las capas de cobertura. El análisis de perfiles está en la pestaña Clusters de la consola.</p>
    <div className="cl-acciones"><a className="cl-cta sec" href={source} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}>Abrir mapa en otra pestaña</a></div>
    <iframe
      src={source}
      title="Mapa de estratos, clientes y cobertura de Bogotá"
      aria-describedby="mapa-descripcion"
      loading="lazy"
      allow="geolocation; fullscreen"
      style={{ display: 'block', width: '100%', height: '78vh', minHeight: 520, border: '1px solid var(--linea)', borderRadius: 12 }}
    />
  </section>;
}
