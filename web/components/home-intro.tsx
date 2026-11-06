'use client';

import Image from 'next/image';
import { useEffect, useRef } from 'react';
import { nf } from '@/lib/api';

const channels = ['Asesor', 'WhatsApp', 'Correo', 'SMS'];
const dots = Array.from({ length: 20 }, (_, i) => ({ x: 40 + (i % 4) * 22, y: 155 + Math.floor(i / 4) * 28 }));

export default function HomeIntro({ clients, campaigns, channelCount, onExplore }: { clients: number; campaigns: number; channelCount: number; onExplore: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const items = root.current?.querySelectorAll<HTMLElement>('[data-reveal]');
    if (!items) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) {
      items.forEach(item => item.classList.add('is-visible')); return;
    }
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } });
    }, { threshold: .12 });
    items.forEach(item => observer.observe(item));
    return () => observer.disconnect();
  }, []);

  return <div className="cl-home-landing" ref={root}>
    <section className="cl-intro" aria-labelledby="home-intro-title">
      <div className="cl-intro-copy">
        <p className="cl-intro-kicker">Claro · Next Best Action</p>
        <h2 id="home-intro-title">La oferta correcta, <span>en el momento preciso.</span></h2>
        <p className="cl-intro-description">Elegimos qué ofrecer y por qué canal contactar a cada cliente.</p>
      </div>
      <div className="cl-intro-photo">
        <Image src="/imagenes/portada-claro-v2.png" alt="Una mujer consulta su celular en su hogar en Bogotá" fill sizes="(max-width: 700px) 1920px, (max-width: 1150px) 1600px, 100vw" quality={90} preload />
        <div className="cl-intro-action">
          <h3>Encuentra la siguiente mejor acción</h3>
          <p>Explora tus campañas y configura el escenario que quieres comparar.</p>
          <div className="cl-intro-summary"><span>Escenario inicial</span><strong>{nf.format(clients)} clientes</strong></div>
          <button className="cl-intro-cta" type="button" onClick={onExplore}>Entrar al simulador<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m9 5 7 7-7 7" /></svg></button>
        </div>
      </div>
      <button className="cl-intro-scroll" type="button" onClick={onExplore} aria-label="Bajar al simulador"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M12 4v15m-6-6 6 6 6-6" /></svg></button>
    </section>
    <section className="cl-intro-story" aria-labelledby="home-story-title">
      <h2 id="home-story-title" data-reveal>Una oferta. El canal adecuado.</h2>
      <div className="cl-intro-story-grid" data-reveal>
      <div className="cl-intro-art" aria-hidden="true">
        <svg viewBox="0 0 540 440" className="cl-intro-network">
          <path d="M-50 405C145 90 365 525 600 12" className="cl-intro-orbit" />
          <path d="M-40 430C165 125 360 550 610 40" className="cl-intro-orbit" />
          <text x="36" y="56" className="cl-intro-art-caption">De una base de clientes</text>
          <text x="36" y="81" className="cl-intro-art-caption">a una mejor decisión.</text>
          {dots.map((dot, i) => <circle key={i} cx={dot.x} cy={dot.y} r="4.5" className="cl-intro-person" style={{ animationDelay: `${i * 130}ms` }} />)}
          <text x="36" y="326" className="cl-intro-art-label">Clientes</text>
          <path d="M120 224H164" className="cl-intro-link" />
          <path d="M120 224H164" className="cl-intro-flow" />
          {channels.map((name, i) => {
            const y = 113 + i * 78;
            const path = `M286 224C326 224 312 ${y} 356 ${y}`;
            return <g key={name}>
              <path d={path} className="cl-intro-link" />
              <path d={path} className="cl-intro-flow" style={{ animationDelay: `${i * -400}ms` }} />
              <rect x="356" y={y - 23} width="145" height="46" rx="5" className="cl-intro-channel" />
              <circle cx="374" cy={y} r="3" fill="currentColor" />
              <text x="389" y={y + 5} className="cl-intro-art-label">{name}</text>
            </g>;
          })}
          <circle cx="225" cy="224" r="75" className="cl-intro-wave" />
          <circle cx="225" cy="224" r="61" className="cl-intro-hub" />
          <text x="225" y="234" textAnchor="middle" className="cl-intro-nba">NBA</text>
          <text x="36" y="405" className="cl-intro-art-footer">Una oferta. El canal adecuado.</text>
        </svg>
      </div>
        <div className="cl-intro-story-copy">
          <h3>De una base de clientes<br />a una mejor decisión.</h3>
          <p>Explora los perfiles, ajusta las campañas y distribuye los cupos de cada canal.</p>
          <dl className="cl-intro-numbers"><div><dt>Clientes</dt><dd>{nf.format(clients)}</dd></div><div><dt>Campañas</dt><dd>{nf.format(campaigns)}</dd></div><div><dt>Canales</dt><dd>{nf.format(channelCount)}</dd></div></dl>
          <button type="button" className="cl-intro-text-link" onClick={onExplore}>Explorar el escenario <span aria-hidden="true">→</span></button>
        </div>
      </div>
    </section>
  </div>;
}
