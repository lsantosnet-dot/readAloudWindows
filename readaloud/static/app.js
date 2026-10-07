"use strict";

const $ = (sel, root = document) => root.querySelector(sel);

const LANG_NAMES = { pt: "Português", en: "Inglês" };
const TEXT_EXTENSIONS = /\.(txt|text|md|markdown|mdown|rst|log|csv|tsv|json|xml|html?|srt|vtt|ini|ya?ml)$/i;
const MAX_FILE_BYTES = 5 * 1024 * 1024;

const state = {
  cards: [],
  voices: [],
  settings: { speed: 1, default_lang: "pt", default_voices: {} },
};

// --------------------------------------------------------------------- API

async function api(path, options = {}) {
  const init = { ...options, headers: { ...(options.headers || {}) } };
  if (init.body !== undefined && typeof init.body !== "string") {
    init.body = JSON.stringify(init.body);
    init.headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, init);
  if (!res.ok) throw new Error(await errorMessage(res));
  if (res.status === 204) return null;
  return res.json();
}

async function errorMessage(res) {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join("; ");
  } catch { /* corpo não-JSON */ }
  return `Erro ${res.status}`;
}

// ------------------------------------------------------------------ toasts

function toast(message, kind = "info") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), kind === "error" ? 6000 : 2500);
}

// ---------------------------------------------------------------- player

const player = {
  audio: new Audio(),
  cardId: null,
  segments: [],
  index: 0,
  status: "idle", // idle | loading | playing | paused
  token: 0,       // invalida downloads de reproduções anteriores
  cache: new Map(), // índice -> Promise<objectURL>

  async toggle(cardId) {
    if (this.cardId === cardId) {
      if (this.status === "playing") return this.pause();
      if (this.status === "paused") return this.resume();
      if (this.status === "loading") return;
    }
    this.stop();
    await this.start(cardId);
  },

  async start(cardId) {
    const token = ++this.token;
    this.cardId = cardId;
    this.setStatus("loading");
    try {
      const { segments } = await api(`/api/cards/${cardId}/segments`);
      if (token !== this.token) return;
      this.segments = segments;
      await this.playIndex(0, token);
    } catch (err) {
      if (token === this.token) this.fail(err);
    }
  },

  fetchSegment(index, token) {
    if (!this.cache.has(index)) {
      const cardId = this.cardId;
      const promise = (async () => {
        const res = await fetch(`/api/cards/${cardId}/audio/${index}`);
        if (!res.ok) throw new Error(await errorMessage(res));
        return URL.createObjectURL(await res.blob());
      })();
      promise.catch(() => {}); // erro tratado por quem aguarda
      this.cache.set(index, promise);
    }
    return this.cache.get(index);
  },

  async playIndex(index, token) {
    this.index = index;
    if (this.status !== "paused") this.setStatus("loading");
    const url = await this.fetchSegment(index, token);
    if (token !== this.token) return;
    this.audio.src = url;
    this.applySpeed();
    if (this.status === "paused") return; // pausado enquanto carregava: fica pronto
    await this.audio.play();
    if (token !== this.token) return;
    this.setStatus("playing");
    if (index + 1 < this.segments.length) this.fetchSegment(index + 1, token);
    this.release(index - 1);
  },

  pause() {
    this.audio.pause();
    this.setStatus("paused");
  },

  async resume() {
    if (!this.audio.src) return;
    try {
      await this.audio.play();
      this.setStatus("playing");
    } catch (err) {
      this.fail(err);
    }
  },

  stop() {
    this.token++;
    this.audio.pause();
    this.audio.removeAttribute("src");
    for (const index of [...this.cache.keys()]) this.release(index);
    const previous = this.cardId;
    this.cardId = null;
    this.segments = [];
    this.status = "idle";
    if (previous !== null) renderPlayerState(previous);
  },

  release(index) {
    const promise = this.cache.get(index);
    if (!promise) return;
    this.cache.delete(index);
    promise.then((url) => URL.revokeObjectURL(url)).catch(() => {});
  },

  async next() {
    const token = this.token;
    if (this.index + 1 >= this.segments.length) return this.stop();
    try {
      await this.playIndex(this.index + 1, token);
    } catch (err) {
      if (token === this.token) this.fail(err);
    }
  },

  applySpeed() {
    const speed = Number(state.settings.speed) || 1;
    this.audio.defaultPlaybackRate = speed;
    this.audio.playbackRate = speed;
    this.audio.preservesPitch = true;
  },

  setStatus(status) {
    this.status = status;
    renderPlayerState(this.cardId);
  },

  fail(err) {
    toast(err.message || String(err), "error");
    this.stop();
  },
};

