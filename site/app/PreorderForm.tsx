"use client";

import { FormEvent, useState } from "react";
import { MessageCircle, Send } from "lucide-react";

const whatsappNumber = "12062387157";

export function PreorderForm() {
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const name = String(data.get("name") || "").trim();
    const email = String(data.get("email") || "").trim();
    const interest = String(data.get("interest") || "").trim();
    const use = String(data.get("use") || "").trim();
    const message = [
      "Hola, quiero entrar a la lista prioritaria de Giddy.",
      `Nombre: ${name}`,
      `Email: ${email}`,
      `Interés: ${interest}`,
      use ? `Lo usaría para: ${use}` : "",
    ].filter(Boolean).join("\n");

    setSubmitted(true);
    window.open(
      `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(message)}`,
      "_blank",
      "noopener,noreferrer",
    );
  }

  return (
    <form className="preorder-form" onSubmit={handleSubmit}>
      <div className="form-heading">
        <MessageCircle size={22} strokeWidth={1.9} aria-hidden="true" />
        <div><strong>Lista prioritaria</strong><span>Te respondemos por WhatsApp.</span></div>
      </div>
      <label>
        Nombre
        <input name="name" autoComplete="name" placeholder="¿Cómo te llamás?" required />
      </label>
      <label>
        Email
        <input name="email" type="email" autoComplete="email" placeholder="vos@ejemplo.com" required />
      </label>
      <label>
        Me interesa
        <select name="interest" defaultValue="Una unidad para mí">
          <option>Una unidad para mí</option>
          <option>Giddy para mi negocio</option>
          <option>Varias unidades para mi equipo</option>
          <option>Distribuir Giddy</option>
        </select>
      </label>
      <label>
        ¿Qué querés que haga?
        <textarea name="use" rows={3} placeholder="Contanos una tarea que hoy te quita tiempo" />
      </label>
      <button type="submit">
        {submitted ? "Abrir WhatsApp de nuevo" : "Guardar mi lugar"}
        <Send size={17} strokeWidth={2.1} aria-hidden="true" />
      </button>
      <small>Al enviar se abre WhatsApp con estos datos. No realizamos ningún cobro.</small>
    </form>
  );
}
