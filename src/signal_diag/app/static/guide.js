"use strict";

// §31 (D057): test guide. The questionnaire is always available; the AI draft
// button appears only when health says the model path is available. Nothing is
// confirmed until the user presses confirm with the values shown in the form.
(function () {
  const PLAN_LABELS = {
    sweep_levels: "扫频测试多个音量",
    existing_recording: "分析现成录音",
    paired_reference: "与参考录音对比",
    nominal_tone: "已知频率的单音",
  };
  const CONNECTION_LABELS = {
    line_loopback: "声卡线路环回",
    acoustic_mic: "音箱放音、麦克风录音",
    digital_capture: "设备自带 USB 或数字录音",
  };
  const byId = (id) => document.getElementById(id);
  let questionnaire = [];
  let answers = {};
  let source = "questionnaire";

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  async function post(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error ? payload.error.message : String(response.status));
    return payload;
  }

  function showPlan(draft, origin, notes) {
    source = origin;
    const form = byId("guide-plan");
    form.hidden = false;
    byId("guide-result").hidden = true;
    byId("guide-plan-id").value = draft.plan_id;
    const p = draft.parameters || {};
    byId("guide-rate").value = String(p.sample_rate_hz || 48000);
    const labels = p.level_labels || [];
    for (let i = 0; i < 3; i += 1) byId(`guide-level-${i + 1}`).value = labels[i] || "";
    byId("guide-connection").value = p.connection || "line_loopback";
    byId("guide-hz").value = p.nominal_fundamental_hz ? String(p.nominal_fundamental_hz) : "";
    const list = byId("guide-notes");
    list.replaceChildren();
    for (const note of notes) list.appendChild(el("li", note));
    updateFields();
  }

  function updateFields() {
    const plan = byId("guide-plan-id").value;
    byId("guide-sweep-fields").hidden = plan !== "sweep_levels";
    byId("guide-hz-field").hidden = plan !== "nominal_tone";
  }

  function renderQuestion(id) {
    const holder = byId("guide-questions");
    holder.replaceChildren();
    const question = questionnaire.find((q) => q.question_id === id);
    if (!question) return;
    holder.appendChild(el("p", question.text_zh));
    for (const option of question.options) {
      const button = el("button", option.label_zh);
      button.type = "button";
      button.addEventListener("click", async () => {
        answers[question.question_id] = option.answer;
        if (option.next) {
          renderQuestion(option.next);
          return;
        }
        holder.replaceChildren();
        try {
          const draft = await post("/api/v1/test-plans/questionnaire", { answers, language: "zh" });
          showPlan(draft, "questionnaire", ["按问卷选出的方案；采样率和音量标签是默认值，请检查后确认。"]);
        } catch (error) {
          byId("guide-status").textContent = `出错：${error.message}`;
        }
      });
      holder.appendChild(button);
    }
  }

  async function startQuestionnaire(note) {
    const text = byId("guide-text").value.trim() || "（未填写描述）";
    const result = await post("/api/v1/test-plans/draft", { text, use_model: false });
    questionnaire = result.questionnaire;
    answers = {};
    byId("guide-status").textContent = note || "";
    renderQuestion("can_replay");
  }

  async function aiDraft() {
    const text = byId("guide-text").value.trim();
    const status = byId("guide-status");
    if (!text) {
      status.textContent = "请先描述问题。";
      return;
    }
    status.textContent = "AI 起草中…";
    try {
      const result = await post("/api/v1/test-plans/draft", { text, use_model: true });
      if (result.source === "model" && result.draft) {
        status.textContent = "";
        const notes = (result.draft.rationale_quotes || []).map((q) => `依据你写的：“${q}”`)
          .concat((result.draft.questions || []).map((q) => `需要你补充：${q}`))
          .concat(["这是 AI 草稿，所有字段都要你确认后才生效。"]);
        showPlan(result.draft, "model", notes);
      } else {
        await startQuestionnaire(`AI 草稿未采用（${result.fallback_reason}），请用问卷选择。`);
      }
    } catch (error) {
      status.textContent = `出错：${error.message}`;
    }
  }

  async function confirm(event) {
    event.preventDefault();
    const plan = byId("guide-plan-id").value;
    const body = { plan_id: plan, source, language: "zh" };
    if (plan === "sweep_levels") {
      body.sample_rate_hz = Number(byId("guide-rate").value);
      body.level_labels = [1, 2, 3].map((i) => byId(`guide-level-${i}`).value.trim()).filter(Boolean);
      body.connection = byId("guide-connection").value;
    }
    if (plan === "nominal_tone") body.nominal_fundamental_hz = Number(byId("guide-hz").value);
    try {
      const record = await post("/api/v1/test-plans/confirm", body);
      const steps = byId("guide-steps");
      steps.replaceChildren();
      for (const step of record.steps) steps.appendChild(el("li", step));
      byId("guide-next").href = record.next_page;
      byId("guide-result").hidden = false;
      byId("guide-status").textContent = "";
    } catch (error) {
      byId("guide-status").textContent = `无法确认：${error.message}`;
    }
  }

  function bind() {
    if (!byId("guide-panel")) return;
    const planSelect = byId("guide-plan-id");
    for (const [value, label] of Object.entries(PLAN_LABELS)) {
      const option = el("option", label);
      option.value = value;
      planSelect.appendChild(option);
    }
    const connection = byId("guide-connection");
    for (const [value, label] of Object.entries(CONNECTION_LABELS)) {
      const option = el("option", label);
      option.value = value;
      connection.appendChild(option);
    }
    planSelect.addEventListener("change", updateFields);
    byId("guide-start").addEventListener("click", () => startQuestionnaire(""));
    byId("guide-model").addEventListener("click", aiDraft);
    byId("guide-plan").addEventListener("submit", confirm);
    fetch("/api/v1/health")
      .then((response) => response.json())
      .then((health) => {
        byId("guide-model").hidden = !(health.guide && health.guide.model_available);
      })
      .catch(() => {});
  }

  // Pages opened from a confirmed plan show its steps and link their run to it.
  async function loadPlanFromUrl() {
    const key = new URLSearchParams(window.location.search).get("plan");
    if (!key || !/^plan_[0-9a-f]+$/.test(key)) return null;
    const response = await fetch(`/api/v1/test-plans/${key}`);
    if (!response.ok) return null;
    const record = await response.json();
    const banner = byId("plan-banner");
    if (banner) {
      banner.hidden = false;
      banner.replaceChildren(el("h2", "测试方案"));
      const list = el("ol");
      for (const step of record.steps) list.appendChild(el("li", step));
      banner.appendChild(list);
    }
    return record;
  }

  async function linkRun(record, runId) {
    if (!record || !runId) return;
    try {
      await post(`/api/v1/test-plans/${record.plan_key}/runs`, { run_id: runId });
    } catch (_error) {
      // The plan link is informational; the run itself is unaffected.
    }
  }

  window.SignalGuide = { bind, loadPlanFromUrl, linkRun };
  document.addEventListener("DOMContentLoaded", bind);
})();
