(async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) return;

  const verdict = await chrome.runtime.sendMessage({
    type: "APDS_GET_CACHED_VERDICT",
    url: tab.url,
  });

  const verdictEl = document.getElementById("verdict");
  const scoreEl = document.getElementById("score");
  const signalEl = document.getElementById("signal");

  if (!verdict) {
    verdictEl.textContent = "SCANNING…";
    return;
  }

  verdictEl.textContent = verdict.verdict;
  verdictEl.className = `verdict ${verdict.verdict}`;
  scoreEl.textContent = `${(verdict.final_score * 100).toFixed(1)}%`;

  const signals = (verdict.explainability && verdict.explainability.top_signals) || [];
  signalEl.textContent = signals[0] || "None";
})();
