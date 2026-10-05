# Enhancing doctor‐patient communication in surgical explanations: Designing effective facial expressions and gestures for animated physician characters

**Hwang Youn Kim, Ghazanfar Ali, Jae‐In Hwang**

**Computer Animation and Virtual Worlds · 2024** · Published

[Paper / publisher](https://doi.org/10.1002/cav.2236) · [Project page](https://ghazanfarali.com/research/virtual-physician/) · [BibTeX](CITATION.bib) · [Requirements](REQUIREMENTS.md) · [Code & setup](#implementation-and-usage)

> Expression and gesture support surgical explanations by animated physicians.

![Graphical abstract: grounded surgical explanations, expressive avatar behavior and communication study findings](paper-assets/graphical-abstract.png)

*Graphical abstract diagram. Grounded explanations and expressive behavior support virtual-physician communication.*

## Why this research

Surgical explanations carry both factual and interpersonal information. This research studies how facial expression and co-speech gesture shape the experience of receiving an explanation from an animated physician.

The system lets clinicians prepare explanations with a virtual physician and lets patients ask follow-up questions. It combines grounded medical information with designed facial expression and co-speech gesture, and evaluates how users perceive the presentation.

## Method at a glance

**Surgical content / question** → **Grounded answer + behavior** → **Animated explanation**

| | Research system |
|---|---|
| Input | Clinician-prepared surgical content and patient questions |
| Method | Content preparation, grounded question answering, facial expression, and gesture |
| Output | Animated surgical explanations and grounded follow-up responses |

## Evidence and scope

113-participant study; reported answer F1 comparison 0.492 to 0.779

**Attribution:** These findings describe the paper or manuscript, not results obtained with this repository's code.

**Study context:** Surgical-explanation materials and study conditions described in the paper.

**Limitations:** This is communication research. Perceived social presence and answer scores do not demonstrate improved clinical outcomes or autonomous medical decision-making.

## Explore the implementation

Authored explanation flows, sourced follow-up retrieval, facial/gesture/voice events and a portable browser preview. It does not reproduce the paper's models or establish clinical effectiveness.

This repository contains independently written research code. The institute's original source, datasets and trained models are not distributed. Public-data preparation, commands, assumptions and checks are documented below and in [REQUIREMENTS.md](REQUIREMENTS.md).

## Resources and citation

Read the paper through its [publisher record](https://doi.org/10.1002/cav.2236). PDFs are hosted by publishers or preprint archives rather than stored in this repository.

Please cite the research paper when using its ideas; [download the BibTeX citation](CITATION.bib). The implementation has its own documented scope.

## Implementation and usage

<!-- implementation-guide -->

This standalone repository reimplements the communication pipeline from **“Enhancing doctor-patient communication in surgical explanations: Designing effective facial expressions and gestures for animated physician characters”** by Hwang Youn Kim, Ghazanfar Ali, and Jae-In Hwang, *Computer Animation and Virtual Worlds* 35(3), e2236, 2024. DOI: [10.1002/cav.2236](https://doi.org/10.1002/cav.2236).

The original institute implementation is unavailable. This new research implementation supports clinician-authored sectioned explanations, media, expression/gesture/viseme events, source-grounded follow-up questions, and branched feedback forms. It does not contain the paper's Unity project, Faceware captures, avatars, voice/gesture assets, HealthCareMagic sample, generated medical-term data, Llama weights, participant data, or experimental results.

The paper adopts the authors' multilingual co-speech gesture preprint as its gesture-generation research lineage; see the separate [multilingual-gesture implementation](https://github.com/ghazanPK/multilingual-gesture). This demo's motion plan is a transparent adapter and does not reuse that model or claim its trained behavior.

The included quickstart uses synthetic interface fixtures without clinical review. A deployment must replace them with licensed educational sources and explanations reviewed by an accountable clinician. This software does not diagnose, recommend treatment, calculate clinical risk, handle emergencies, or replace communication with a qualified clinician.

### Setup and run

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
python scripts/prepare_viewer.py
virtual-physician --sources .\examples\sources.jsonl --script .\examples\script.json --questionnaire .\examples\questionnaire.json
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) for the procedural 3D explanation, neutral/expressive comparison, cited questions and optional feedback flow. The bundled files are synthetic interface fixtures and contain no patient or paper data. For API and event checks, run `python scripts/verify.py` and `virtual-physician-validate .\examples\script.json`. The check writes `outputs/verify/script.json`, `answer.json`, `questionnaire.json`, and `questionnaire-branch.json`; omit `--questionnaire` when feedback is not required.

### Clinician-authored explanation format

`script.json` must identify the reviewer and review date. Emotions follow the paper (`neutral`, `anger`, `disgust`, `fear`, `happiness`, `sadness`, `surprise`) and intensity is 1–3:

```json
{
  "title": "Clinician-authored procedure explanation",
  "reviewed_by": "Name and role of accountable reviewer",
  "reviewed_at": "2026-10-03",
  "sections": [
    {
      "id": "overview",
      "text": "Insert the clinician-approved explanation here.",
      "emotion": "neutral",
      "intensity": 1,
      "gesture": "open_hand",
      "media_url": "https://your-approved-host.example/illustration.png",
      "media_alt": "Clinician-approved description of the illustration"
    }
  ]
}
```

Media remains on its configured host. Confirm copyright, accessibility, and patient-education suitability before use.

### Grounded source format

`sources.jsonl` contains one reviewed passage per line:

```json
{"source_id":"stable-id","title":"Public reference title","url":"https://authoritative.example/page","reviewed_at":"2026-10-03","text":"A licensed or permitted passage reviewed for this deployment."}
```

The local TF-IDF retriever ranks passages and the default answer selects relevant sentences verbatim from those passages. Every returned answer includes clickable provenance. If nothing matches, it declines and directs the user to the clinical team. This is deliberately conservative; a generative model may only be added after a clinical review process that checks every answer against retrieved evidence.

A practical public starting point is [MedlinePlus for Developers](https://medlineplus.gov/about/developers/), maintained by the U.S. National Library of Medicine. Its APIs, XML files, and linking options have different usage rules. The [MedlinePlus Connect service documentation](https://medlineplus.gov/medlineplus-connect/web-service/) says returned service data may be linked/displayed under its acceptable-use terms and warns against copying MedlinePlus pages wholesale. Preserve source URLs, attribution, review dates, and the terms of every source. User-provided hospital materials require their own authorization and review.

### Research feedback form

An optional `questionnaire.json` defines `choice`, `number`, `text`, and `message` items, default `next` edges, and `eq`/`gte`/`lte` branches. It is a navigation and feedback mechanism only. The loader rejects fields named `diagnosis`, `risk_score`, or `clinical_score`; the runtime returns only the next item ID and does not compute or claim a validated diagnostic result.

The browser keeps answers in page memory and this server does not persist them. Do not request identifying or sensitive health information without an approved privacy, security, consent, and data-retention design.

### Swap in reviewed deployment content

Copy the three example files, preserve their documented keys, and replace their synthetic text with licensed, reviewed material. Point the same `virtual-physician` command at the new paths; no code change is required. `scripts/verify.py` exercises the same app factory and API routes used by the server, including the explanation, cited question-answering, behavior events, and questionnaire branch.

### Browser event preview

The procedural Three.js character demonstrates the event contract: speech, one facial state with intensity, gesture, and timed viseme cues run in parallel. Browser speech synthesis and text-derived visemes are portable approximations, not the paper's Naver TTS, SALSA lip sync, Faceware expressions, multilingual gesture system, or a validated bedside interface.


### Public source import and 3D browser playback

`python -m virtual_physician.importer` imports one explicitly selected public educational page into a local JSONL collection. It records the HTTPS source URL and supplied review date; inspect and edit the extracted text before serving. This is a preparation tool, not clinician review. The authored explanation script remains a separate file. Do not replace its `reviewed_by` field with an automated importer or claim review that did not occur.

```powershell
python -m virtual_physician.importer "https://your-permitted-educational-source.example/page" --file data/page.html --id page-1 --title "Source title" --reviewed-at 2026-10-05 --out data/sources.jsonl
virtual-physician --sources data/sources.jsonl --script data/approved-script.json
```

The browser presents the same authored explanation in neutral and expressive delivery with an original procedural Three.js character. The Q&A pane shows ranked source passages and an extractive answer separately from scripted clinical content. Browser speech and typed questions work without models. The quickstart prepares the pinned renderer in ignored `static/vendor/`; no avatar assets or model weights are included. For optional local speech, run `python -m pip install -e ".[speech]"`, prepare the English phonemizer dependencies in [Kokoro's setup guide](https://github.com/hexgrad/kokoro) (including `espeak-ng` where required), and set `KOKORO_MODEL_DIR` to a user-owned folder with `config.json`, `kokoro-v1_0.pth`, and `voices/af_heart.pt`. Set `WHISPER_MODEL_DIR` to a local converted faster-whisper folder with `model.bin`. The UI reports configuration errors and leaves browser speech and typed input available.

<!-- avatar-recorded-motion:start -->
## Bundled characters and recorded public motion

The browser demos include Rowan and Mira, two new fictional GLB characters built with MPFB and MakeHuman community assets under CC0 1.0. See [avatar licensing and provenance](static/avatars/LICENSE.md). Use the character selector in the stage. The shared renderer supports body bones, ARKit facial channels, and approximate speaking motion.

The [recorded BEAT motion companion](static/recorded-motion.html) opens at `/static/recorded-motion.html` while the demo server is running. It plays locally selected motion, face, and WAV files on the bundled characters; this is recorded public-data inspection, separate from the paper implementation. No BEAT recording, dataset archive, or trained model is bundled. Install the one preparation dependency and fetch a small official sample into ignored `outputs/beat-demo/`:

```sh
python -m pip install numpy
python scripts/beat_demo/fetch_modalities.py --speaker 1 --sequence 1_wayne_0_1_1 --include-bvh --max-bytes 25000000 --output-dir outputs/beat-demo/source
python scripts/beat_demo/prepare_bvh.py --bvh outputs/beat-demo/source/1_wayne_0_1_1.bvh --output outputs/beat-demo/sample/1_wayne_0_1_1-raw-motion.json --frames 120
python scripts/beat_demo/prepare_modalities.py --sequence 1_wayne_0_1_1 --source outputs/beat-demo/source --output outputs/beat-demo/sample --frames 120
```

Open the companion and select `outputs/beat-demo/sample/1_wayne_0_1_1-raw-motion.json`, `1_wayne_0_1_1-face.json`, and `1_wayne_0_1_1.wav`. The downloader caps each original file at 25 MB; the prepared clip contains up to 120 frames. The viewer uses local files and does not upload them. For other BEAT takes, substitute a matching official speaker and sequence ID.
<!-- avatar-recorded-motion:end -->