player.audio.addEventListener("ended", () => player.next());
player.audio.addEventListener("error", () => {
  if (player.cardId !== null && player.audio.getAttribute("src")) player.fail(new Error("Não foi possível tocar o áudio."));
});

function renderPlayerState(cardId) {
  const el = document.querySelector(`.card[data-id="${cardId}"]`);
  if (!el) return;
  const active = player.cardId === cardId;
  const status = active ? player.status : "idle";
  el.dataset.state = status;
  el.classList.toggle("active", active);
  $(".stop", el).disabled = !active;
  $(".play", el).title = status === "playing" ? "Pausar" : status === "paused" ? "Continuar" : "Ouvir";
  $(".progress", el).textContent =
    active && player.segments.length > 1 ? `trecho ${player.index + 1} de ${player.segments.length}` : "";
}

// ----------------------------------------------------------------- cards

const dateFormat = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

function voiceLabel(id) {
  const voice = state.voices.find((v) => v.id === id);
  return voice ? voice.label : "nenhuma voz";
}

function fillVoiceSelect(select, card) {
  select.replaceChildren();
  const auto = new Option(`Automática · ${voiceLabel(card.effective_voice)}`, "");
  select.append(auto);
  const byLang = new Map();
  for (const voice of state.voices) {
    if (!byLang.has(voice.lang)) byLang.set(voice.lang, []);
    byLang.get(voice.lang).push(voice);
  }
  for (const [lang, voices] of byLang) {
    const group = document.createElement("optgroup");
    group.label = LANG_NAMES[lang] || lang.toUpperCase();
    for (const voice of voices) group.append(new Option(voice.label, voice.id));
    select.append(group);
  }
  select.value = card.voice && state.voices.some((v) => v.id === card.voice) ? card.voice : "";
}

function buildCard(card) {
  const el = $("#card-template").content.firstElementChild.cloneNode(true);
  el.dataset.id = card.id;
  $(".lang", el).textContent = card.lang;
  $(".lang", el).title = LANG_NAMES[card.lang] || card.lang;
  $(".card-source", el).textContent = card.source ? `📄 ${card.source}` : "Colado";
  $(".card-source", el).title = card.source || "";
  const date = new Date(card.created_at * 1000);
  $(".card-date", el).textContent = dateFormat.format(date);
  $(".card-date", el).dateTime = date.toISOString();
  $(".card-text", el).textContent = card.text;
  fillVoiceSelect($(".voice", el), card);

  $(".play", el).addEventListener("click", () => player.toggle(card.id));
  $(".stop", el).addEventListener("click", () => player.stop());
  $(".delete", el).addEventListener("click", () => deleteCard(card.id));
  $(".voice", el).addEventListener("change", (e) => changeVoice(card.id, e.target.value));
  $(".more", el).addEventListener("click", (e) => {
    const expanded = el.classList.toggle("expanded");
    e.target.textContent = expanded ? "mostrar menos" : "mostrar mais";
  });
  return el;
}

