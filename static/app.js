import { createStage } from "/static/avatar.js?v=20261006-paper1";
import { Speech } from "/static/speech.js?v=20261006-paper1";
import {prepareApplicationMotion,gestureSummary} from "/static/application-gesture.js?v=20261006-paper1";
let script, sectionIndex = 0, formFlow, formItemId, lastAnswer = null;
const $ = (selector) => document.querySelector(selector);
const stage = createStage($("#avatar-canvas"), { background: "#e3eee9", color: 0xe7f5ef });
stage.camera.position.set(0,1.5,3.2);stage.camera.lookAt(0,.9,0);
// Blink, breathing and head idle come from the shared renderer when it provides them.
stage.setIdle?.(true);
let activeMotion=null, playGeneration=0, loadedAvatar="rowan", activeVoice=null;

// The shared renderer exposes setExpression(name, level 1-3) for the paper's
// seven emotions. Older renderers only accept expression(name, 0-1).
const LEGACY_EMOTION = { happiness: "happy", sadness: "sad" };
function setFace(emotion = "neutral", level = 1) {
  if (typeof stage.setExpression === "function") stage.setExpression(emotion, level);
  else stage.expression(LEGACY_EMOTION[emotion] || emotion, level / 3);
}

// Persona voices. Kokoro voices use a per-voice API base; browser speech gets
// the persona's pitch, rate and preferred system voice on each utterance.
const speechClients = new Map();
function speechFor(voice) {
  const key = voice?.kokoro_voice || "";
  if (!speechClients.has(key)) speechClients.set(key, new Speech(stage, key ? `/api/voice/${encodeURIComponent(key)}` : "/api"));
  return speechClients.get(key);
}
function cancelSpeech() { for (const client of speechClients.values()) client.cancel(); }
if (window.speechSynthesis) {
  const synth = window.speechSynthesis, speak = synth.speak.bind(synth);
  synth.speak = (utterance) => {
    if (activeVoice) {
      if (Number.isFinite(Number(activeVoice.pitch))) utterance.pitch = Number(activeVoice.pitch);
      if (Number.isFinite(Number(activeVoice.rate))) utterance.rate = Number(activeVoice.rate);
      const voices = synth.getVoices?.() || [], language = (activeVoice.language || "en").toLowerCase();
      const wanted = activeVoice.browser_voice?.toLowerCase();
      const match = wanted ? voices.find((v) => v.name.toLowerCase().includes(wanted)) : null;
      if (match) utterance.voice = match;
      else if (!utterance.voice) { const local = voices.find((v) => v.lang?.toLowerCase().startsWith(language)); if (local) utterance.voice = local; }
    }
    return speak(utterance);
  };
}

function errorText(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => item.msg || String(item)).join("; ");
  return detail?.message || "The request could not be completed.";
}

async function requestJSON(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(`${errorText(payload?.detail || payload?.error)} (HTTP ${response.status})`);
  if (!payload) throw new Error("The server returned an empty response.");
  return payload;
}

const setLabel = (text) => { $("#delivery-label").textContent = text; };
function currentPersona() { return $("#persona").value || script.sections[sectionIndex]?.persona || script.persona; }
async function applyPersona(name) {
  const persona = script.personas[name] || script.personas[script.persona];
  $("#persona-label").textContent = persona.label;
  if (persona.avatar !== loadedAvatar && typeof stage.setCharacter === "function") {
    loadedAvatar = persona.avatar;
    await stage.setCharacter(persona.avatar);
  }
  return persona;
}

// Events from the server are the single source for each delivery channel.
function planFrom(events) {
  const byChannel = Object.fromEntries(events.map(event => [event.channel, event]));
  const expression = byChannel.expression || { value: "neutral", level: 1 };
  return { text: byChannel.speech?.value || "", emotion: expression.value,
    level: expression.level ?? Math.max(1, Math.round((expression.intensity ?? .34) * 3)),
    gesture: byChannel.gesture?.value || "auto", lipSync: Boolean(byChannel.viseme) };
}

function stopPlayback() {
  cancelSpeech(); activeMotion?.onEnd(); activeMotion = null;
  stage.clearMotion(); stage.gesture("idle"); stage.setSpeech(false); stage.setSpeechLevel(0);
  $("#media video")?.pause();
}

