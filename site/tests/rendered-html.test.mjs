import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the Giddy commercial site", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>Giddy \| El agente que no se queda en el chat<\/title>/i);
  assert.match(html, /Giddy lo pone en movimiento/);
  assert.match(html, /Una frase entra/);
  assert.match(html, /Agente físico · prototipo funcional/i);
  assert.match(html, /Lista prioritaria/);
  assert.match(html, /giddy-motion-hero\.png/);
  assert.match(html, /giddy-desk-2418\.png/);
  assert.match(html, /giddy-package-2418\.png/);
  assert.match(html, /Tres formas de estar/);
  assert.doesNotMatch(html, /giddy-(?:hero|package)-leaf\.png/);
  assert.doesNotMatch(html, /merch|stickers|gorra|remera|desk mat/i);
  assert.doesNotMatch(html, /codex-preview|SkeletonPreview|react-loading-skeleton/i);
});
