// APDS Background Service Worker (Manifest V3)
// Responsibilities (per SRS §5.1 / §5.3):
//  - Intercept navigation events
//  - Check local LRU cache for a known verdict
//  - Otherwise call POST /api/v1/analyse and subscribe to the
//    WebSocket channel returned for the async verdict
//  - Relay BLOCK/WARN/ALLOW verdicts to the content script
//  - Persist verdicts into a capped local cache (chrome.storage)

const API_BASE = "http://localhost:8000"; // change to your api-gateway origin
const WS_BASE = "ws://localhost:8000";
const CACHE_KEY = "apds_verdict_cache";
const CACHE_MAX_ENTRIES = 10000; // per SRS §3.3 (LRU, 10k entries)

// ---- Simple LRU-ish cache backed by chrome.storage.local ----
// (A true in-memory LRU is faster but doesn't survive service-worker
// suspension; we keep an in-memory mirror for the current session and
// flush periodically to storage.)
let cacheMirror = null;

async function loadCache() {
  if (cacheMirror) return cacheMirror;
  const stored = await chrome.storage.local.get(CACHE_KEY);
  cacheMirror = stored[CACHE_KEY] || {};
  return cacheMirror;
}

async function saveCache() {
  const keys = Object.keys(cacheMirror);
  if (keys.length > CACHE_MAX_ENTRIES) {
    // Evict oldest by insertion order (Map semantics emulated via array)
    const toDrop = keys
      .map((k) => [k, cacheMirror[k].ts])
      .sort((a, b) => a[1] - b[1])
      .slice(0, keys.length - CACHE_MAX_ENTRIES)
      .map(([k]) => k);
    toDrop.forEach((k) => delete cacheMirror[k]);
  }
  await chrome.storage.local.set({ [CACHE_KEY]: cacheMirror });
}

async function getCachedVerdict(url) {
  const cache = await loadCache();
  return cache[url] || null;
}

async function setCachedVerdict(url, verdict) {
  const cache = await loadCache();
  cache[url] = { ...verdict, ts: Date.now() };
  await saveCache();
}

// ---- API calls ----
async function requestAnalysis(url, tabId) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/analyse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, context: "browser" }),
    });

    if (!res.ok) {
      console.warn("APDS: analyse request failed", res.status);
      return;
    }

    const data = await res.json(); // { task_id, websocket_channel, cache_hit }

    if (data.cache_hit) {
      // Backend already had a cached verdict server-side; poll once.
      const verdictRes = await fetch(`${API_BASE}/api/v1/verdict/${data.task_id}`);
      if (verdictRes.ok) {
        const verdict = await verdictRes.json();
        handleVerdict(url, tabId, verdict);
      }
      return;
    }

    subscribeToVerdict(data.task_id, url, tabId);
  } catch (err) {
    console.warn("APDS: analyse request errored", err);
  }
}

function subscribeToVerdict(taskId, url, tabId) {
  const ws = new WebSocket(`${WS_BASE}/ws/tasks/${taskId}`);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.status === "COMPLETE" && msg.verdict) {
        handleVerdict(url, tabId, msg.verdict);
        ws.close();
      } else if (msg.status === "TIMEOUT") {
        console.warn("APDS: verdict timed out for", url);
        ws.close();
      }
      // status === "PROCESSING" -> keep waiting
    } catch (e) {
      console.warn("APDS: bad WS message", e);
    }
  };

  ws.onerror = () => ws.close();
}

async function handleVerdict(url, tabId, verdict) {
  await setCachedVerdict(url, verdict);

  if (verdict.verdict === "BLOCK") {
    chrome.tabs.sendMessage(tabId, { type: "APDS_BLOCK", verdict }).catch(() => {});
  } else if (verdict.verdict === "WARN") {
    chrome.tabs.sendMessage(tabId, { type: "APDS_WARN", verdict }).catch(() => {});
  } else {
    chrome.tabs.sendMessage(tabId, { type: "APDS_ALLOW", verdict }).catch(() => {});
  }
}

// ---- Navigation intercept (§5.3) ----
chrome.webNavigation.onCommitted.addListener(async (details) => {
  if (details.frameId !== 0) return; // main frame only
  const { url, tabId } = details;
  if (!url.startsWith("http")) return;

  const cached = await getCachedVerdict(url);
  if (cached) {
    // Immediate local decision from cache, then re-validate async in background.
    handleVerdict(url, tabId, cached);
    return;
  }

  // Unknown domain: page loads normally (non-blocking), async analysis runs.
  requestAnalysis(url, tabId);
});

// ---- Messages from content script / popup ----
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "APDS_GET_CACHED_VERDICT") {
    getCachedVerdict(message.url).then((v) => sendResponse(v));
    return true; // async
  }

  if (message.type === "APDS_REPORT_FEEDBACK") {
    fetch(`${API_BASE}/api/v1/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        verdict_id: message.verdictId,
        label: message.label, // TRUE_PHISHING | FALSE_POSITIVE
      }),
    }).catch((err) => console.warn("APDS: feedback submit failed", err));
    return false;
  }
});