async function perform({ events, label, personaName, neutral = false, video = null }) {
  const generation = ++playGeneration;
  stopPlayback();
  const plan = planFrom(events), persona = await applyPersona(personaName);
  if (generation !== playGeneration) return;
  const authored = plan.gesture && plan.gesture !== "auto";
  let prepared = null;
  if (!neutral && !authored) {
    try { prepared = await prepareApplicationMotion(stage, plan.text, { mode: "multilingual" }); }
    catch (error) { setLabel(`Recorded co-speech unavailable: ${error.message}`); }
  }
  if (generation !== playGeneration) return;
  activeMotion = prepared?.motion || null;
  const face = neutral ? ["neutral", 1] : [plan.emotion, plan.level];
  const pose = neutral ? "rest" : authored ? plan.gesture : "idle";
  const summary = neutral ? "neutral face, no gesture" : authored ? `authored gesture ${plan.gesture}` : prepared ? gestureSummary(prepared.data) : "no recorded gesture";
  const begin = () => { setFace(...face); stage.gesture(pose); activeMotion?.onStart(); video?.play().catch(() => {}); };
  activeVoice = persona.voice;
  setLabel(`${label} · ${persona.label} · ${face[0]} ${face[1]}/3 · ${summary}`);
  try {
    await speechFor(persona.voice).speak(plan.text, { backend: $("#speech-backend").value, language: persona.voice.language || "en-US", lipSync: plan.lipSync,
      onStart: () => { begin(); setLabel(`Playing ${label} · ${persona.label} · ${face[0]} ${face[1]}/3 · ${summary}`); },
      onProgress: clock => { const sample = activeMotion?.onProgress(clock); if (sample) setLabel(`Playing ${label}: ${sample.slot.gesture_id} · frame ${Math.floor(Math.min(sample.localTime * activeMotion.fps, sample.slot.frames.length - 1)) + 1}`); },
      onEnd: ({ reason }) => { if (generation !== playGeneration) return; activeMotion?.onEnd(); activeMotion = null; stage.clearMotion(); stage.gesture("idle"); setLabel(`${reason === "ended" ? "Finished" : "Stopped"} ${label}`); },
    });
  } catch (error) {
    if (generation !== playGeneration) return;
    setLabel(`${error.message}. Playing face and motion without speech.`);
    begin(); prepared?.motion.playSilent();
  }
}

function showMedia(section) {
  const media = $("#media");
  media.replaceChildren();
  if (section.video_url) {
    const video = document.createElement("video");
    Object.assign(video, { src: section.video_url, controls: true, muted: true, playsInline: true, preload: "metadata" });
    video.setAttribute("aria-label", section.media_alt || "Clinician-provided section video");
    media.append(video);
  } else if (section.media_url) {
    const image = document.createElement("img");
    image.src = section.media_url; image.alt = section.media_alt || "Clinician-provided section illustration";
    media.append(image);
  }
  media.hidden = !media.childElementCount;
  media.closest(".stage").classList.toggle("without-media", media.hidden);
}

function showSection(speak = false) {
  playGeneration++; stopPlayback(); setFace("neutral", 1);
  const section = script.sections[sectionIndex];
  $("#counter").textContent = `SECTION ${sectionIndex + 1} OF ${script.sections.length} · ${section.emotion.toUpperCase()} ${section.intensity}/3 · ${(script.personas[section.persona]?.label || section.persona).toUpperCase()}`;
  $("#speech").textContent = section.text;
  showMedia(section);
  applyPersona(currentPersona());
  if (speak) playSection("expressive");
  $("#previous").disabled = sectionIndex === 0; $("#next").disabled = sectionIndex === script.sections.length - 1;
}

function playSection(mode) {
  const section = script.sections[sectionIndex];
  return perform({ events: section.events, label: `section ${sectionIndex + 1} (${mode})`, personaName: currentPersona(), neutral: mode === "neutral", video: $("#media video") });
}

async function load() {
  try {
    script = await requestJSON("/api/script");
    $("#title").textContent = script.title; $("#review").textContent = `Content attribution: ${script.reviewed_by} · ${script.reviewed_at}`;
    for (const [name, persona] of Object.entries(script.personas)) $("#persona").append(new Option(`${persona.label} (${persona.avatar})`, name));
    showSection();
  } catch (error) {
    $("#speech").textContent = `Could not load the explanation: ${error.message}`;
    for (const selector of ["#previous", "#next", "#play", "#neutral-play", "#expressive-play"]) $(selector).disabled = true;
    return;
  }
  requestJSON("/api/speech-status").then(status => { $("#answer-mode").textContent = status.answer_mode === "rag-generation" ? `Answers are generated by ${status.generator} from retrieved passages, with citations.` : "Answers are extracted verbatim from retrieved passages (no LLM configured)."; }).catch(() => {});
  try {
    formFlow = await requestJSON("/api/questionnaire");
    if (formFlow.enabled) { $("#questionnaire").hidden = false; $("#form-title").textContent = formFlow.title; formItemId = formFlow.start_id; showFormItem(); }
  } catch (error) {
    $("#answer").textContent = `Feedback form unavailable: ${error.message}`;
  }
}

