"use strict";
// Multi-round test session panel (D060, §32). Text is set with textContent only.
(function () {
  const byId = (id) => document.getElementById(id);
  const FIX_TEXT = {
    rerecord_quieter: "降低环境噪声（或提高播放音量）后重录",
    use_one_clock: "播放和录音使用同一个时钟（同一台声卡）",
    check_stimulus_file: "确认播放的是本页下载的测试信号",
    record_whole_stimulus: "从播放开始前录音，录完整个测试信号",
    check_recorder_gain: "调低录音设备的输入增益，避免录到满刻度",
  };
  const STATUS_TEXT = {
    resolved: "已得出结论",
    blocked_by_user: "无法继续（设备不能重测或条件不允许）",
    budget_exhausted: "轮数已用完，结论仍不完整",
    measurement_failed: "多次尝试后仍无法得到有效测量",
  };
  let current = null;

  function el(tag, text) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function setStatus(text) {
    byId("session-status").textContent = text || "";
  }

  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error((payload.error && payload.error.message) || response.statusText);
    return payload;
  }

  function fillLevels(labels) {
    for (let index = 1; index <= 3; index += 1) {
      const input = byId(`level-label-${index}`);
      const file = byId(`level-file-${index}`);
      if (!input) continue;
      input.value = labels[index - 1] || "";
      if (file) file.value = "";
    }
  }

  function answerControls(next) {
    const box = el("p");
    const send = async (value) => {
      try {
        setStatus("提交中…");
        render(await post(`/api/v1/test-sessions/${current.session.session_id}/answers`, { field: next.field, value }));
        setStatus("");
      } catch (error) {
        setStatus(`出错：${error.message}`);
      }
    };
    if (next.field === "max_level_db") {
      const input = el("input");
      input.type = "number";
      input.step = "3";
      input.value = "0";
      input.id = "session-answer";
      const button = el("button", "确定");
      button.type = "button";
      button.addEventListener("click", () => send(Number(input.value)));
      box.append(input, document.createTextNode(" dB "), button);
    } else if (next.field === "connection") {
      const select = el("select");
      select.id = "session-answer";
      [["line_loopback", "线路接声卡"], ["acoustic_mic", "麦克风拾音"], ["digital_capture", "USB/数字直录"]].forEach(([value, text]) => {
        const option = el("option", text);
        option.value = value;
        select.appendChild(option);
      });
      const button = el("button", "确定");
      button.type = "button";
      button.addEventListener("click", () => send(select.value));
      box.append(select, document.createTextNode(" "), button);
    } else {
      [["能", true], ["不能", false]].forEach(([text, value]) => {
        const button = el("button", text);
        button.type = "button";
        button.addEventListener("click", () => send(value));
        box.append(button, document.createTextNode(" "));
      });
    }
    return box;
  }

  function render(view) {
    current = view;
    const body = byId("session-body");
    body.replaceChildren();
    const next = view.next;
    if (next.kind === "propose_test") {
      body.appendChild(el("p", `第 ${view.session.rounds.length + 1} 轮（剩余 ${view.rounds_left} 轮）：请按下列电平各录一次，并在上方第 3 步上传分析：`));
      body.appendChild(el("p", next.level_labels.join("、")));
      if (next.fix) body.appendChild(el("p", `这次先处理测量问题：${FIX_TEXT[next.fix] || next.fix}`));
      fillLevels(next.level_labels);
    } else if (next.kind === "ask_user") {
      body.appendChild(el("p", next.question));
      body.appendChild(answerControls(next));
    } else if (next.kind === "finish") {
      body.appendChild(el("p", `会话结束：${STATUS_TEXT[next.status] || next.status}`));
    }
    const list = el("ul");
    view.summary.forEach((line) => list.appendChild(el("li", line)));
    body.appendChild(list);
  }

  async function start() {
    try {
      setStatus("创建会话…");
      const params = new URLSearchParams(window.location.search);
      const body = { sample_rate_hz: Number(byId("sweep-rate").value) };
      if (params.get("plan")) body.plan_key = params.get("plan");
      render(await post("/api/v1/test-sessions", body));
      setStatus("");
    } catch (error) {
      setStatus(`出错：${error.message}`);
    }
  }

  async function linkRun(runId) {
    if (!current || current.next.kind !== "propose_test") return;
    try {
      render(await post(`/api/v1/test-sessions/${current.session.session_id}/runs`, { run_id: runId }));
    } catch (error) {
      setStatus(`本次录音没有计入会话：${error.message}`);
    }
  }

  window.SignalSession = { linkRun };
  const button = byId("session-start");
  if (button) button.addEventListener("click", start);
})();
