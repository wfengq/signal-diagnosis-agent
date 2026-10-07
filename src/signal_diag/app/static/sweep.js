"use strict";

(function () {
  const SERIES = ["#2a78d6", "#eb6834", "#1baf7a"];
  const OUTCOME_TEXT = {
    supported_fault: "发现失真",
    no_supported_fault: "未发现受支持的故障",
    inconclusive: "无法判定",
  };

  const byId = (id) => document.getElementById(id);

  function bandLabel(center) {
    return center >= 1000 ? `${center / 1000}k Hz` : `${center} Hz`;
  }

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function renderChart(svgText) {
    const holder = byId("sweep-chart");
    holder.replaceChildren();
    const parsed = new DOMParser().parseFromString(svgText, "image/svg+xml");
    const svg = parsed.documentElement;
    if (svg && svg.nodeName === "svg") holder.appendChild(document.importNode(svg, true));
  }

  function renderLegend(levels) {
    const legend = byId("sweep-legend");
    legend.replaceChildren();
    levels.forEach((level, index) => {
      const item = el("li");
      const key = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      key.setAttribute("width", "18");
      key.setAttribute("height", "8");
      key.setAttribute("aria-hidden", "true");
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      for (const [name, value] of Object.entries({
        x1: "1", x2: "17", y1: "4", y2: "4", stroke: SERIES[index],
        "stroke-width": "2", "stroke-linecap": "round",
      })) line.setAttribute(name, value);
      key.appendChild(line);
      item.append(key, document.createTextNode(` ${level.level_label}`));
      legend.appendChild(item);
    });
  }

  function renderTable(levels) {
    const head = byId("sweep-table-head");
    const body = byId("sweep-table-body");
    const row = el("tr");
    row.appendChild(el("th", "频带（Band）"));
    levels.forEach((level) => row.appendChild(el("th", level.level_label)));
    head.replaceChildren(row);
    body.replaceChildren();
    levels[0].measurement.bands.forEach((_, index) => {
      const tr = el("tr");
      tr.appendChild(el("th", bandLabel(levels[0].measurement.bands[index].center_hz)));
      levels.forEach((level) => {
        const band = level.measurement.bands[index];
        if (band.measurable && band.thd_percent !== null) {
          const order = band.dominant_order ? `（${band.dominant_order} 次为主）` : "";
          tr.appendChild(el("td", `${band.thd_percent.toFixed(2)}%${order}`));
        } else {
          tr.appendChild(el("td", "不可测", "muted"));
        }
      });
      body.appendChild(tr);
    });
  }

  function renderClaims(levels) {
    const holder = byId("sweep-claims");
    holder.replaceChildren();
    levels.forEach((level) => {
      holder.appendChild(
        el("h4", `${level.level_label}：${OUTCOME_TEXT[level.outcome] || level.outcome}`),
      );
      const list = el("ul");
      level.claims.forEach((claim) => {
        const item = el("li");
        item.appendChild(el("strong", claim.fault_type));
        item.appendChild(document.createTextNode(`: ${claim.statement}`));
        item.appendChild(el("br"));
        item.appendChild(el("span", `规则评估：${claim.rule_refs.join(", ")}`, "muted"));
        list.appendChild(item);
      });
      holder.appendChild(list);
    });
  }

  function render(payload) {
    byId("sweep-summary").textContent =
      `${OUTCOME_TEXT[payload.outcome] || payload.outcome}。${payload.summary}`;
    byId("sweep-identity").textContent =
      `${payload.engine_version} · ${payload.profile_id} ${payload.profile_version} · ` +
      `${payload.sample_rate_hz} Hz · 模型调用 ${payload.model_calls} 次 · ${payload.threshold_notice}`;
    renderLegend(payload.levels);
    renderChart(payload.chart_svg);
    renderTable(payload.levels);
    renderClaims(payload.levels);
    const base = `/api/v1/sweep-runs/${encodeURIComponent(payload.run_id)}`;
    byId("sweep-report-json").href = `${base}/report.json`;
    byId("sweep-report-html").href = `${base}/report.html`;
    byId("sweep-result").hidden = false;
    window.SignalGuide.linkRun(plan, payload.run_id);
    window.SignalExplanation.show(
      {
        panel: "sweep-explanation-panel",
        body: "sweep-explanation-body",
        button: "sweep-explanation-model",
        status: "sweep-explanation-status",
      },
      `${base}/explanation`,
    );
  }

  window.SignalExplanation.loadAvailability();
  let plan = null;
  window.SignalGuide.loadPlanFromUrl().then((record) => {
    plan = record;
    if (!record || record.plan_id !== "sweep_levels") return;
    const rate = String(record.parameters.sample_rate_hz);
    byId("sweep-rate").value = rate;
    byId("stimulus-link").href = `/api/v1/sweep/stimulus?rate=${rate}`;
    (record.parameters.level_labels || []).forEach((label, index) => {
      const input = byId(`level-label-${index + 1}`);
      if (input) input.value = label;
    });
  });

  byId("sweep-rate").addEventListener("change", (event) => {
    byId("stimulus-link").href = `/api/v1/sweep/stimulus?rate=${event.target.value}`;
  });

  byId("sweep-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = byId("sweep-status");
    const form = new FormData();
    const labels = [];
    for (let index = 1; index <= 3; index += 1) {
      const file = byId(`level-file-${index}`).files[0];
      if (!file) continue;
      labels.push(byId(`level-label-${index}`).value.trim());
      form.append(`recording_${labels.length}`, file, file.name);
    }
    if (labels.length === 0) {
      status.textContent = "请至少上传一个录音。";
      return;
    }
    form.append("metadata", JSON.stringify({ levels: labels }));
    byId("sweep-submit").disabled = true;
    status.textContent = "分析中…";
    try {
      const response = await fetch("/api/v1/sweep-runs", { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) {
        status.textContent = `错误：${payload.error ? payload.error.message : response.status}`;
        return;
      }
      status.textContent = "";
      render(payload);
    } catch (error) {
      status.textContent = "请求失败，请重试。";
    } finally {
      byId("sweep-submit").disabled = false;
    }
  });
})();
