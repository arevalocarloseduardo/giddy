const emotions = [
  ["boot", "Encendido y primera presencia."],
  ["wake", "Vuelve disponible y toma foco."],
  ["dozing", "Transicion suave hacia el descanso."],
  ["goodnight", "Cierre tranquilo antes de dormir."],
  ["listening", "Escucha activa y atenta."],
  ["speaking", "Respuesta clara y expresiva."],
  ["music", "Ritmo, disfrute y energia contenida."],
  ["connecting", "Conexion o sincronizacion en curso."],
  ["curious", "Interes genuino por lo que sigue."],
  ["neutral", "Presencia atenta, tranquila y disponible."],
  ["robot_2", "Alias compatible del estado neutral."],
  ["happy", "Satisfaccion calida y directa."],
  ["laughing", "Alegria abierta sin exageracion."],
  ["sad", "Empatia y tono bajo."],
  ["crying", "Tristeza intensa, legible y breve."],
  ["angry", "Limite firme sin agresion visual."],
  ["sleepy", "Cansancio en reposo."],
  ["surprised", "Sorpresa positiva e inmediata."],
  ["shocked", "Impacto fuerte y alerta."],
  ["thinking", "Procesamiento y busqueda de respuesta."],
  ["confused", "Falta de certeza y pedido implicito de contexto."],
  ["winking", "Complicidad breve."],
  ["loving", "Afecto y cuidado."],
  ["cool", "Calma segura y relajada."],
  ["confident", "Control y decision."],
  ["embarrassed", "Timidez amable."],
  ["funny", "Humor espontaneo."],
  ["silly", "Juego y liviandad."],
  ["kissy", "Gesto afectuoso breve."],
  ["relaxed", "Bienestar sin demanda."],
  ["delicious", "Disfrute y aprobacion."],
];

const avatar = document.querySelector("#avatar");
const title = document.querySelector("#emotion-title");
const role = document.querySelector("#emotion-role");
const stateName = document.querySelector("#state-name");
const variantName = document.querySelector("#variant-name");
const downloadLink = document.querySelector("#download-link");
const grid = document.querySelector("#emotion-grid");
const variantTabs = [...document.querySelectorAll("[data-variant]")];

let activeVariant = "core";
let activeEmotion = "neutral";

function assetPath(emotion) {
  return `../output/giddy-v2-${activeVariant}-240/${emotion}.gif`;
}

function selectEmotion(emotion) {
  const entry = emotions.find(([name]) => name === emotion);
  if (!entry) return;
  activeEmotion = emotion;
  const src = assetPath(emotion);
  avatar.src = `${src}?selected=${Date.now()}`;
  avatar.alt = `Animacion ${emotion} de Giddy`;
  title.textContent = emotion.replace("_", " ");
  role.textContent = entry[1];
  stateName.textContent = `${emotion}.gif`;
  downloadLink.href = src;
  document.querySelectorAll(".emotion-button").forEach((button) => {
    const selected = button.dataset.emotion === emotion;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

function renderGrid() {
  grid.innerHTML = "";
  emotions.forEach(([name]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "emotion-button";
    button.dataset.emotion = name;
    button.setAttribute("aria-pressed", String(name === activeEmotion));
    button.innerHTML = `<img src="${assetPath(name)}" width="112" height="112" alt=""><span>${name.replace("_", " ")}</span>`;
    button.addEventListener("click", () => selectEmotion(name));
    grid.appendChild(button);
  });
  selectEmotion(activeEmotion);
}

variantTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    activeVariant = tab.dataset.variant;
    variantTabs.forEach((candidate) => {
      const selected = candidate === tab;
      candidate.classList.toggle("is-active", selected);
      candidate.setAttribute("aria-selected", String(selected));
    });
    variantName.textContent = activeVariant[0].toUpperCase() + activeVariant.slice(1);
    renderGrid();
  });
});

renderGrid();
