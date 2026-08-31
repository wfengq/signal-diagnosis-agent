function appendText(parent, tagName, value, className = "") {
  const element = document.createElement(tagName);
  element.textContent = String(value ?? "");
  if (className) element.className = className;
  parent.appendChild(element);
  return element;
}

function clearPanel(panel, heading) {
  panel.replaceChildren();
  appendText(panel, "h2", heading);
}

function metricText(metric) {
  if (metric && typeof metric === "object" && "value" in metric) {
    return String(metric.value);
  }
  return String(metric ?? "");
}

function refsText(refs) {
  return Array.isArray(refs) && refs.length ? refs.join(", ") : "none";
}

async function apiJson(path) {
  const response = await fetch(path);
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
    error.payload = payload;
    throw error;
  }
  return payload;
}

function renderLifecycle(status) {
  const panel = document.getElementById("lifecycle-panel");
  panel.replaceChildren();
  appendText(panel, "h2", "Lifecycle");
  appendText(panel, "p", status, "lifecycle-status");
  if (status === "queued" || status === "running") {
    appendText(panel, "p", "elapsed", "lifecycle-elapsed");
  }
}

function renderPreview(parent, preview) {
  appendText(parent, "p", preview.label || "visualization_only", "muted");
  appendText(
    parent,
    "p",
    `${preview.points.length} preview points from ${preview.original_num_samples} samples at ${preview.sample_rate_hz} Hz`,
    "muted",
  );
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", "0 0 1000 200");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Waveform preview");
  const polyline = document.createElementNS(svgNS, "polyline");
  const count = preview.points.length;
  const coords = preview.points.map((point, index) => {
    const x = count <= 1 ? 0 : (index / (count - 1)) * 1000;
    const y = 100 - Number(point.amplitude) * 90;
    return `${x},${y}`;
  });
  polyline.setAttribute("points", coords.join(" "));
  polyline.setAttribute("fill", "none");
  polyline.setAttribute("stroke", "currentColor");
  polyline.setAttribute("stroke-width", "1.5");
  svg.appendChild(polyline);
  parent.appendChild(svg);
}

function renderDiagnosis(panel, snapshot) {
  const result = snapshot.result;
  if (snapshot.status === "failed" && snapshot.application_error) {
    appendText(panel, "p", snapshot.application_error.code);
    appendText(panel, "p", snapshot.application_error.message);
    return;
  }
  if (!result) {
    appendText(panel, "p", "No diagnosis result.");
    return;
  }
  const diagnosis = result.diagnosis;
  appendText(panel, "p", `Agent status: ${result.status}`);
  appendText(panel, "p", `Termination: ${result.termination_reason}`);
  if (diagnosis) {
    appendText(panel, "p", `Outcome: ${diagnosis.outcome}`);
    appendText(panel, "p", `Confidence: ${diagnosis.confidence_label}`);
    for (const claim of diagnosis.claims || []) {
      const article = appendText(panel, "article", "");
      appendText(article, "h3", claim.claim_id);
      appendText(article, "p", claim.statement);
      appendText(article, "p", `fault: ${claim.fault_type}`);
      appendText(article, "p", `evidence: ${refsText(claim.evidence_refs)}`);
      appendText(article, "p", `rules: ${refsText(claim.rule_refs)}`);
      appendText(article, "p", `knowledge: ${refsText(claim.knowledge_refs)}`);
    }
    for (const limitation of diagnosis.limitations || []) {
      appendText(panel, "p", `limitation: ${limitation}`);
    }
  }
  for (const warning of result.warnings || []) {
    appendText(panel, "p", `warning: ${warning}`);
  }
  for (const error of result.errors || []) {
    appendText(panel, "p", `error: ${error}`);
  }
}

function renderTrace(panel, events) {
  if (!events.length) {
    appendText(panel, "p", "No trace events.");
    return;
  }
  for (const event of events) {
    const article = appendText(panel, "article", "");
    appendText(
      article,
      "p",
      `${event.event_index} ${event.kind} ${event.action_name} ${event.status}`,
    );
    if (event.purpose) {
      appendText(article, "p", event.purpose);
    }
    appendText(article, "p", `refs: ${refsText(event.reference_ids)}`);
  }
}

