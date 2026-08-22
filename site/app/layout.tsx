import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://giddy-otra-mano.asdaeq.chatgpt.site"),
  title: { default: "Giddy | El agente que no se queda en el chat", template: "%s | Giddy" },
  description: "Giddy es un agente físico: le hablás para consultar tu agenda, poner música, crear imágenes y usar herramientas autorizadas.",
  keywords: ["Giddy", "agente físico", "asistente con IA", "ESP32", "Otra Mano"],
  authors: [{ name: "Otra Mano" }],
  icons: { icon: "/giddy/face-happy-2418.gif", shortcut: "/giddy/face-happy-2418.gif" },
  openGraph: {
    title: "Giddy · El agente que no se queda en el chat",
    description: "Agenda, música, imágenes y herramientas en un objeto al que le hablás con naturalidad.",
    type: "website",
    locale: "es_AR",
    images: [{ url: "/giddy/giddy-motion-hero.png", width: 1536, height: 1024, alt: "Giddy con su carcasa blanca y los ojos redondeados Leaf 2.4.18" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Giddy · El agente que no se queda en el chat",
    description: "Agenda, música, imágenes y herramientas en un objeto al que le hablás con naturalidad.",
    images: ["/giddy/giddy-motion-hero.png"],
  },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f4f3ef" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es"><body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body></html>;
}
