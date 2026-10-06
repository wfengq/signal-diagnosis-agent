function appendText(parent, tagName, value, className = "") {
  const element = document.createElement(tagName);
  element.textContent = String(value ?? "");
  if (className) element.className = className;
  parent.appendChild(element);
  return element;
}

/** When false, submit-run stays disabled (planner health gate). */
let plannerHealthAllowsSubmit = false;

/** Client-held test WAV for D037 upgrade resubmits (cleared on reload). */
const heldTestSignal = {
  blob: null,
  filename: null,
  channel: null,
  userRequest: null,
};

function clearHeldTestSignal() {
  heldTestSignal.blob = null;
  heldTestSignal.filename = null;
  heldTestSignal.channel = null;
  heldTestSignal.userRequest = null;
}

function rememberHeldTestSignal({ blob, filename, channel, userRequest }) {
  heldTestSignal.blob = blob;
  heldTestSignal.filename = filename;
  heldTestSignal.channel = channel;
  heldTestSignal.userRequest = userRequest;
}

function setUpgradeControlsVisible(visible) {
  const controls = document.getElementById("upgrade-controls");
  if (!controls) return;
  controls.hidden = !visible;
  if (!visible) {
    const hz = document.getElementById("upgrade-nominal-hz");
    if (hz) hz.value = "";
    const ref = document.getElementById("upgrade-reference-file");
    if (ref) ref.value = "";
  }
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

const QUALIFICATION_METRICS = new Set([
  "context_valid",
  "mode",
  "algorithm_version",
  "invalid_reason",
  "test_f0_hz",
  "comparison_f0_hz",
  "f0_relative_delta",
  "alignment_lag_samples",
  "alignment_correlation",
  "gain_ratio",
]);

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

function setSubmitRunEnabled() {
  const submit = document.getElementById("submit-run");
  if (submit) submit.disabled = !plannerHealthAllowsSubmit;
}

function renderPlannerReadiness(health) {
  const panel = document.getElementById("lifecycle-panel");
  panel.replaceChildren();
  appendText(panel, "h2", "运行状态");
  const identity = health && health.planner_identity ? health.planner_identity : {};
  if (health && health.planner_configured) {
    appendText(
      panel,
      "p",
      `诊断模型已就绪（${identity.provider} / ${identity.model} / ${identity.prompt_version}）。`,
      "planner-readiness",
    );
  } else {
    appendText(
      panel,
      "p",
      `诊断需要配置 RealLLMPlanner（设置环境变量 ${"DEEPSEEK_" + "API" + "_KEY"}）。应用不会回退到 ScriptedPlanner。`,
      "planner-readiness",
    );
  }
  appendText(panel, "p", "还没有运行。", "muted");
}

function renderPlannerHealthFailure() {
  const panel = document.getElementById("lifecycle-panel");
  panel.replaceChildren();
  appendText(panel, "h2", "运行状态");
  appendText(
    panel,
    "p",
    "无法从 /api/v1/health 读取诊断模型状态。",
    "planner-readiness",
  );
  appendText(panel, "p", "还没有运行。", "muted");
}

const LIFECYCLE_LABELS = {
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
};

function renderLifecycle(status) {
  const panel = document.getElementById("lifecycle-panel");
  panel.replaceChildren();
  appendText(panel, "h2", "运行状态");
  appendText(
    panel,
    "p",
    `${LIFECYCLE_LABELS[status] || status}（${status}）`,
    `lifecycle-status status-${status}`,
  );
  if (status === "queued" || status === "running") {
    appendText(panel, "p", "请稍候，计时中（elapsed）", "lifecycle-elapsed");
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
    appendText(panel, "p", "没有诊断结果。");
    return;
  }
  const diagnosis = result.diagnosis;
  appendText(panel, "p", `Agent 状态：${result.status}`);
  appendText(panel, "p", `结束原因：${result.termination_reason}`);
  if (diagnosis) {
    appendText(panel, "p", `结论：${outcomeLabel(diagnosis.outcome)}`);
    appendText(panel, "p", `置信度：${confidenceLabel(diagnosis.confidence_label)}`);
    for (const claim of diagnosis.claims || []) {
      const article = appendText(panel, "article", "");
      appendText(article, "h3", claim.claim_id);
      appendText(article, "p", claim.statement);
      appendText(article, "p", `故障类型（fault）：${claim.fault_type}`);
      appendText(article, "p", `证据（evidence）：${refsText(claim.evidence_refs)}`);
      appendText(article, "p", `规则（rules）：${refsText(claim.rule_refs)}`);
      appendText(article, "p", `知识（knowledge）：${refsText(claim.knowledge_refs)}`);
    }
  }
  for (const warning of result.warnings || []) {
    appendText(panel, "p", `warning: ${warning}`);
  }
  for (const error of result.errors || []) {
    appendText(panel, "p", `error: ${error}`);
  }
}

function renderDeclaration(panel, snapshot) {
  const context = snapshot.stimulus_context;
  if (!context) {
    appendText(panel, "p", "本次运行没有声明的激励上下文。");
    return;
  }
  appendText(panel, "p", `mode: ${context.mode}`);
  appendText(panel, "p", `assertion_source: ${context.assertion_source}`);
  appendText(panel, "p", `test_signal_id: ${context.test_signal_id}`);
  if (context.reference_signal_id) {
    appendText(panel, "p", `reference_signal_id: ${context.reference_signal_id}`);
  }
  if (context.nominal_fundamental_hz != null) {
    appendText(panel, "p", `nominal_fundamental_hz: ${context.nominal_fundamental_hz}`);
  }
  if (context.stimulus_kind) {
    appendText(panel, "p", `stimulus_kind: ${context.stimulus_kind}`);
  }
  if (snapshot.context_origin === "intake_confirmed") {
    appendText(panel, "p", "上下文来源：文字草稿，经用户确认（free-text draft, confirmed by the user）");
  }
  appendText(
    panel,
    "p",
    "StimulusContext is declared provenance, not measured Evidence.",
    "muted",
  );
}

function renderQualification(panel, evidence) {
  const items = (evidence || []).filter((item) =>
    QUALIFICATION_METRICS.has(item.metric),
  );
  if (!items.length) {
    appendText(panel, "p", "没有比较资格证据。");
    return;
  }
  for (const item of items) {
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

const DIAGNOSTIC_MODE_LABELS = {
  single_signal: "未知单文件信号（Unknown one-WAV signal）",
  nominal_single_tone: "声明单音（Declared single tone）",
  paired_reference: "与干净参考对比（Compare with clean reference）",
};

const OUTCOME_LABELS = {
  supported_fault: "发现有证据支持的故障",
  no_supported_fault: "未发现有证据支持的故障",
  inconclusive: "无法下结论",
};

const CONFIDENCE_LABELS = { low: "低", medium: "中", high: "高" };

function outcomeLabel(outcome) {
  return OUTCOME_LABELS[outcome] ? `${OUTCOME_LABELS[outcome]}（${outcome}）` : outcome;
}

function confidenceLabel(label) {
  return CONFIDENCE_LABELS[label] ? `${CONFIDENCE_LABELS[label]}（${label}）` : label;
}

function diagnosticModeLabel(modeName) {
  return DIAGNOSTIC_MODE_LABELS[modeName] || modeName;
}

function humanizeRequiredInputToken(token) {
  if (token === "reference_wav") {
    return "reference WAV";
  }
  if (token === "nominal_fundamental_hz") {
    return "nominal fundamental (Hz)";
  }
  const eq = token.indexOf("=");
  if (eq >= 0) {
    const key = token.slice(0, eq);
    const value = token.slice(eq + 1);
    if (key === "stimulus_kind" && value === "single_tone") {
      return "stimulus kind single tone";
    }
    return `${key.replace(/_/g, " ")} ${value.replace(/_/g, " ")}`;
  }
  return token.replace(/_/g, " ");
}

function renderGuidance(panel, snapshot) {
  const guidance = snapshot.context_guidance;
  const controls = document.getElementById("upgrade-controls");
  if (!guidance) {
    appendText(panel, "p", "本次运行没有上下文升级建议。");
    setUpgradeControlsVisible(false);
    if (controls) panel.appendChild(controls);
    return;
  }
  appendText(panel, "p", guidance.summary);
  const unlockable = (guidance.unlockable_modes || [])
    .map(diagnosticModeLabel)
    .join(", ");
  if (unlockable) {
    appendText(panel, "p", `可选升级（Optional upgrades: ${unlockable}）`);
  }
  const required = guidance.required_inputs || {};
  for (const modeName of Object.keys(required)) {
    const inputs = required[modeName] || [];
    const humanInputs = inputs.map(humanizeRequiredInputToken).join(", ");
    appendText(
      panel,
      "p",
      `${diagnosticModeLabel(modeName)}: ${humanInputs}`,
    );
  }
  const facts = guidance.observed_facts || [];
  if (facts.length) {
    appendText(panel, "p", "已观测到的事实（observed_facts）：");
    const list = document.createElement("ul");
    list.id = "observed-facts";
    panel.appendChild(list);
    for (const fact of facts) {
      const unit = fact.unit;
      const unitSuffix =
        unit === null || unit === undefined || unit === "" ? "" : ` ${unit}`;
      const line = `${fact.evidence_id} ${fact.metric}=${fact.value}${unitSuffix}`;
      appendText(list, "li", line);
    }
  }
  appendText(
    panel,
    "p",
    "升级需要你提供参考 WAV 或声明 nominal_fundamental_hz；不会用测得的基频自动填写。",
    "muted",
  );
  setUpgradeControlsVisible(Boolean(heldTestSignal.blob));
  if (controls) {
    panel.appendChild(controls);
  }
}

function renderLimitations(panel, snapshot) {
  const diagnosis = snapshot.result && snapshot.result.diagnosis;
  const limitations = (diagnosis && diagnosis.limitations) || [];
  if (!limitations.length) {
    appendText(panel, "p", "没有记录因果限制。");
    return;
  }
  for (const item of limitations) {
    appendText(panel, "p", item);
  }
}

function renderTrace(panel, events) {
  if (!events.length) {
    appendText(panel, "p", "没有轨迹事件。");
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
    appendText(article, "p", `引用（refs）：${refsText(event.reference_ids)}`);
  }
}

function renderObservations(panel, observations) {
  if (!observations.length) {
    appendText(panel, "p", "没有观测记录。");
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
  const items = (evidence || []).filter(
    (item) => !QUALIFICATION_METRICS.has(item.metric),
  );
  if (!items.length) {
    appendText(panel, "p", "没有证据。");
    return;
  }
  for (const item of items) {
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
    appendText(panel, "p", "没有规则判定。");
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
    appendText(panel, "p", "没有知识引用。");
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

function isContextualSnapshot(snapshot) {
  return Boolean(snapshot && snapshot.stimulus_context);
}

function setTechPanelVisible(panelId, visible) {
  const wrapper = document.getElementById(panelId).closest("details");
  if (wrapper) wrapper.hidden = !visible;
}

function renderSummary(snapshot) {
  const card = document.getElementById("summary-card");
  const body = document.getElementById("summary-body");
  body.replaceChildren();
  card.hidden = false;
  if (snapshot.status === "failed" && snapshot.application_error) {
    appendText(body, "p", "诊断没有完成", "summary-outcome outcome-error");
    appendText(body, "p", `${snapshot.application_error.code}: ${snapshot.application_error.message}`);
    return;
  }
  const result = snapshot.result || {};
  const diagnosis = result.diagnosis;
  const list = document.createElement("dl");
  list.className = "summary-facts";
  body.appendChild(list);
  const fact = (term, value) => {
    appendText(list, "dt", term);
    appendText(list, "dd", value);
  };
  if (diagnosis) {
    appendText(
      body,
      "p",
      outcomeLabel(diagnosis.outcome),
      `summary-outcome outcome-${diagnosis.outcome}`,
    );
    body.insertBefore(body.lastChild, list);
    fact("置信度", confidenceLabel(diagnosis.confidence_label));
  } else {
    appendText(body, "p", `Agent 没有给出诊断（${result.status || "error"}）`, "summary-outcome outcome-error");
    body.insertBefore(body.lastChild, list);
    fact("结束原因", String(result.termination_reason || ""));
  }
  const context = snapshot.stimulus_context;
  if (context) {
    fact("诊断模式", diagnosticModeLabel(context.mode));
    if (context.nominal_fundamental_hz != null) {
      fact("标称基频", `${context.nominal_fundamental_hz} Hz`);
    }
  }
  if (snapshot.context_origin === "intake_confirmed") {
    fact("上下文来源", "文字草稿，经用户确认");
  }
  const claims = (diagnosis && diagnosis.claims) || [];
  if (claims.length) {
    appendText(body, "p", claims[0].statement, "summary-claim");
  }
}

function renderTerminal(snapshot) {
  const diagnosisPanel = document.getElementById("diagnosis-panel");
  const guidancePanel = document.getElementById("guidance-panel");
  const declarationPanel = document.getElementById("declaration-panel");
  const qualificationPanel = document.getElementById("qualification-panel");
  const limitationPanel = document.getElementById("limitation-panel");
  const waveformPanel = document.getElementById("waveform-panel");
  const tracePanel = document.getElementById("trace-panel");
  const evidencePanel = document.getElementById("evidence-panel");
  const rulesPanel = document.getElementById("rules-panel");
  const knowledgePanel = document.getElementById("knowledge-panel");
  const upgradeControls = document.getElementById("upgrade-controls");
  if (upgradeControls) {
    upgradeControls.remove();
  }
  clearPanel(diagnosisPanel, "诊断详情");
  clearPanel(guidancePanel, "上下文升级建议");
  clearPanel(declarationPanel, "声明的上下文");
  clearPanel(qualificationPanel, "比较资格");
  clearPanel(limitationPanel, "因果限制");
  clearPanel(waveformPanel, "波形预览");
  clearPanel(tracePanel, "运行轨迹");
  clearPanel(evidencePanel, "证据");
  clearPanel(rulesPanel, "规则判定");
  clearPanel(knowledgePanel, "知识引用");
  if (upgradeControls) {
    guidancePanel.appendChild(upgradeControls);
  }

  renderSummary(snapshot);
  renderDiagnosis(diagnosisPanel, snapshot);
  renderGuidance(guidancePanel, snapshot);
  const result = snapshot.result || {};
  const evidence = result.evidence || [];
  const diagnosis = result.diagnosis;
  const limitations = (diagnosis && diagnosis.limitations) || [];
  const contextual = isContextualSnapshot(snapshot);
  if (contextual) {
    renderDeclaration(declarationPanel, snapshot);
    renderQualification(qualificationPanel, evidence);
    renderLimitations(limitationPanel, snapshot);
  } else {
    appendText(declarationPanel, "p", "旧版 V0.2 单文件运行不适用。");
    appendText(qualificationPanel, "p", "旧版 V0.2 单文件运行不适用。");
    if (limitations.length) {
      for (const item of limitations) {
        appendText(limitationPanel, "p", item);
      }
    } else {
      appendText(limitationPanel, "p", "没有记录因果限制。");
    }
  }

  const preview = snapshot.test_preview || snapshot.waveform_preview;
  if (preview) {
    renderPreview(waveformPanel, preview);
  }
  const traceEvents = snapshot.trace_events || [];
  const observations = result.observations || [];
  const batches = result.rule_evaluation_batches || [];
  const retrievals = result.knowledge_retrievals || [];
  renderTrace(tracePanel, traceEvents);
  appendText(tracePanel, "h3", "观测记录（Observations）");
  renderObservations(tracePanel, observations);
  renderEvidence(evidencePanel, evidence);
  renderRules(rulesPanel, batches);
  renderKnowledge(knowledgePanel, retrievals);

  // Technical panels with nothing to show for this run stay hidden.
  setTechPanelVisible("declaration-panel", contextual);
  setTechPanelVisible(
    "qualification-panel",
    contextual && evidence.some((item) => QUALIFICATION_METRICS.has(item.metric)),
  );
  setTechPanelVisible("limitation-panel", limitations.length > 0);
  setTechPanelVisible("waveform-panel", Boolean(preview));
  setTechPanelVisible("trace-panel", traceEvents.length + observations.length > 0);
  setTechPanelVisible(
    "evidence-panel",
    evidence.some((item) => !QUALIFICATION_METRICS.has(item.metric)),
  );
  setTechPanelVisible(
    "rules-panel",
    batches.some((batch) => (batch.evaluations || []).length > 0),
  );
  setTechPanelVisible("knowledge-panel", retrievals.length > 0);
  document.getElementById("tech-panels").hidden = false;

  const jsonLink = document.getElementById("report-json");
  const htmlLink = document.getElementById("report-html");
  if (snapshot.status === "completed") {
    const runId = encodeURIComponent(snapshot.run_id);
    const base = isContextualSnapshot(snapshot)
      ? `/api/v1/contextual-runs/${runId}`
      : `/api/v1/runs/${runId}`;
    jsonLink.setAttribute("href", `${base}/report.json`);
    htmlLink.setAttribute("href", `${base}/report.html`);
    jsonLink.hidden = false;
    htmlLink.hidden = false;
  } else {
    jsonLink.removeAttribute("href");
    htmlLink.removeAttribute("href");
    jsonLink.hidden = true;
    htmlLink.hidden = true;
  }
}

async function pollRun(runId, options) {
  const contextual = Boolean(options && options.contextual);
  const pathBase = contextual
    ? `/api/v1/contextual-runs/${encodeURIComponent(runId)}`
    : `/api/v1/runs/${encodeURIComponent(runId)}`;
  for (;;) {
    const snapshot = await apiJson(pathBase);
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

async function loadPlannerHealth() {
  try {
    const health = await apiJson("/api/v1/health");
    plannerHealthAllowsSubmit = Boolean(health.planner_configured);
    renderPlannerReadiness(health);
  } catch (_error) {
    plannerHealthAllowsSubmit = false;
    renderPlannerHealthFailure();
  }
  setSubmitRunEnabled();
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

function selectedDiagnosticMode() {
  const select = document.getElementById("diagnostic-mode");
  return select ? select.value : "single_signal";
}

function updateContextualFields() {
  const mode = selectedDiagnosticMode();
  const nominal = document.getElementById("nominal-fields");
  const reference = document.getElementById("reference-fields");
  const sourceIsWav = selectedMode() === "wav";
  const showNominal = sourceIsWav && mode === "nominal_single_tone";
  const showReference = sourceIsWav && mode === "paired_reference";
  nominal.hidden = !showNominal;
  reference.hidden = !showReference;
}

function showError(message) {
  const panel = document.getElementById("lifecycle-panel");
  panel.replaceChildren();
  appendText(panel, "h2", "运行状态");
  appendText(panel, "p", message, "lifecycle-error");
}

async function parseJsonResponse(response) {
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(
      payload && payload.error && payload.error.message
        ? payload.error.message
        : `request failed (${response.status})`,
    );
  }
  return payload;
}

async function fetchPresetWavBlob(presetId) {
  const response = await fetch(`/api/v1/presets/${encodeURIComponent(presetId)}/wav`);
  if (!response.ok) {
    let payload = null;
    try {
      payload = await response.json();
    } catch (_error) {
      payload = null;
    }
    throw new Error(
      payload && payload.error && payload.error.message
        ? payload.error.message
        : `preset wav request failed (${response.status})`,
    );
  }
  return response.blob();
}

async function postContextualWav(body) {
  return fetch("/api/v1/contextual-runs/wav", {
    method: "POST",
    body,
  }).then(parseJsonResponse);
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
    let testBlob;
    let testFilename;
    let diagnosticMode;
    if (selectedMode() === "preset") {
      const presetId = document.getElementById("preset-id").value;
      testBlob = await fetchPresetWavBlob(presetId);
      testFilename = "input.wav";
      diagnosticMode = "single_signal";
    } else {
      const fileInput = document.getElementById("wav-file");
      if (!fileInput.files || !fileInput.files[0]) {
        throw new Error("请先选择一个 WAV 文件。");
      }
      testBlob = fileInput.files[0];
      testFilename = fileInput.files[0].name || "input.wav";
      diagnosticMode = selectedDiagnosticMode();
    }
    rememberHeldTestSignal({
      blob: testBlob,
      filename: testFilename,
      channel,
      userRequest: question,
    });
    const body = new FormData();
    body.append("test_file", testBlob, testFilename);
    body.append("mode", diagnosticMode);
    body.append("user_request", question);
    body.append("channel", channel);
    if (diagnosticMode === "nominal_single_tone") {
      body.append("stimulus_kind", "single_tone");
      body.append(
        "nominal_fundamental_hz",
        document.getElementById("nominal-fundamental-hz").value,
      );
    } else if (diagnosticMode === "paired_reference") {
      const referenceInput = document.getElementById("reference-file");
      if (!referenceInput.files || !referenceInput.files[0]) {
        throw new Error("请先选择参考 WAV。");
      }
      body.append("reference_file", referenceInput.files[0]);
    }
    const submission = await postContextualWav(body);
    renderLifecycle(submission.status);
    await pollRun(submission.run_id, { contextual: true });
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    setSubmitRunEnabled();
  }
}

async function submitUpgradePaired() {
  if (!heldTestSignal.blob) {
    throw new Error("没有可重新提交的待测 WAV。");
  }
  const referenceInput = document.getElementById("upgrade-reference-file");
  if (!referenceInput.files || !referenceInput.files[0]) {
    throw new Error("请先选择参考 WAV。");
  }
  const body = new FormData();
  body.append("test_file", heldTestSignal.blob, heldTestSignal.filename || "input.wav");
  body.append("mode", "paired_reference");
  body.append("user_request", heldTestSignal.userRequest || "");
  body.append("channel", heldTestSignal.channel || "mixdown");
  body.append("reference_file", referenceInput.files[0]);
  const submission = await postContextualWav(body);
  renderLifecycle(submission.status);
  await pollRun(submission.run_id, { contextual: true });
}

async function submitUpgradeNominal() {
  if (!heldTestSignal.blob) {
    throw new Error("没有可重新提交的待测 WAV。");
  }
  const hz = document.getElementById("upgrade-nominal-hz").value;
  if (!hz || !String(hz).trim()) {
    throw new Error("请先填写标称基频（Hz）。");
  }
  const body = new FormData();
  body.append("test_file", heldTestSignal.blob, heldTestSignal.filename || "input.wav");
  body.append("mode", "nominal_single_tone");
  body.append("stimulus_kind", "single_tone");
  body.append("nominal_fundamental_hz", hz);
  body.append("user_request", heldTestSignal.userRequest || "");
  body.append("channel", heldTestSignal.channel || "mixdown");
  const submission = await postContextualWav(body);
  renderLifecycle(submission.status);
  await pollRun(submission.run_id, { contextual: true });
}

function bindUi() {
  setSubmitRunEnabled();
  document.getElementById("diagnose-form").addEventListener("submit", submitDiagnose);
  document
    .getElementById("diagnostic-mode")
    .addEventListener("change", updateContextualFields);
  document
    .querySelectorAll('input[name="source-mode"]')
    .forEach((input) => input.addEventListener("change", updateContextualFields));
  const pairedButton = document.getElementById("upgrade-paired");
  const nominalButton = document.getElementById("upgrade-nominal");
  if (pairedButton) {
    pairedButton.addEventListener("click", () => {
      submitUpgradePaired().catch((error) => {
        showError(error instanceof Error ? error.message : String(error));
      });
    });
  }
  if (nominalButton) {
    nominalButton.addEventListener("click", () => {
      submitUpgradeNominal().catch((error) => {
        showError(error instanceof Error ? error.message : String(error));
      });
    });
  }
  setUpgradeControlsVisible(false);
  updateContextualFields();
  loadPlannerHealth().catch(() => {
    plannerHealthAllowsSubmit = false;
    renderPlannerHealthFailure();
    setSubmitRunEnabled();
  });
  loadPresets().catch((error) => {
    showError(error instanceof Error ? error.message : String(error));
  });
  loadEvaluation().catch((error) => {
    showError(error instanceof Error ? error.message : String(error));
  });
}

/** Files chosen for intake, held in page memory until the user confirms (§25). */
const intakeState = {
  filesByName: {},
  filenames: [],
  draft: null,
};

const INTAKE_FIELD_LABELS = {
  mode: "intake-mode",
  reference_file: "intake-reference",
  nominal_fundamental_hz: "intake-nominal-hz",
  stimulus_kind: "intake-stimulus-kind",
};

function setOptions(select, values, labels) {
  select.replaceChildren();
  for (const value of values) {
    const option = appendText(select, "option", labels ? labels[value] : value);
    option.value = value;
  }
}

function refreshIntakeFiles() {
  const picker = document.getElementById("intake-files");
  const files = Array.from(picker.files || []);
  intakeState.filesByName = {};
  for (const file of files) {
    intakeState.filesByName[file.name] = file;
  }
  intakeState.filenames = files.map((file) => file.name);
  setOptions(document.getElementById("intake-test-file"), intakeState.filenames);
  intakeState.draft = null;
  document.getElementById("intake-confirm").hidden = true;
  document.getElementById("intake-raw").hidden = true;
}

function intakeTestFile() {
  return document.getElementById("intake-test-file").value;
}

async function readIntakeSampleRates(filenames) {
  const rates = [];
  for (const name of filenames) {
    try {
      const header = await intakeState.filesByName[name].slice(0, 4096).arrayBuffer();
      rates.push(wavHeaderSampleRate(header));
    } catch (_error) {
      rates.push(null);
    }
  }
  return rates;
}

async function requestIntakeDraft() {
  const text = document.getElementById("intake-text").value.trim();
  const filenames = intakeState.filenames;
  if (!text || filenames.length === 0) {
    throw new Error("请先写问题描述，并至少选择一个 WAV 文件。");
  }
  if (filenames.length > INTAKE_MAX_FILES) {
    throw new Error(`最多选择 ${INTAKE_MAX_FILES} 个 WAV 文件。`);
  }
  const testFile = intakeTestFile();
  const sampleRates = await readIntakeSampleRates(filenames);
  const response = await fetch("/api/v1/intake/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildDraftRequestBody(text, filenames, testFile, sampleRates)),
  });
  const draft = await parseJsonResponse(response);
  intakeState.draft = draft;
  document.getElementById("intake-result").textContent = JSON.stringify(draft, null, 2);
  document.getElementById("intake-raw").hidden = false;
  showIntakeDraft(draft, testFile);
}

function showIntakeDraft(draft, testFile) {
  const doubtful = new Set([...(draft.missing_fields || []), ...(draft.asked_fields || [])]);
  const others = intakeState.filenames.filter((name) => name !== testFile);
  setOptions(document.getElementById("intake-reference"), others);
  document.getElementById("intake-mode").value = draft.mode;
  if (draft.reference_file && others.includes(draft.reference_file)) {
    document.getElementById("intake-reference").value = draft.reference_file;
  }
  document.getElementById("intake-nominal-hz").value =
    draft.nominal_fundamental_hz == null ? "" : String(draft.nominal_fundamental_hz);
  document.getElementById("intake-stimulus-kind").value =
    draft.stimulus_kind === "single_tone" ? "single_tone" : "";
  for (const id of [
    "intake-mode-confirmed",
    "intake-reference-confirmed",
    "intake-nominal-confirmed",
    "intake-stimulus-confirmed",
  ]) {
    document.getElementById(id).checked = false;
  }
  for (const [field, id] of Object.entries(INTAKE_FIELD_LABELS)) {
    document.getElementById(id).classList.toggle("needs-confirmation", doubtful.has(field));
  }
  const list = document.getElementById("intake-questions");
  list.replaceChildren();
  const questions = draft.questions || [];
  const asked = draft.asked_fields || [];
  questions.forEach((question, index) => {
    const prefix = asked.length === questions.length ? `${asked[index]}: ` : "";
    appendText(list, "li", `${prefix}${question}`);
  });
  document.getElementById("intake-confirm").hidden = false;
  updateIntakePlan();
}

function intakeSelection() {
  const checked = (id) => document.getElementById(id).checked;
  const hzText = document.getElementById("intake-nominal-hz").value.trim();
  const kind = document.getElementById("intake-stimulus-kind").value;
  return {
    mode: checked("intake-mode-confirmed") ? document.getElementById("intake-mode").value : null,
    reference_file: checked("intake-reference-confirmed")
      ? document.getElementById("intake-reference").value || null
      : null,
    nominal_fundamental_hz:
      checked("intake-nominal-confirmed") && hzText !== "" ? Number(hzText) : null,
    stimulus_kind: checked("intake-stimulus-confirmed") && kind ? kind : null,
  };
}

const INTAKE_FIELD_NAMES_ZH = {
  mode: "诊断模式",
  reference_file: "参考文件",
  nominal_fundamental_hz: "标称基频",
  stimulus_kind: "激励类型",
};

function intakeDowngradeNoteZh(assembly) {
  const fields = assembly.unconfirmed_fields
    .map((field) => INTAKE_FIELD_NAMES_ZH[field] || field)
    .join("、");
  if (assembly.downgraded_from === null) {
    return `${fields}未确认，按单文件信号诊断。`;
  }
  return `${diagnosticModeLabel(assembly.downgraded_from)}还需要确认${fields}，现按单文件信号诊断。`;
}

function updateIntakePlan() {
  const mode = document.getElementById("intake-mode").value;
  document.getElementById("intake-reference-fields").hidden = mode !== "paired_reference";
  document.getElementById("intake-nominal-fields").hidden = mode !== "nominal_single_tone";
  document.getElementById("intake-stimulus-fields").hidden = mode !== "nominal_single_tone";
  const plan = document.getElementById("intake-plan");
  const button = document.getElementById("intake-diagnose");
  try {
    const assembly = assembleIntakeSubmission(
      intakeSelection(),
      intakeState.filenames,
      intakeTestFile(),
    );
    const note = intakeDowngradeMessage(assembly);
    plan.textContent =
      `将按此模式诊断：${diagnosticModeLabel(assembly.mode)}。` +
      (note ? ` ${intakeDowngradeNoteZh(assembly)}` : "");
    button.disabled = !plannerHealthAllowsSubmit;
  } catch (error) {
    plan.textContent = error instanceof Error ? error.message : String(error);
    button.disabled = true;
  }
}

function confirmOnEdit(inputId, checkboxId) {
  const input = document.getElementById(inputId);
  const markConfirmed = () => {
    document.getElementById(checkboxId).checked = true;
    updateIntakePlan();
  };
  input.addEventListener("change", markConfirmed);
  input.addEventListener("input", markConfirmed);
}

async function submitIntakeDiagnosis(event) {
  event.preventDefault();
  const testFile = intakeTestFile();
  const assembly = assembleIntakeSubmission(intakeSelection(), intakeState.filenames, testFile);
  const channel = document.getElementById("channel").value;
  const button = document.getElementById("intake-diagnose");
  button.disabled = true;
  document.getElementById("report-json").hidden = true;
  document.getElementById("report-html").hidden = true;
  try {
    rememberHeldTestSignal({
      blob: intakeState.filesByName[testFile],
      filename: testFile,
      channel,
      userRequest: INTAKE_DIAGNOSIS_QUESTION,
    });
    const body = buildIntakeDiagnoseForm(assembly, intakeState.filesByName, testFile, channel);
    const submission = await postContextualWav(body);
    renderLifecycle(submission.status);
    await pollRun(submission.run_id, { contextual: true });
  } finally {
    updateIntakePlan();
  }
}

function bindIntake() {
  const button = document.getElementById("intake-draft");
  if (!button) return;
  const report = (error) => showError(error instanceof Error ? error.message : String(error));
  document.getElementById("intake-files").addEventListener("change", refreshIntakeFiles);
  document.getElementById("intake-test-file").addEventListener("change", () => {
    if (intakeState.draft) showIntakeDraft(intakeState.draft, intakeTestFile());
  });
  button.addEventListener("click", () => {
    requestIntakeDraft().catch(report);
  });
  confirmOnEdit("intake-mode", "intake-mode-confirmed");
  confirmOnEdit("intake-reference", "intake-reference-confirmed");
  confirmOnEdit("intake-nominal-hz", "intake-nominal-confirmed");
  confirmOnEdit("intake-stimulus-kind", "intake-stimulus-confirmed");
  for (const id of [
    "intake-mode-confirmed",
    "intake-reference-confirmed",
    "intake-nominal-confirmed",
    "intake-stimulus-confirmed",
  ]) {
    document.getElementById(id).addEventListener("change", updateIntakePlan);
  }
  document.getElementById("intake-confirm").addEventListener("submit", (event) => {
    submitIntakeDiagnosis(event).catch(report);
  });
}

bindUi();
bindIntake();
