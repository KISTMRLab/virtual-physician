let script, sectionIndex = 0, formFlow, formItemId;
const $ = (selector) => document.querySelector(selector);

function behavior(events) {
  const avatar = $("#avatar");
  for (const event of events) {
    setTimeout(() => {
      if (event.channel === "expression") avatar.dataset.emotion = event.value;
      if (event.channel === "gesture") avatar.dataset.gesture = event.value;
      if (event.channel === "viseme") $(".mouth").classList.toggle("open", event.value === "open");
    }, event.at_ms || 0);
  }
}

function showSection(speak = false) {
  const section = script.sections[sectionIndex];
  $("#counter").textContent = `SECTION ${sectionIndex + 1} OF ${script.sections.length} · ${section.emotion.toUpperCase()} ${section.intensity}/3`;
  $("#speech").textContent = section.text;
  const media = $("#media");
  media.innerHTML = section.media_url ? `<img src="${section.media_url}" alt="${section.media_alt || "Clinician-provided section illustration"}">` : "<span>No media for this section</span>";
  behavior(section.events);
  if (speak && "speechSynthesis" in window) { speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(section.text)); }
  $("#previous").disabled = sectionIndex === 0; $("#next").disabled = sectionIndex === script.sections.length - 1;
}

async function load() {
  script = await fetch("/api/script").then((response) => response.json());
  $("#title").textContent = script.title; $("#review").textContent = `Reviewed by ${script.reviewed_by} · ${script.reviewed_at}`; showSection();
  formFlow = await fetch("/api/questionnaire").then((response) => response.json());
  if (formFlow.enabled) { $("#questionnaire").hidden = false; $("#form-title").textContent = formFlow.title; formItemId = formFlow.start_id; showFormItem(); }
}

$("#previous").onclick = () => { sectionIndex--; showSection(); }; $("#next").onclick = () => { sectionIndex++; showSection(); }; $("#play").onclick = () => showSection(true);
$("#chat-form").onsubmit = async (event) => {
  event.preventDefault(); const question = new FormData(event.currentTarget).get("question"); $("#answer").textContent = "Searching reviewed sources…";
  const result = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) }).then((response) => response.json());
  $("#answer").textContent = result.answer; $("#citations").innerHTML = result.citations.map((item) => `<li><a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a></li>`).join(""); behavior(result.events);
};

function showFormItem() {
  const item = formFlow.items.find((candidate) => candidate.id === formItemId);
  if (!item) { $("#feedback-item").textContent = "Feedback complete."; $("#feedback-form button").hidden = true; return; }
  let field = `<textarea name="answer" required></textarea>`;
  if (item.type === "number") field = `<input name="answer" type="number" min="${item.min ?? 1}" max="${item.max ?? 5}" required>`;
  if (item.type === "choice") field = `<select name="answer">${item.options.map((value) => `<option>${value}</option>`).join("")}</select>`;
  if (item.type === "message") field = `<input type="hidden" name="answer" value="acknowledged">`;
  $("#feedback-item").innerHTML = `<label>${item.prompt}${field}</label>`;
}
$("#feedback-form").onsubmit = async (event) => { event.preventDefault(); const answer = new FormData(event.currentTarget).get("answer"); const result = await fetch("/api/questionnaire/respond", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item_id: formItemId, answer }) }).then((response) => response.json()); formItemId = result.next_id; showFormItem(); };
load();

