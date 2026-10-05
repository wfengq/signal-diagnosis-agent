function appendText(parent, tagName, value, className = "") {
  const element = document.createElement(tagName);
  element.textContent = String(value ?? "");
  if (className) element.className = className;
  parent.appendChild(element);
  return element;
}

const state = {
  caseId: null,
  revision: null,
  latestComparisonId: null,
  pendingRequestIds: new Set(),
  recommendationAvailable: false,
};

function newRequestId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, "").slice(0, 32);
  }
  return `req_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function setCaseStatus(message, className = "muted") {
  const node = document.getElementById("case-status");
  if (!node) return;
  node.textContent = message;
  node.className = className;
}

function setSubmitEnabled() {
  const submit = document.getElementById("submit-comparison");
  const repeat = document.getElementById("repeat-retest");
  const repair = document.getElementById("repair-retest");
  const recommend = document.getElementById("request-recommendation");
  const hasCase = Boolean(state.caseId);
  const busy = state.pendingRequestIds.size > 0;
  if (submit) submit.disabled = !hasCase || busy;
  if (repeat) repeat.disabled = !hasCase || !state.latestComparisonId || busy;
  if (repair) repair.disabled = !hasCase || !state.latestComparisonId || busy;
  if (recommend) {
    recommend.hidden = !state.recommendationAvailable;
    recommend.disabled =
      !state.recommendationAvailable ||
      !hasCase ||
      !state.latestComparisonId ||
      busy;
  }
}

function updateExportLinks() {
  const json = document.getElementById("export-json");
  const html = document.getElementById("export-html");
  if (!json || !html) return;
  if (!state.caseId) {
    json.hidden = true;
    html.hidden = true;
    json.removeAttribute("href");
    html.removeAttribute("href");
    return;
  }
  json.href = `/api/v1/regression/cases/${state.caseId}/report.json`;
  html.href = `/api/v1/regression/cases/${state.caseId}/report.html`;
  json.hidden = false;
  html.hidden = false;
}

async function apiJson(path, options = {}) {
  const response = await fetch(path, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch (_error) {
    payload = null;
  }
  if (!response.ok) {
    const message =
      payload && payload.error && payload.error.message
        ? payload.error.message
        : `request failed (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function readConditions() {
  return {
    intent: "preserve_behavior",
    baseline_version: document.getElementById("baseline-version").value.trim(),
    candidate_version: document.getElementById("candidate-version").value.trim(),
    stimulus_key: document.getElementById("stimulus-key").value.trim(),
    parameters_key: document.getElementById("parameters-key").value.trim(),
    same_input: document.getElementById("same-input").value,
    parameters_unchanged: document.getElementById("parameters-unchanged").value,
    aligned_ranges: document.getElementById("aligned-ranges").value,
    repeatability: document.getElementById("repeatability").value,
  };
}

function readSelection() {
  const channel = document.getElementById("analysis-channel").value;
  return {
    clipping: { channel, full_scale_threshold: 0.99 },
    harmonic: { channel },
  };
}

function readFullScaleDeclarations(forRepeat) {
  const periodic = document.getElementById("fs-periodic").value;
  if (!forRepeat) {
    return {
      periodic_test_signal: periodic,
      baseline_independent_render: "unknown",
      candidate_independent_render: "unknown",
    };
  }
  return {
    periodic_test_signal: periodic,
    baseline_independent_render: document.getElementById("fs-baseline-independent").value,
    candidate_independent_render: document.getElementById("fs-candidate-independent").value,
  };
}

function buildMetadata(requestId, link) {
  const conditions = readConditions();
  const forRepeat = Boolean(link && link.kind === "repeat");
  const metadata = {
    request_id: requestId,
    baseline_version: conditions.baseline_version,
    candidate_version: conditions.candidate_version,
    conditions,
    selection: readSelection(),
    link: link || null,
    full_scale_declarations: readFullScaleDeclarations(forRepeat),
  };
  return metadata;
}

async function readFileInput(id) {
  const input = document.getElementById(id);
  if (!input || !input.files || !input.files[0]) {
    throw new Error(`missing file for ${id}`);
  }
  const file = input.files[0];
  const buffer = await file.arrayBuffer();
  return { bytes: new Uint8Array(buffer), filename: file.name || `${id}.wav` };
}

async function submitComparison(link) {
  if (!state.caseId) {
    setCaseStatus("Start a case before uploading.", "warn");
    return;
  }
  const requestId = newRequestId();
  if (state.pendingRequestIds.has(requestId)) {
    return;
  }
  state.pendingRequestIds.add(requestId);
  setSubmitEnabled();
  const targetCaseId = state.caseId;
  try {
    const baseline = await readFileInput("baseline-file");
    const candidate = await readFileInput("candidate-file");
    const originalInput = document.getElementById("original-file");
    const form = new FormData();
    form.append(
      "baseline",
      new Blob([baseline.bytes], { type: "audio/wav" }),
      baseline.filename,
    );
    form.append(
      "candidate",
      new Blob([candidate.bytes], { type: "audio/wav" }),
      candidate.filename,
    );
    if (originalInput && originalInput.files && originalInput.files[0]) {
      const original = originalInput.files[0];
      const originalBytes = new Uint8Array(await original.arrayBuffer());
      form.append(
        "original",
        new Blob([originalBytes], { type: "audio/wav" }),
        original.name || "original.wav",
      );
    }
    const metadata = buildMetadata(requestId, link);
    form.append("metadata", JSON.stringify(metadata));
    const snapshot = await apiJson(
      `/api/v1/regression/cases/${targetCaseId}/comparisons`,
      { method: "POST", body: form },
    );
    if (snapshot.case_id !== targetCaseId || state.caseId !== targetCaseId) {
      return;
    }
    applySnapshot(snapshot);
  } catch (error) {
    if (error.status === 404) {
      state.caseId = null;
      state.revision = null;
      state.latestComparisonId = null;
      updateExportLinks();
      setCaseStatus(
        "This case is no longer available (service restarted or case deleted). Start a new case.",
        "warn",
      );
    } else {
      setCaseStatus(error.message || "Comparison failed.", "warn");
    }
  } finally {
    state.pendingRequestIds.delete(requestId);
    setSubmitEnabled();
  }
}

function renderResults(snapshot) {
  const root = document.getElementById("results-root");
  if (!root) return;
  root.replaceChildren();
  if (!snapshot.comparisons || !snapshot.comparisons.length) {
    appendText(root, "p", "No comparisons yet.", "muted");
    return;
  }
  if (snapshot.full_scale_checks && snapshot.full_scale_checks.length) {
    const fsBlock = document.createElement("section");
    appendText(fsBlock, "h3", "Full-scale check");
    snapshot.full_scale_checks.forEach((check, checkIndex) => {
      const title =
        checkIndex === snapshot.full_scale_checks.length - 1
          ? `Anchor ${check.anchor_comparison_id} (current)`
          : `Anchor ${check.anchor_comparison_id} (superseded)`;
      appendText(fsBlock, "h4", title);
      const list = document.createElement("ul");
      (check.lines || []).forEach((line) => {
        appendText(list, "li", line);
      });
      fsBlock.appendChild(list);
    });
    root.appendChild(fsBlock);
  }
  snapshot.comparisons.forEach((item, index) => {
    const block = document.createElement("article");
    appendText(block, "h3", `Comparison ${index + 1}: ${item.comparison_id}`);
    if (item.link_kind) {
      appendText(
        block,
        "p",
        `Linked ${item.link_kind} of ${item.parent_comparison_id}`,
        "muted",
      );
    }
    const record = item.record;
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["metric", "baseline", "candidate", "difference", "status", "reasons"].forEach(
      (label) => appendText(headRow, "th", label),
    );
    head.appendChild(headRow);
    table.appendChild(head);
    const body = document.createElement("tbody");
    (record.metric_comparisons || []).forEach((row) => {
      const tr = document.createElement("tr");
      appendText(tr, "td", row.metric);
      appendText(
        tr,
        "td",
        row.baseline_ref ? row.baseline_ref.value : "n/a",
      );
      appendText(
        tr,
        "td",
        row.candidate_ref ? row.candidate_ref.value : "n/a",
      );
      appendText(tr, "td", row.difference == null ? "n/a" : row.difference);
      appendText(tr, "td", row.status);
      appendText(
        tr,
        "td",
        Array.isArray(row.reason_codes) ? row.reason_codes.join(", ") : "",
      );
      body.appendChild(tr);
    });
    table.appendChild(body);
    block.appendChild(table);
    if (record.coverage && record.coverage.length) {
      appendText(block, "h4", "Coverage");
      const list = document.createElement("ul");
      record.coverage.forEach((entry) => {
        const text = entry.detail
          ? `${entry.check_id}: ${entry.status} (${entry.detail})`
          : `${entry.check_id}: ${entry.status}`;
        appendText(list, "li", text);
      });
      block.appendChild(list);
    }
    root.appendChild(block);
  });
  if (snapshot.failures && snapshot.failures.length) {
    appendText(root, "h3", "Failures");
    const list = document.createElement("ul");
    snapshot.failures.forEach((failure) => {
      appendText(list, "li", `${failure.request_id}: ${failure.message}`);
    });
    root.appendChild(list);
  }
  if (snapshot.recommendations && snapshot.recommendations.length) {
    appendText(root, "h3", "Retest recommendations");
    const list = document.createElement("ul");
    snapshot.recommendations.forEach((rec) => {
      const text = rec.detail
        ? `${rec.comparison_id}: ${rec.status} — ${rec.detail}`
        : `${rec.comparison_id}: ${rec.status}`;
      appendText(list, "li", text);
    });
    root.appendChild(list);
    const latest = snapshot.recommendations[snapshot.recommendations.length - 1];
    const statusNode = document.getElementById("recommendation-status");
    if (statusNode && latest) {
      statusNode.hidden = false;
      statusNode.textContent = `${latest.status}: ${latest.detail || ""}`.trim();
    }
  }
}

function applySnapshot(snapshot) {
  state.caseId = snapshot.case_id;
  state.revision = snapshot.revision;
  const comparisons = snapshot.comparisons || [];
  state.latestComparisonId = comparisons.length
    ? comparisons[comparisons.length - 1].comparison_id
    : null;
  setCaseStatus(
    `Case ${snapshot.case_id} (revision ${snapshot.revision}); latest submit ${snapshot.latest_submit_status}.`,
  );
  renderResults(snapshot);
  const recDetail = document.getElementById("recommendation-detail");
  if (recDetail) {
    const recommendations = snapshot.recommendations || [];
    const latest = recommendations.length
      ? recommendations[recommendations.length - 1]
      : null;
    recDetail.textContent = latest
      ? `${latest.status}: ${latest.detail || ""}`
      : "";
  }
  updateExportLinks();
  setSubmitEnabled();
}

async function requestRecommendation() {
  if (!state.caseId || !state.latestComparisonId || !state.recommendationAvailable) {
    return;
  }
  const requestId = newRequestId();
  if (state.pendingRequestIds.has(requestId)) {
    return;
  }
  state.pendingRequestIds.add(requestId);
  setSubmitEnabled();
  const targetCaseId = state.caseId;
  try {
    const snapshot = await apiJson(
      `/api/v1/regression/cases/${state.caseId}/comparisons/${state.latestComparisonId}/recommendations`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: requestId }),
      },
    );
    if (state.caseId !== targetCaseId) {
      return;
    }
    applySnapshot(snapshot);
  } catch (error) {
    setCaseStatus(error.message || "Recommendation request failed.", "warn");
  } finally {
    state.pendingRequestIds.delete(requestId);
    setSubmitEnabled();
  }
}