function renderObservations(panel, observations) {
  if (!observations.length) {
    appendText(panel, "p", "No observations.");
    return;
  }
  for (const item of observations) {
    const article = appendText(panel, "article", "");
    appendText(
      article,
      "p",
      `${item.observation_id} ${item.tool_name} ${item.status}`,
    );
    appendText(article, "p", item.purpose || "");
    appendText(article, "p", `evidence: ${refsText(item.evidence_refs)}`);
    if (item.error_message) {
      appendText(article, "p", item.error_message);
    }
  }
}

function renderEvidence(panel, evidence) {
  if (!evidence.length) {
    appendText(panel, "p", "No evidence.");
    return;
  }
  for (const item of evidence) {
    const article = appendText(panel, "article", "");
    appendText(
      article,
      "p",
      `${item.evidence_id} ${item.metric} ${item.value} ${item.validity}`,
    );
    if (item.unit) {
      appendText(article, "p", item.unit);
    }
  }
}

function renderRules(panel, batches) {
  if (!batches.length) {
    appendText(panel, "p", "No rule evaluations.");
    return;
  }
  for (const batch of batches) {
    for (const item of batch.evaluations || []) {
      const article = appendText(panel, "article", "");
      appendText(
        article,
        "p",
        `${item.evaluation_id} ${item.profile_id} ${item.profile_version} ${item.judgment}`,
      );
      if (item.reason) {
        appendText(article, "p", item.reason);
      }
    }
  }
}

function renderKnowledge(panel, retrievals) {
  if (!retrievals.length) {
    appendText(panel, "p", "No knowledge retrievals.");
    return;
  }
  for (const retrieval of retrievals) {
    const article = appendText(panel, "article", "");
    appendText(article, "p", retrieval.retrieval_id);
    appendText(article, "p", retrieval.query_text || "");
    for (const chunk of retrieval.chunks || []) {
      appendText(article, "p", chunk.excerpt);
    }
  }
}

function renderTerminal(snapshot) {
  const diagnosisPanel = document.getElementById("diagnosis-panel");
  const waveformPanel = document.getElementById("waveform-panel");
  const tracePanel = document.getElementById("trace-panel");
  const evidencePanel = document.getElementById("evidence-panel");
  const rulesPanel = document.getElementById("rules-panel");
  const knowledgePanel = document.getElementById("knowledge-panel");
  clearPanel(diagnosisPanel, "Diagnosis");
  clearPanel(waveformPanel, "Waveform preview");
  clearPanel(tracePanel, "Trace");
  clearPanel(evidencePanel, "Evidence");
  clearPanel(rulesPanel, "Rules");
  clearPanel(knowledgePanel, "Knowledge");

  renderDiagnosis(diagnosisPanel, snapshot);
  if (snapshot.waveform_preview) {
    renderPreview(waveformPanel, snapshot.waveform_preview);
  }
  const result = snapshot.result || {};
  renderTrace(tracePanel, snapshot.trace_events || []);
  appendText(tracePanel, "h3", "Observations");
  renderObservations(tracePanel, result.observations || []);
  renderEvidence(evidencePanel, result.evidence || []);
  renderRules(rulesPanel, result.rule_evaluation_batches || []);
  renderKnowledge(knowledgePanel, result.knowledge_retrievals || []);

  const jsonLink = document.getElementById("report-json");
  const htmlLink = document.getElementById("report-html");
  if (snapshot.status === "completed") {
    const runId = encodeURIComponent(snapshot.run_id);
    jsonLink.setAttribute("href", `/api/v1/runs/${runId}/report.json`);
    htmlLink.setAttribute("href", `/api/v1/runs/${runId}/report.html`);
    jsonLink.hidden = false;
    htmlLink.hidden = false;
  } else {
    jsonLink.removeAttribute("href");
    htmlLink.removeAttribute("href");
    jsonLink.hidden = true;
    htmlLink.hidden = true;
  }
}