function render() {
  const list = $("#cards");
  list.replaceChildren(...state.cards.map(buildCard));
  $("#empty").hidden = state.cards.length > 0;
  $("#clear-all-btn").disabled = state.cards.length === 0;
  requestAnimationFrame(updateMoreLinks);
  if (player.cardId !== null) renderPlayerState(player.cardId);
}

function updateMoreLinks() {
  for (const el of document.querySelectorAll(".card")) {
    const text = $(".card-text", el);
    $(".more", el).hidden = !el.classList.contains("expanded") && text.scrollHeight <= text.clientHeight + 2;
  }
}

function replaceCard(card) {
  const index = state.cards.findIndex((c) => c.id === card.id);
  if (index >= 0) state.cards[index] = card;
  const old = document.querySelector(`.card[data-id="${card.id}"]`);
  if (old) {
    const fresh = buildCard(card);
    fresh.classList.toggle("expanded", old.classList.contains("expanded"));
    old.replaceWith(fresh);
    requestAnimationFrame(updateMoreLinks);
    renderPlayerState(card.id);
  }
}

async function addCard(text, source = null) {
  if (!text || !text.trim()) return;
  try {
    const card = await api("/api/cards", { method: "POST", body: { text, source } });
    state.cards.unshift(card);
    render();
    toast(source ? `Importado: ${source}` : `Texto adicionado (${(LANG_NAMES[card.lang] || card.lang).toLowerCase()})`);
  } catch (err) {
    toast(source ? `${source}: ${err.message}` : err.message, "error");
  }
}

async function deleteCard(id) {
  if (player.cardId === id) player.stop();
  try {
    await api(`/api/cards/${id}`, { method: "DELETE" });
    state.cards = state.cards.filter((c) => c.id !== id);
    render();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function deleteAll() {
  if (!state.cards.length) return;
  if (!confirm(`Apagar todos os ${state.cards.length} cards? Isso não pode ser desfeito.`)) return;
  player.stop();
  try {
    await api("/api/cards", { method: "DELETE" });
    state.cards = [];
    render();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function changeVoice(id, voice) {
  if (player.cardId === id) player.stop();
  try {
    replaceCard(await api(`/api/cards/${id}`, { method: "PATCH", body: { voice } }));
  } catch (err) {
    toast(err.message, "error");
  }
}

// ------------------------------------------------------- colar / importar

function isEditable(target) {
  return target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
}

document.addEventListener("paste", (e) => {
  if (isEditable(e.target) || $("#settings-dialog").open) return;
  const data = e.clipboardData;
  if (!data) return;
  e.preventDefault();
  const files = [...data.files];
  if (files.length) return importFiles(files);
  addCard(data.getData("text/plain"));
});

function decodeText(buffer) {
  // UTF-8 (com ou sem BOM) primeiro; senão, o padrão antigo do Windows.
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch {
    return new TextDecoder("windows-1252").decode(buffer);
  }
}

function htmlToText(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll("script, style, noscript").forEach((n) => n.remove());
  return doc.body ? doc.body.innerText || doc.body.textContent : "";
}

async function importFiles(files) {
  for (const file of files) {
    if (!TEXT_EXTENSIONS.test(file.name) && !file.type.startsWith("text/")) {
      toast(`${file.name}: tipo de arquivo não suportado`, "error");
      continue;
    }
    if (file.size > MAX_FILE_BYTES) {
      toast(`${file.name}: arquivo maior que 5 MB`, "error");
      continue;
    }
    let text = decodeText(await file.arrayBuffer());
    if (/\.html?$/i.test(file.name)) text = htmlToText(text);
    if (!text.trim()) {
      toast(`${file.name}: arquivo vazio`, "error");
      continue;
    }
    await addCard(text, file.name);
  }
}

$("#import-btn").addEventListener("click", () => $("#file-input").click());
$("#file-input").addEventListener("change", async (e) => {
  await importFiles([...e.target.files]);
  e.target.value = "";
});

let dragDepth = 0;
const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");
window.addEventListener("dragenter", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth++;
  $("#drop-overlay").hidden = false;
});
window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
window.addEventListener("dragleave", (e) => {
  if (!hasFiles(e)) return;
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) $("#drop-overlay").hidden = true;
});
window.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth = 0;
  $("#drop-overlay").hidden = true;
  importFiles([...e.dataTransfer.files]);
});

