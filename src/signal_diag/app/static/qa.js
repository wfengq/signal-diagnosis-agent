"use strict";

// §33 (D060 C): ask a question about a finished run. Shown only when the
// health response says the Q&A model path is available; answers cite the
// run's evidence and may decline. All text uses textContent.
(function () {
  let modelAvailable = false;

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function sourceText(result) {
    if (result.source === "model" && result.answerer) {
      return `由 AI（${result.answerer.model}，${result.answerer.prompt_version}）根据本次证据回答；结论来自确定性引擎。`;
    }
    const base = "模板回答，由代码根据本次证据生成。";
    return result.fallback_reason ? `${base}（AI 回答未采用：${result.fallback_reason}）` : base;
  }

  function render(container, result) {
    container.replaceChildren();
    container.appendChild(el("p", `问：${result.question}`));
    const list = el("ul");
    for (const line of result.lines) list.appendChild(el("li", line));
    container.appendChild(list);
    container.appendChild(el("p", sourceText(result), "muted"));
  }

  async function ask(url, question) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, language: "zh", use_model: true }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error ? payload.error.message : String(response.status));
    }
    return payload;
  }

  function attach(panel, url) {
    const old = panel.querySelector(".qa-box");
    if (old) old.remove();
    if (!modelAvailable) return;
    const box = el("div", undefined, "qa-box");
    box.appendChild(el("h3", "就本次结果提问"));
    const form = el("form");
    const input = el("input");
    input.type = "text";
    input.maxLength = 500;
    input.required = true;
    input.placeholder = "例如：削波比例是什么意思？";
    input.setAttribute("aria-label", "问题");
    const button = el("button", "提问");
    button.type = "submit";
    const status = el("span", "", "muted");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    form.append(input, button, status);
    const answer = el("div");
    box.append(form, answer, el("p", "只根据本次测试的证据回答；证据回答不了的问题会说明并建议下一步。", "muted"));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = input.value.trim();
      if (!question) return;
      button.disabled = true;
      status.textContent = "AI 回答中…";
      try {
        render(answer, await ask(url, question));
        status.textContent = "";
      } catch (error) {
        status.textContent = `提问失败：${error.message}`;
      } finally {
        button.disabled = false;
      }
    });
    panel.appendChild(box);
  }

  async function loadAvailability() {
    try {
      const response = await fetch("/api/v1/health");
      const health = await response.json();
      modelAvailable = Boolean(health.qa && health.qa.model_available);
    } catch (_error) {
      modelAvailable = false;
    }
  }

  window.SignalQA = { attach, loadAvailability };
})();
