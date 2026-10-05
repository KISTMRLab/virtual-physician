# Reimplementation requirements

This repository reproduces the paper's communication architecture while treating every medical statement as externally authored and reviewed content.

## Required behavior

1. Load a clinician-authored explanation split into ordered sections with emotion, intensity, gesture, and optional media per section.
2. Validate attribution, review date, emotion vocabulary, media URLs, and non-empty section text before serving.
3. Retrieve question-relevant passages from user-provided public/clinician-approved sources and return source-linked evidence.
4. Use an extractive grounded answer by default so the system cannot silently add medical claims. Expose retrieved evidence as the boundary for a separately reviewed generator.
5. Emit parallel speech, facial-expression, gesture, and viseme events for each explanation section and answer.
6. Provide a browser UI for the scripted explanation, questions/chat, source citations, and a research questionnaire flow.
7. Questionnaire branching may navigate an authored form but must not calculate diagnoses, risk classes, or validated clinical scores.
8. Keep all state in the local process/browser by default and avoid collecting personal health information.

## Deliberate boundaries

- This is research software for clinician-reviewed patient education, not a medical device, diagnostic assistant, emergency service, or substitute for a clinician.
- No HealthCareMagic sample, generated medical terms, Llama weights, vector store, surgery content, participant data, avatars, Faceware captures, gestures, or study results are included.
- Text-derived visemes, bundled fictional CC0 characters, and locally retrieved BEAT motion only demonstrate behavior events; they are not clinical communication validation or the paper's Unity rendering. Optional local speech adapters require user-provided models and do not establish clinical accuracy.

## Acceptance checks

- Tests cover source validation, retrieval provenance, script-to-behavior events, and questionnaire navigation without diagnostic scoring.
- Server files compile and the static client passes JavaScript syntax checking; no network or model download is required.

## Bundled fictional avatar substitution

Two newly generated fictional CC0 humanoids replace the original avatar assets in the browser demo. They provide a 53-bone rig and named ARKit/viseme targets. Motion retargeting adapts source joints to their bind pose; speaking envelopes approximate mouth motion rather than phoneme alignment. The optional recorded BEAT companion inspects public motion, face and audio files prepared locally, independently of the paper's learned algorithm. No dataset recordings or trained weights are bundled.

## Local recorded co-speech integration

The browser application retrieves prepared BEAT body-motion clips with `multilingual` mode: the multilingual gesture component adopted in section 3.5 of the paper. The first `python scripts/start_demo.py` run fetches a small official BVH/TextGrid sample, constructs a nine-clip bank, and fits the local retrieval artifact under ignored `outputs/beat-library/`. Install `scripts/requirements-demo.txt` first. Preparation code and method dependencies are vendored in this repository; no sibling clone, original institute library, full dataset, or pretrained weights are bundled. The clinician-authored content, grounded question answering, and questionnaire remain this application's core. The separate recorded-motion companion remains available for local motion/face/audio inspection.