// ------------------------------------------------------ velocidade/ajustes

let saveSpeedTimer = null;
function showSpeed() {
  const speed = Number(state.settings.speed) || 1;
  $("#speed").value = speed;
  $("#speed-value").textContent = `${speed.toFixed(2)}×`;
}

$("#speed").addEventListener("input", (e) => {
  state.settings.speed = Number(e.target.value);
  showSpeed();
  player.applySpeed();
  clearTimeout(saveSpeedTimer);
  saveSpeedTimer = setTimeout(() => saveSettings({ speed: state.settings.speed }), 400);
});

async function saveSettings(values) {
  try {
    state.settings = await api("/api/settings", { method: "PUT", body: values });
  } catch (err) {
    toast(err.message, "error");
  }
}

function languages() {
  return [...new Set(["pt", "en", ...state.voices.map((v) => v.lang)])];
}

function renderSettings() {
  $("#voices-dir").textContent = state.settings.voices_dir || "";
  const container = $("#default-voices");
  container.replaceChildren();
  for (const lang of languages()) {
    const voices = state.voices.filter((v) => v.lang === lang);
    const label = document.createElement("label");
    label.className = "field";
    const span = document.createElement("span");
    span.textContent = LANG_NAMES[lang] || lang.toUpperCase();
    const select = document.createElement("select");
    if (!voices.length) select.append(new Option("nenhuma voz instalada", ""));
    for (const voice of voices) select.append(new Option(voice.label, voice.id));
    select.value = state.settings.default_voices?.[lang] || voices[0]?.id || "";
    select.disabled = !voices.length;
    select.addEventListener("change", async () => {
      await saveSettings({ default_voices: { ...state.settings.default_voices, [lang]: select.value } });
      await loadCards();
    });
    label.append(span, select);
    container.append(label);
  }
  const langSelect = $("#default-lang");
  langSelect.replaceChildren(...languages().map((l) => new Option(LANG_NAMES[l] || l.toUpperCase(), l)));
  langSelect.value = state.settings.default_lang;
}

$("#default-lang").addEventListener("change", (e) => saveSettings({ default_lang: e.target.value }));
$("#settings-btn").addEventListener("click", () => {
  renderSettings();
  $("#settings-dialog").showModal();
});
$("#open-voices-btn").addEventListener("click", () =>
  api("/api/voices/open-folder", { method: "POST" }).catch((err) => toast(err.message, "error")));
$("#refresh-voices-btn").addEventListener("click", async () => {
  try {
    state.voices = await api("/api/voices/refresh", { method: "POST" });
    renderSettings();
    renderNotice();
    await loadCards();
    toast(`${state.voices.length} voz(es) encontrada(s)`);
  } catch (err) {
    toast(err.message, "error");
  }
});
$("#clear-all-btn").addEventListener("click", deleteAll);

function renderNotice() {
  const notice = $("#notice");
  notice.hidden = state.voices.length > 0;
  notice.textContent =
    "Nenhuma voz instalada. Rode setup.bat (ou: python -m readaloud --download-voices) " +
    "e depois clique em ⚙ → Recarregar vozes.";
}

// ------------------------------------------------------------------ início

async function loadCards() {
  state.cards = await api("/api/cards");
  render();
}

async function init() {
  try {
    [state.settings, state.voices] = await Promise.all([api("/api/settings"), api("/api/voices")]);
    showSpeed();
    renderNotice();
    await loadCards();
  } catch (err) {
    toast(`Falha ao carregar: ${err.message}`, "error");
  }
}

window.addEventListener("resize", () => requestAnimationFrame(updateMoreLinks));
init();