async function pollRun(runId) {
  for (;;) {
    const snapshot = await apiJson(`/api/v1/runs/${encodeURIComponent(runId)}`);
    renderLifecycle(snapshot.status);
    if (snapshot.status === "completed" || snapshot.status === "failed") {
      renderTerminal(snapshot);
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 500));
  }
}

function renderEvaluation(summary) {
  const panel = document.getElementById("evaluation-panel");
  panel.replaceChildren();
  appendText(panel, "h2", "Accepted evaluation");
  appendText(panel, "p", `${summary.benchmark_status}/${summary.target_status}`);
  appendText(panel, "p", `${summary.agent_slot_count} held-out Agent slots`);
  appendText(
    panel,
    "p",
    `Agent causal_macro_f1 ${summary.agent_metrics.causal_macro_f1} vs target ${summary.targets.causal_macro_f1_min} vs fixed ${summary.baseline_metrics.causal_macro_f1}`,
  );
  appendText(
    panel,
    "p",
    `Agent outcome_accuracy ${metricText(summary.agent_metrics.outcome_accuracy)} vs fixed ${metricText(summary.baseline_metrics.outcome_accuracy)}`,
  );
  appendText(
    panel,
    "p",
    `${summary.behavioral_failure_slot_count}/${summary.agent_slot_count} behavioral-failure slots`,
  );
  appendText(
    panel,
    "p",
    `${summary.outcome_error_slot_count}/${summary.agent_slot_count} outcome error`,
  );
  appendText(panel, "p", String(summary.disclaimer).replaceAll("_", " "));
  appendText(
    panel,
    "p",
    "V0.2 demonstration targets are not industry standards or SLAs.",
  );
}

async function loadEvaluation() {
  const summary = await apiJson("/api/v1/evaluation-summary");
  renderEvaluation(summary);
}

async function loadPresets() {
  const presets = await apiJson("/api/v1/presets");
  const select = document.getElementById("preset-id");
  select.replaceChildren();
  for (const item of presets) {
    const option = appendText(select, "option", item.label);
    option.value = item.preset_id;
  }
}

function selectedMode() {
  const checked = document.querySelector('input[name="source-mode"]:checked');
  return checked ? checked.value : "wav";
}

function showError(message) {
  const panel = document.getElementById("lifecycle-panel");
  panel.replaceChildren();
  appendText(panel, "h2", "Lifecycle");
  appendText(panel, "p", message);
}

async function submitDiagnose(event) {
  event.preventDefault();
  const question = document.getElementById("question").value;
  const channel = document.getElementById("channel").value;
  const submit = document.getElementById("submit-run");
  submit.disabled = true;
  document.getElementById("report-json").hidden = true;
  document.getElementById("report-html").hidden = true;
  try {
    let submission;
    if (selectedMode() === "preset") {
      submission = await fetch("/api/v1/runs/synthetic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preset_id: document.getElementById("preset-id").value,
          user_request: question,
          channel,
        }),
      }).then(async (response) => {
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(
            payload && payload.error && payload.error.message
              ? payload.error.message
              : `request failed (${response.status})`,
          );
        }
        return payload;
      });
    } else {
      const fileInput = document.getElementById("wav-file");
      if (!fileInput.files || !fileInput.files[0]) {
        throw new Error("Choose a WAV file before submitting.");
      }
      const body = new FormData();
      body.append("file", fileInput.files[0]);
      body.append("user_request", question);
      body.append("channel", channel);
      submission = await fetch("/api/v1/runs/wav", {
        method: "POST",
        body,
      }).then(async (response) => {
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(
            payload && payload.error && payload.error.message
              ? payload.error.message
              : `request failed (${response.status})`,
          );
        }
        return payload;
      });
    }
    renderLifecycle(submission.status);
    await pollRun(submission.run_id);
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    submit.disabled = false;
  }
}

function bindUi() {
  document.getElementById("diagnose-form").addEventListener("submit", submitDiagnose);
  loadPresets().catch((error) => {
    showError(error instanceof Error ? error.message : String(error));
  });
  loadEvaluation().catch((error) => {
    showError(error instanceof Error ? error.message : String(error));
  });
}

bindUi();