$("#previous").onclick = () => { sectionIndex--; showSection(); }; $("#next").onclick = () => { sectionIndex++; showSection(); }; $("#play").onclick = () => showSection(true);
$("#neutral-play").onclick = () => playSection("neutral");
$("#expressive-play").onclick = () => playSection("expressive");
$("#persona").onchange = () => { stopPlayback(); applyPersona(currentPersona()); };
$("#replay-answer").onclick = () => { if (lastAnswer) speakAnswer(lastAnswer); };

function speakAnswer(result) {
  return perform({ events: result.events, label: result.grounded ? "answer" : "decline", personaName: currentPersona() });
}

$("#chat-form").onsubmit = async (event) => {
  event.preventDefault(); const question = new FormData(event.currentTarget).get("question"); $("#answer").textContent = "Searching reviewed sources…";
  try {
    const result = await requestJSON("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
    if (typeof result.answer !== "string" || !Array.isArray(result.citations) || !Array.isArray(result.retrieved) || !Array.isArray(result.events)) throw new Error("The answer response is incomplete.");
    lastAnswer = result; $("#replay-answer").disabled = false;
    $("#answer").textContent = result.answer;
    const mode = document.createElement("small"); mode.className = "answer-mode";
    mode.textContent = ` [${result.answer_mode}${result.generation_error ? `: ${result.generation_error}` : ""}]`;
    $("#answer").append(mode);
    $("#citations").replaceChildren(...result.citations.map(item => {const li=document.createElement("li"),link=document.createElement("a");link.href=item.url;link.target="_blank";link.rel="noreferrer";link.textContent=`${item.marker ? `[${item.marker}] ` : ""}${item.title}`;li.append(link);return li}));
    const floor = result.grounding || {};
    $("#retrieved").replaceChildren(...result.retrieved.map(item => {const p=document.createElement("p"),below=item.score<floor.min_score||item.coverage<floor.min_coverage;p.textContent=`${item.title} · score ${item.score} · coverage ${item.coverage}${below?" · below grounding floor":""}: ${item.passage}`;if(below)p.className="below-floor";return p}));
    if ($("#speak-answers").checked) speakAnswer(result);
  } catch (error) {
    $("#answer").textContent = `Could not answer the question: ${error.message}`;
    $("#citations").replaceChildren(); $("#retrieved").replaceChildren();
  }
};
$("#transcribe").onclick = async () => {const file=$("#audio-input").files[0];if(!file)return;try{const result=await speechFor(null).transcribe(file);$("[name=question]").value=result.text;$("#answer").textContent=`Transcribed with ${result.backend}. Review the text before asking.`}catch(error){$("#answer").textContent=error.message}};

function field(tag, attributes = {}) { const element = document.createElement(tag); for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value); return element; }
function showFormItem() {
  const item = formFlow.items.find((candidate) => candidate.id === formItemId);
  if (!item) { $("#feedback-item").textContent = "Feedback complete."; $("#feedback-form button").hidden = true; return; }
  let control = field("textarea", { name: "answer", required: "" });
  if (item.type === "number") control = field("input", { name: "answer", type: "number", min: String(item.min ?? 1), max: String(item.max ?? 5), required: "" });
  if (item.type === "choice") { control = field("select", { name: "answer" }); for (const value of item.options || []) control.append(new Option(String(value), String(value))); }
  if (item.type === "message") control = field("input", { type: "hidden", name: "answer", value: "acknowledged" });
  const label = document.createElement("label"); label.append(String(item.prompt), control);
  $("#feedback-item").replaceChildren(label);
  feedbackError.textContent = "";
}
const feedbackError = document.createElement("p");
feedbackError.setAttribute("role", "alert");
$("#feedback-form").append(feedbackError);
$("#feedback-form").onsubmit = async (event) => {
  event.preventDefault();
  const answer = new FormData(event.currentTarget).get("answer");
  const button = $("#feedback-form button");
  feedbackError.textContent = "";
  button.disabled = true;
  try {
    const result = await requestJSON("/api/questionnaire/respond", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item_id: formItemId, answer }) });
    if (!("next_id" in result)) throw new Error("The feedback response is incomplete.");
    formItemId = result.next_id;
    showFormItem();
  } catch (error) {
    feedbackError.textContent = `Could not save this response: ${error.message}`;
  } finally {
    button.disabled = false;
  }
};
window.addEventListener("pagehide", () => { cancelSpeech(); stage.dispose(); });
load();
