import Image from "next/image";
import {
  ArrowDown,
  ArrowRight,
  BatteryCharging,
  Check,
  Mic2,
  Move3d,
  PackageOpen,
  ShieldCheck,
  Usb,
  Volume2,
  Wifi,
} from "lucide-react";
import { DailyDemo } from "./DailyDemo";
import { PreorderForm } from "./PreorderForm";

const hardware = [
  { icon: Mic2, value: "2 micrófonos", label: "con cancelación de eco" },
  { icon: Volume2, value: "Parlante lateral", label: "voz y música sin ocupar la pantalla" },
  { icon: Move3d, value: "Sensor de 6 ejes", label: "giro, orientación y sacudidas" },
  { icon: Wifi, value: "Wi-Fi + BLE", label: "herramientas y actualizaciones" },
  { icon: BatteryCharging, value: "Soporte de batería", label: "preparado para moverse con vos" },
  { icon: Usb, value: "USB-C lateral", label: "carga y recuperación" },
];

const faqs = [
  {
    question: "¿Giddy ya funciona?",
    answer:
      "Sí. El prototipo escucha y habla, consulta hora, fecha y clima, reproduce música, crea imágenes, usa herramientas, cambia de modo y recibe actualizaciones remotas. La carcasa blanca es la dirección industrial de la primera serie.",
  },
  {
    question: "¿Qué necesita para empezar?",
    answer:
      "Hora, fecha, conversación y controles funcionan desde el inicio. Clima, música, imágenes, calendario, archivos u otras acciones necesitan internet o una conexión autorizada según el caso.",
  },
  {
    question: "¿Escucha todo el tiempo?",
    answer:
      "No. La activación por su nombre ocurre localmente. En modo dormido cierra la conversación y deja de enviar audio hasta que lo despiertes.",
  },
  {
    question: "¿Cuánto cuesta?",
    answer:
      "El precio se confirmará antes de abrir la preventa paga. Entrar a la lista prioritaria no te obliga a comprar y no genera ningún cobro.",
  },
];

function Brand() {
  return (
    <span className="brand-lockup">
      <span className="brand-screen" aria-hidden="true">
        <Image src="/giddy/face-neutral-2418.gif" alt="" width={32} height={32} unoptimized />
      </span>
      <span>giddy</span>
    </span>
  );
}

