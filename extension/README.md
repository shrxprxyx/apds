# APDS Browser Extension (MVP)

Manifest V3 Chrome extension implementing the flow in SRS §5.

## What's implemented
- `manifest.json` — MV3 config, `activeTab`/`storage`/`webNavigation` permissions only (no broad host permission, per §14.4)
- `background.js` — navigation intercept, local verdict cache, calls
  `POST /api/v1/analyse`, subscribes to `/ws/tasks/{task_id}`, relays
  verdicts to the content script, forwards feedback to `/api/v1/feedback`
- `content.js` — Shadow DOM blocking/warning overlay (§5.4), form-submission
  intercept for cross-domain posts to flagged sites (§5.3)
- `popup.html` / `popup.js` — shows the current page's cached verdict

## Not yet implemented (left for later)
- Edge ONNX inference (DistilBERT-tiny, INT8, <10ms local scoring) — the
  extension currently defers **all** scoring to the backend `/analyse`
  call. Wiring in `onnxruntime-web` is the next step once you have an
  exported/quantised model artifact from `nlp-service/train.py`.
- IndexedDB-backed model caching (currently using `chrome.storage.local`
  only for verdicts, not model weights)
- Periodic Redis TI cache sync (30-min diff endpoint from intel-service)

## Setup
1. Make sure `api-gateway` is reachable at `http://localhost:8000`
   (edit `API_BASE` / `WS_BASE` at the top of `background.js` if different).
2. Go to `chrome://extensions`, enable Developer Mode, click
   "Load unpacked", and select this `extension/` folder.
3. Browse normally — every top-level navigation triggers a call to
   `/api/v1/analyse`; a BLOCK/WARN verdict shows the overlay.

## Known gap vs. your docker-compose
Your `api-gateway`'s CORS config needs to allow requests from an
extension origin (`chrome-extension://<id>`) for `fetch()` calls to
succeed — check `services/api-gateway/app/main.py` for a CORS
middleware; add one if it's missing before testing.