async function createCase() {
  const goal = document.getElementById("case-goal").value.trim();
  if (!goal) {
    setCaseStatus("Enter a goal before starting a case.", "warn");
    return;
  }
  const requestId = newRequestId();
  if (state.pendingRequestIds.has(requestId)) {
    return;
  }
  state.pendingRequestIds.add(requestId);
  setSubmitEnabled();
  try {
    const snapshot = await apiJson("/api/v1/regression/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, request_id: requestId }),
    });
    applySnapshot(snapshot);
  } catch (error) {
    setCaseStatus(error.message || "Could not create case.", "warn");
  } finally {
    state.pendingRequestIds.delete(requestId);
    setSubmitEnabled();
  }
}

async function loadCapabilities() {
  try {
    const caps = await apiJson("/api/v1/regression/capabilities");
    state.recommendationAvailable = Boolean(caps && caps.recommendation_available);
    const notice = document.getElementById("measurement-notice");
    if (notice && caps && caps.enabled_profile_ids && caps.enabled_profile_ids.length) {
      notice.textContent = `Enabled comparison profiles: ${caps.enabled_profile_ids.join(", ")}`;
    }
    setSubmitEnabled();
  } catch (_error) {
    setCaseStatus("Regression API unavailable.", "warn");
  }
}

function bindUi() {
  const create = document.getElementById("create-case");
  const submit = document.getElementById("submit-comparison");
  const repeat = document.getElementById("repeat-retest");
  const repair = document.getElementById("repair-retest");
  const recommend = document.getElementById("request-recommendation");
  if (create) create.addEventListener("click", () => createCase());
  if (submit) submit.addEventListener("click", () => submitComparison(null));
  if (recommend) {
    recommend.addEventListener("click", () => requestRecommendation());
  }
  if (repeat) {
    repeat.addEventListener("click", () =>
      submitComparison({
        kind: "repeat",
        parent_comparison_id: state.latestComparisonId,
      }),
    );
  }
  if (repair) {
    repair.addEventListener("click", () =>
      submitComparison({
        kind: "repair",
        parent_comparison_id: state.latestComparisonId,
      }),
    );
  }
  setSubmitEnabled();
  updateExportLinks();
  loadCapabilities();
}

document.addEventListener("DOMContentLoaded", bindUi);
