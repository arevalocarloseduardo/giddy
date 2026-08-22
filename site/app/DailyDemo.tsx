"use client";

import Image from "next/image";
import { CalendarDays, Check, ImageIcon, MessageCircleOff, Music2, Pause, Play } from "lucide-react";
import { useEffect, useState } from "react";

const examples = [
  {
    id: "agenda",
    icon: CalendarDays,
    tab: "Agenda",
    time: "08:10",
    state: "ESCUCHANDO",
    face: "face-listening-2418.gif",
    command: "Giddy, ¿qué tengo en mi agenda?",
    source: "Calendario autorizado",
    steps: ["Consulta tus eventos", "Ordena el día por horario", "Resume sólo lo importante"],
    result: "Te cuenta el próximo compromiso y deja el resto del día visible en pantalla.",
  },
  {
    id: "music",
    icon: Music2,
    tab: "Música",
    time: "11:25",
    state: "REPRODUCIENDO",
    face: "face-music-2418.gif",
    command: "Poneme De música ligera de Soda Stereo",
    source: "Búsqueda + parlante",
    steps: ["Encuentra la canción", "Comprueba que el audio empezó", "Muestra su performance musical"],
    result: "La música empieza de verdad y Giddy toca la guitarra en pantalla.",
  },
  {
    id: "image",
    icon: ImageIcon,
    tab: "Imagen",
    time: "14:40",
    state: "CREANDO",
    face: "face-thinking-2418.gif",
    command: "Creame una imagen vertical de un robot tocando la guitarra",
    source: "Generador + pantalla",
    steps: ["Entiende la composición", "Genera la imagen", "La adapta sin deformarla"],
    result: "La imagen aparece con su orientación y proporciones correctas.",
  },
  {
    id: "silent",
    icon: MessageCircleOff,
    tab: "Silencio",
    time: "18:15",
    state: "ESCUCHA SILENCIOSA",
    face: "face-listening-2418.gif",
    command: "Escuchame pero no me hables",
    source: "Modo de interacción",
    steps: ["Deja de usar voz", "Sigue entendiendo pedidos", "Mantiene el modo hasta que lo cambies"],
    result: "Ejecuta acciones y confirma en pantalla sin interrumpirte con voz.",
  },
];

export function DailyDemo() {
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);
  const example = examples[active];

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => {
      setReducedMotion(media.matches);
      if (media.matches) setPlaying(false);
    };
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!playing || reducedMotion) return;
    const timer = window.setInterval(() => {
      setActive((current) => (current + 1) % examples.length);
    }, 5200);
    return () => window.clearInterval(timer);
  }, [active, playing, reducedMotion]);

  return (
    <section className="showcase-section" id="experiencia" aria-labelledby="experience-title">
      <div className="showcase-heading reveal">
        <div>
          <p className="section-index section-index-dark">01 / En acción</p>
          <h2 id="experience-title">Una frase entra. Algo cambia afuera del chat.</h2>
        </div>
        <div className="showcase-intro">
          <p>Cuatro pedidos reales. Cuatro resultados visibles.</p>
          <button
            className="play-control"
            type="button"
            onClick={() => setPlaying((current) => !current)}
            aria-label={playing ? "Pausar recorrido automático" : "Reanudar recorrido automático"}
            title={playing ? "Pausar" : "Reproducir"}
          >
            {playing ? <Pause size={17} aria-hidden="true" /> : <Play size={17} aria-hidden="true" />}
          </button>
        </div>
      </div>

      <div className="showcase-grid" role="tablist" aria-label="Casos de uso reales">
        {examples.map((item, index) => {
          const Icon = item.icon;
          const selected = active === index;
          return (
            <button
              type="button"
              role="tab"
              id={`showcase-tab-${item.id}`}
              aria-controls="showcase-panel"
              aria-selected={selected}
              className={`showcase-card ${selected ? "active" : ""}`}
              key={item.id}
              onClick={() => setActive(index)}
            >
              <span className="showcase-preview">
                <span className="preview-status"><i /> {item.state}</span>
                <Image
                  src={`/giddy/${item.face}`}
                  alt={`Giddy ${item.state.toLowerCase()}`}
                  width={260}
                  height={260}
                  unoptimized
                />
                <span className="preview-command">“{item.command}”</span>
              </span>
              <span className="showcase-card-footer">
                <span><Icon size={18} strokeWidth={1.8} aria-hidden="true" /><strong>{item.tab}</strong></span>
                <small>{item.time}</small>
              </span>
              {selected && playing && !reducedMotion ? <span className="card-progress" aria-hidden="true" /> : null}
            </button>
          );
        })}
      </div>

      <div
        className="showcase-detail"
        id="showcase-panel"
        role="tabpanel"
        aria-labelledby={`showcase-tab-${example.id}`}
        key={example.id}
      >
        <blockquote>“{example.command}”</blockquote>
        <div className="detail-tool">
          <span>Giddy trabaja con</span>
          <strong>{example.source}</strong>
          <ol>
            {example.steps.map((step) => (
              <li key={step}><Check size={16} aria-hidden="true" />{step}</li>
            ))}
          </ol>
        </div>
        <div className="detail-result">
          <span>Resultado</span>
          <p>{example.result}</p>
        </div>
      </div>
      <p className="showcase-note">Comportamientos documentados · algunas funciones requieren internet o una conexión autorizada.</p>
    </section>
  );
}
