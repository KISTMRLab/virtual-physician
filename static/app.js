import { createStage } from "/static/avatar.js";
import { Speech } from "/static/speech.js";
let script, sectionIndex = 0, formFlow, formItemId;
const $ = (selector) => document.querySelector(selector);
const stage = createStage($("#avatar-canvas"), { background: "#e3eee9", color: 0xe7f5ef });
stage.camera.position.set(0,1.5,3.2);stage.camera.lookAt(0,.9,0);
const speech = new Speech(stage);
let behaviorTimers = [];

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

function behavior(events) {
  behaviorTimers.forEach(clearTimeout);
  behaviorTimers = [];
  for (const event of events) {
    behaviorTimers.push(setTimeout(() => {
      if (event.channel === "expression") stage.expression(event.value, event.intensity);
      if (event.channel === "gesture") stage.gesture(event.value);
      if (event.channel === "viseme") stage.setSpeech(event.value === "open");
    }, event.at_ms || 0));
  }
}

function showSection(speak = false) {
  speech.cancel();
  const section = script.sections[sectionIndex];
  $("#counter").textContent = `SECTION ${sectionIndex + 1} OF ${script.sections.length} · ${section.emotion.toUpperCase()} ${section.intensity}/3`;
  $("#speech").textContent = section.text;
  const media = $("#media");
  media.innerHTML = section.media_url ? `<img src="${section.media_url}" alt="${section.media_alt || "Clinician-provided section illustration"}">` : "<span>No media for this section</span>";
  behavior(section.events);
  if (speak) speech.speak(section.text, {backend: $("#speech-backend").value}).catch(error => {$("#delivery-label").textContent = error.message});
  $("#previous").disabled = sectionIndex === 0; $("#next").disabled = sectionIndex === script.sections.length - 1;
}

function playComparison(mode) {
  const section = script.sections[sectionIndex];
  speech.cancel();
  const events = mode === "neutral" ? section.events.map(event => {
    if (event.channel === "expression") return { ...event, value: "neutral", intensity: 0 };
    if (event.channel === "gesture") return { ...event, value: "rest", intensity: 0 };
    return event;
  }) : section.events;
  behavior(events);
  $("#delivery-label").textContent = ` ${mode} · same authored words`;
  speech.speak(section.text, {backend: $("#speech-backend").value}).catch(error => {$("#delivery-label").textContent = error.message});
}

async function load() {
  try {
    script = await requestJSON("/api/script");
    $("#title").textContent = script.title; $("#review").textContent = `Content attribution: ${script.reviewed_by} · ${script.reviewed_at}`; showSection();
  } catch (error) {
    $("#speech").textContent = `Could not load the explanation: ${error.message}`;
    for (const selector of ["#previous", "#next", "#play", "#neutral-play", "#expressive-play"]) $(selector).disabled = true;
    return;
  }
  try {
    formFlow = await requestJSON("/api/questionnaire");
    if (formFlow.enabled) { $("#questionnaire").hidden = false; $("#form-title").textContent = formFlow.title; formItemId = formFlow.start_id; showFormItem(); }
  } catch (error) {
    $("#answer").textContent = `Feedback form unavailable: ${error.message}`;
  }
}

$("#previous").onclick = () => { sectionIndex--; showSection(); }; $("#next").onclick = () => { sectionIndex++; showSection(); }; $("#play").onclick = () => showSection(true);
$("#neutral-play").onclick = () => playComparison("neutral");
$("#expressive-play").onclick = () => playComparison("expressive");
$("#chat-form").onsubmit = async (event) => {
  event.preventDefault(); const question = new FormData(event.currentTarget).get("question"); $("#answer").textContent = "Searching reviewed sources…";
  try {
    const result = await requestJSON("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
    if (typeof result.answer !== "string" || !Array.isArray(result.citations) || !Array.isArray(result.retrieved) || !Array.isArray(result.events)) throw new Error("The answer response is incomplete.");
    $("#answer").textContent = result.answer;
    $("#citations").replaceChildren(...result.citations.map(item => {const li=document.createElement("li"),link=document.createElement("a");link.href=item.url;link.target="_blank";link.rel="noreferrer";link.textContent=item.title;li.append(link);return li}));
    $("#retrieved").replaceChildren(...result.retrieved.map(item => {const p=document.createElement("p");p.textContent=`${item.title} · score ${item.score}: ${item.passage}`;return p}));
    behavior(result.events);
  } catch (error) {
    $("#answer").textContent = `Could not answer the question: ${error.message}`;
    $("#citations").replaceChildren(); $("#retrieved").replaceChildren();
  }
};
$("#transcribe").onclick = async () => {const file=$("#audio-input").files[0];if(!file)return;try{const result=await speech.transcribe(file);$("[name=question]").value=result.text;$("#answer").textContent=`Transcribed with ${result.backend}. Review the text before asking.`}catch(error){$("#answer").textContent=error.message}};

function showFormItem() {
  const item = formFlow.items.find((candidate) => candidate.id === formItemId);
  if (!item) { $("#feedback-item").textContent = "Feedback complete."; $("#feedback-form button").hidden = true; return; }
  let field = `<textarea name="answer" required></textarea>`;
  if (item.type === "number") field = `<input name="answer" type="number" min="${item.min ?? 1}" max="${item.max ?? 5}" required>`;
  if (item.type === "choice") field = `<select name="answer">${item.options.map((value) => `<option>${value}</option>`).join("")}</select>`;
  if (item.type === "message") field = `<input type="hidden" name="answer" value="acknowledged">`;
  $("#feedback-item").innerHTML = `<label>${item.prompt}${field}</label>`;
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
window.addEventListener("pagehide", () => { behaviorTimers.forEach(clearTimeout); behaviorTimers = []; speech.cancel(); stage.dispose(); });
load();
