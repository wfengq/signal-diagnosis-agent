"use strict";

// §30 (D055): plain-language explanation of a finished run. The template is
// loaded by default; the AI rewrite button appears only when the health
// response says the model path is available. All text uses textContent.
(function () {
  const TITLES = { conclusion: "结论", evidence: "依据", meaning: "含义", next_steps: "下一步" };
  let modelAvailable = false;

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function sourceText(result) {
    if (result.source === "model" && result.explainer) {
      return `由 AI（${result.explainer.model}，${result.explainer.prompt_version}）根据本次证据撰写；结论来自确定性引擎。`;
    }
    const base = "模板解释，由代码根据本次证据生成。";
    return result.fallback_reason ? `${base}（AI 改写未采用：${result.fallback_reason}）` : base;
  }

  function render(container, result) {
    container.replaceChildren();
    container.appendChild(el("p", sourceText(result), "muted"));
    for (const section of result.draft.sections) {
      const texts = (section.sentences || []).map((s) => s.text)
        .concat((section.steps || []).map((s) => s.text));
      if (!texts.length) continue;
      container.appendChild(el("h3", TITLES[section.kind] || section.kind));
      const list = el("ul");
      for (const text of texts) list.appendChild(el("li", text));
      container.appendChild(list);
    }
  }

  async function request(url, useModel) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: "zh", use_model: useModel }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error ? payload.error.message : String(response.status));
    }
    return payload;
  }

  async function show(ids, url) {
    const panel = document.getElementById(ids.panel);
    const body = document.getElementById(ids.body);
    const button = document.getElementById(ids.button);
    const status = document.getElementById(ids.status);
    panel.hidden = false;
    status.textContent = "";
    button.hidden = !modelAvailable;
    button.disabled = false;
    button.onclick = async () => {
      button.disabled = true;
      status.textContent = "AI 改写中…";
      try {
        render(body, await request(url, true));
        status.textContent = "";
      } catch (error) {
        status.textContent = `AI 改写失败：${error.message}`;
      } finally {
        button.disabled = false;
      }
    };
    try {
      render(body, await request(url, false));
    } catch (error) {
      body.replaceChildren(el("p", `无法生成解释：${error.message}`, "muted"));
    }
    // §33: questions about the same run, when the Q&A model is available.
    if (window.SignalQA) window.SignalQA.attach(panel, url.replace(/\/explanation$/, "/questions"));
  }

  function hide(panelId) {
    const panel = document.getElementById(panelId);
    if (panel) panel.hidden = true;
  }

  async function loadAvailability() {
    try {
      const response = await fetch("/api/v1/health");
      const health = await response.json();
      modelAvailable = Boolean(health.explanation && health.explanation.model_available);
    } catch (_error) {
      modelAvailable = false;
    }
  }

  window.SignalExplanation = { show, hide, render, loadAvailability };
})();
