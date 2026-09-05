// APDS Content Script
// Injects a Shadow DOM overlay (SRS §5.4) when the background worker
// reports a BLOCK or WARN verdict for the current page.

let overlayHost = null;

function buildOverlay(verdict) {
  if (overlayHost) return; // already showing one

  overlayHost = document.createElement("div");
  overlayHost.id = "apds-overlay-host";
  overlayHost.style.cssText =
    "all: initial; position: fixed; inset: 0; z-index: 2147483647;";
  document.documentElement.appendChild(overlayHost);

  const shadow = overlayHost.attachShadow({ mode: "closed" });

  const isBlock = verdict.verdict === "BLOCK";
  const topSignals = (verdict.explainability && verdict.explainability.top_signals) || [];

  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <style>
      .apds-scrim {
        position: fixed; inset: 0;
        background: ${isBlock ? "#1B0000" : "#1B3A6B"};
        color: #fff;
        font-family: -apple-system, Segoe UI, Roboto, sans-serif;
        display: flex; align-items: center; justify-content: center;
        z-index: 2147483647;
      }
      .apds-card {
        max-width: 480px; background: #12141a; border-radius: 12px;
        padding: 32px; box-shadow: 0 20px 60px rgba(0,0,0,.5);
      }
      .apds-badge {
        display: inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: 12px; font-weight: 700; letter-spacing: .04em;
        background: ${isBlock ? "#E84545" : "#E8A945"}; color: #10121a;
        margin-bottom: 16px;
      }
      h1 { font-size: 20px; margin: 0 0 12px; }
      p { font-size: 14px; line-height: 1.5; color: #c7cbd4; margin: 0 0 16px; }
      ul { margin: 0 0 20px; padding-left: 18px; font-size: 13px; color: #9aa1af; }
      .apds-actions { display: flex; gap: 8px; flex-wrap: wrap; }
      button {
        font: inherit; font-size: 13px; font-weight: 600; padding: 10px 16px;
        border-radius: 8px; border: none; cursor: pointer;
      }
      .apds-primary { background: #E84545; color: #fff; }
      .apds-secondary { background: #2a2d38; color: #fff; }
      .apds-ghost { background: transparent; color: #9aa1af; text-decoration: underline; }
    </style>
    <div class="apds-scrim">
      <div class="apds-card">
        <span class="apds-badge">${isBlock ? "PHISHING DETECTED" : "SUSPICIOUS"}</span>
        <h1>${isBlock ? "This page looks like phishing" : "This page looks suspicious"}</h1>
        <p>APDS score: ${(verdict.final_score * 100).toFixed(1)}% — combining URL, content, visual and AI-content signals.</p>
        ${
          topSignals.length
            ? `<ul>${topSignals.map((s) => `<li>${escapeHtml(String(s))}</li>`).join("")}</ul>`
            : ""
        }
        <div class="apds-actions">
          <button class="apds-primary" id="apds-go-back">Go Back (Safe)</button>
          <button class="apds-secondary" id="apds-report-fp">Report False Positive</button>
          ${isBlock ? `<button class="apds-ghost" id="apds-proceed">Proceed Anyway (unsafe)</button>` : ""}
        </div>
      </div>
    </div>
  `;
  shadow.appendChild(wrapper);

  shadow.getElementById("apds-go-back").addEventListener("click", () => {
    history.back();
    removeOverlay();
  });

  shadow.getElementById("apds-report-fp").addEventListener("click", () => {
    chrome.runtime.sendMessage({
      type: "APDS_REPORT_FEEDBACK",
      verdictId: verdict.task_id,
      label: "FALSE_POSITIVE",
    });
    removeOverlay();
  });

  const proceedBtn = shadow.getElementById("apds-proceed");
  if (proceedBtn) {
    proceedBtn.addEventListener("click", () => {
      // Per SRS §5.4: acknowledge risk, log event, add to user-override list
      removeOverlay();
    });
  }
}

function removeOverlay() {
  if (overlayHost) {
    overlayHost.remove();
    overlayHost = null;
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "APDS_BLOCK" || message.type === "APDS_WARN") {
    buildOverlay(message.verdict);
  }
  if (message.type === "APDS_ALLOW") {
    removeOverlay();
  }
});

// Form submission intercept (§5.3): warn if a form posts to a
// known Warn/Block domain that differs from the current page's domain.
document.addEventListener(
  "submit",
  async (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement) || !form.action) return;

    let actionUrl;
    try {
      actionUrl = new URL(form.action, location.href);
    } catch {
      return;
    }
    if (actionUrl.hostname === location.hostname) return;

    const cached = await chrome.runtime.sendMessage({
      type: "APDS_GET_CACHED_VERDICT",
      url: actionUrl.origin,
    });

    if (cached && (cached.verdict === "BLOCK" || cached.verdict === "WARN")) {
      const proceed = confirm(
        `APDS: This form submits to a site flagged as ${cached.verdict}. Continue anyway?`
      );
      if (!proceed) e.preventDefault();
    }
  },
  true
);