export default function Home() {
  return (
    <main>
      <header className="site-header">
        <a href="#inicio" aria-label="Giddy, volver al inicio"><Brand /></a>
        <nav aria-label="Navegación principal">
          <a href="#experiencia">En acción</a>
          <a href="#objeto">El objeto</a>
          <a href="#reserva">Primera serie</a>
        </nav>
        <a className="header-action" href="#reserva">
          Reservar <ArrowRight size={16} aria-hidden="true" />
        </a>
      </header>

      <section className="motion-hero" id="inicio" aria-labelledby="hero-title">
        <Image
          className="motion-hero-media"
          src="/giddy/giddy-motion-hero.png"
          alt="Giddy blanco con tres botones superiores, USB-C lateral y sus ojos redondeados"
          fill
          priority
          unoptimized
          sizes="100vw"
        />
        <div className="motion-hero-shade" aria-hidden="true" />
        <div className="motion-hero-copy">
          <p className="hero-kicker"><span /> Agente físico · prototipo funcional</p>
          <h1 id="hero-title"><span>Giddy.</span></h1>
          <p className="hero-promise">
            Decís lo que necesitás. <strong>Giddy lo pone en movimiento.</strong>
          </p>
          <div className="hero-actions">
            <a className="action action-light" href="#experiencia">
              Verlo actuar <ArrowDown size={18} aria-hidden="true" />
            </a>
            <a className="action action-outline" href="#reserva">
              Primera serie <ArrowRight size={18} aria-hidden="true" />
            </a>
          </div>
        </div>
        <div className="hero-specs" aria-label="Estado del producto">
          <span><i /> Funcional</span>
          <span>Leaf 2.4.18</span>
          <span>240 × 240 RGB565</span>
        </div>
      </section>

      <div className="motion-rail" aria-label="Funciones de Giddy">
        <div>
          <span>AGENDA</span><i />
          <span>MÚSICA</span><i />
          <span>IMÁGENES</span><i />
          <span>ARCHIVOS</span><i />
          <span>VOZ</span><i />
          <span>SILENCIO</span><i />
          <span aria-hidden="true">AGENDA</span><i aria-hidden="true" />
          <span aria-hidden="true">MÚSICA</span><i aria-hidden="true" />
          <span aria-hidden="true">IMÁGENES</span><i aria-hidden="true" />
          <span aria-hidden="true">ARCHIVOS</span><i aria-hidden="true" />
          <span aria-hidden="true">VOZ</span><i aria-hidden="true" />
          <span aria-hidden="true">SILENCIO</span><i aria-hidden="true" />
        </div>
      </div>

      <section className="motion-manifesto reveal" aria-labelledby="manifesto-title">
        <p className="section-index section-index-dark">00 / Fuera del chat</p>
        <div>
          <h2 id="manifesto-title">No es otro lugar donde escribir. Es algo que está ahí y hace.</h2>
          <p>
            Le hablás como a una persona. Giddy escucha, usa la herramienta correcta y deja
            un resultado visible sin mandarte a recorrer menús.
          </p>
        </div>
        <dl className="manifesto-stats">
          <div><dt>01</dt><dd>frase natural</dd></div>
          <div><dt>01</dt><dd>acción concreta</dd></div>
          <div><dt>00</dt><dd>menús que aprender</dd></div>
        </dl>
      </section>

      <DailyDemo />

      <section className="day-scene" aria-labelledby="day-title">
        <div className="day-media">
          <Image
            src="/giddy/giddy-desk-2418.png"
            alt="Giddy en un escritorio junto a un cuaderno y un teléfono"
            fill
            unoptimized
            sizes="(max-width: 820px) 100vw, 62vw"
          />
        </div>
        <div className="day-copy reveal">
          <p className="section-index">02 / Un día normal</p>
          <h2 id="day-title">Vos seguís. Giddy resuelve.</h2>
          <p>El pedido no termina en otra aplicación abierta.</p>
          <ol className="day-lines">
            <li><span>08:10</span><strong>“¿Qué tengo en mi agenda?”</strong></li>
            <li><span>11:25</span><strong>“Poneme De música ligera.”</strong></li>
            <li><span>14:40</span><strong>“Creame una imagen para esta idea.”</strong></li>
          </ol>
        </div>
      </section>

      <section className="modes-section" aria-labelledby="modes-title">
        <div className="section-lead reveal">
          <p className="section-index">03 / Presencia</p>
          <h2 id="modes-title">Tres formas de estar. Ninguna invade.</h2>
          <p>El modo queda activo hasta que vos lo cambies.</p>
        </div>
        <div className="mode-grid">
          <article>
            <div><Image src="/giddy/face-speaking-2418.gif" alt="Giddy en modo charla" width={210} height={210} unoptimized /></div>
            <span>01 / CHARLA</span>
            <h3>Escucha y responde.</h3>
            <p>Usa voz y ejecuta acciones.</p>
          </article>
          <article>
            <div><Image src="/giddy/face-listening-2418.gif" alt="Giddy escuchando en silencio" width={210} height={210} unoptimized /></div>
            <span>02 / SILENCIO</span>
            <h3>Entiende sin hablar.</h3>
            <p>Hace y confirma en pantalla.</p>
          </article>
          <article>
            <div><Image src="/giddy/face-goodnight-2418.gif" alt="Giddy dormido" width={210} height={210} unoptimized /></div>
            <span>03 / DORMIDO</span>
            <h3>La conversación termina.</h3>
            <p>No vuelve a escuchar hasta que lo despiertes.</p>
          </article>
        </div>
      </section>

      <section className="object-section" id="objeto" aria-labelledby="object-title">
        <div className="object-copy reveal">
          <p className="section-index">04 / El objeto</p>
          <h2 id="object-title">Lo girás. Lo tocás. Lo despertás.</h2>
          <p>
            La cara y los subtítulos acompañan la orientación. Una sacudida lo despierta y
            los tres controles superiores responden de inmediato.
          </p>
          <span className="prototype-mark"><Check size={17} aria-hidden="true" /> Electrónica ya probada</span>
        </div>
        <div className="hardware-list">
          {hardware.map(({ icon: Icon, value, label }) => (
            <div key={value}>
              <Icon size={23} strokeWidth={1.7} aria-hidden="true" />
              <strong>{value}</strong>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="package-section" aria-labelledby="package-title">
        <div className="package-media">
          <Image
            src="/giddy/giddy-package-2418.png"
            alt="Packaging blanco de Giddy con dispositivo, cable USB-C y guía"
            fill
            unoptimized
            sizes="(max-width: 900px) 100vw, 62vw"
          />
          <span>Concepto de packaging · primera serie</span>
        </div>
        <div className="package-copy reveal">
          <PackageOpen size={32} strokeWidth={1.5} aria-hidden="true" />
          <p className="section-index">05 / Primera serie</p>
          <h2 id="package-title">Abrís la caja. Decís “Giddy”.</h2>
          <ul>
            <li><Check size={17} aria-hidden="true" /><span>Dispositivo Giddy</span></li>
            <li><Check size={17} aria-hidden="true" /><span>Cable USB-C</span></li>
            <li><Check size={17} aria-hidden="true" /><span>Guía de configuración inicial</span></li>
            <li><Check size={17} aria-hidden="true" /><span>Agente y actualizaciones remotas</span></li>
          </ul>
          <p className="package-note">El contenido final se confirmará antes de la preventa paga.</p>
        </div>
      </section>

      <section className="trust-section" aria-labelledby="trust-title">
        <div className="trust-lead reveal">
          <ShieldCheck size={38} strokeWidth={1.45} aria-hidden="true" />
          <p className="section-index section-index-dark">06 / Control</p>
          <h2 id="trust-title">Vos decidís cuándo escucha, habla y actúa.</h2>
        </div>
        <div className="trust-points">
          <p><strong>En espera</strong><span>La activación por “Giddy” ocurre localmente. Antes de eso no envía audio.</span></p>
          <p><strong>En una tarea</strong><span>Usa únicamente las fuentes y herramientas que autorizaste.</span></p>
          <p><strong>Dormido</strong><span>Cierra la conversación y no vuelve a escuchar hasta que lo despiertes.</span></p>
        </div>
      </section>

      <section className="reserve-section" id="reserva" aria-labelledby="reserve-title">
        <div className="reserve-copy reveal">
          <p className="section-index">07 / Lista prioritaria</p>
          <h2 id="reserve-title">La primera serie empieza con una tarea real.</h2>
          <p>
            Contanos qué querés sacarte de encima. Te diremos qué puede hacer desde el primer
            día, qué conexión necesita y cuándo podrías recibir una unidad.
          </p>
          <div className="reserve-note">
            <ShieldCheck size={19} aria-hidden="true" />
            <span>No pagás ahora. Primero confirmamos precio, alcance y fecha.</span>
          </div>
        </div>
        <PreorderForm />
      </section>

      <section className="faq-section" aria-labelledby="faq-title">
        <div className="faq-heading reveal">
          <p className="section-index">Antes de reservar</p>
          <h2 id="faq-title">Lo importante, sin letra chica.</h2>
        </div>
        <div className="faq-list">
          {faqs.map((faq) => (
            <details key={faq.question}>
              <summary>{faq.question}<span aria-hidden="true">+</span></summary>
              <p>{faq.answer}</p>
            </details>
          ))}
        </div>
      </section>

      <footer>
        <Brand />
        <p>Un agente físico creado por <strong>Otra Mano</strong>.</p>
        <a href="#inicio">Volver arriba <ArrowRight size={15} aria-hidden="true" /></a>
      </footer>
    </main>
  );
}
