const API = "/api";

let currentRunId = null;
let currentAnalytics = null;
let currentMatrixData = null;
let selectedFiles = [];
let chartTrajectory = null;
let chartArAp = null;
let chartInflowsOutflows = null;
let chartRevenueStreams = null;
let activeTimeframe = 52;

const SECTIONS = ["dashboard", "upload", "matrix", "config"];

function showSection(name) {
  SECTIONS.forEach((s) => {
    const sec = document.getElementById(`section-${s}`);
    const nav = document.getElementById(`nav-${s}`);
    if (sec) {
      if (s === name) sec.classList.remove("hidden");
      else sec.classList.add("hidden");
    }
    if (nav) {
      if (s === name) nav.classList.add("active");
      else nav.classList.remove("active");
    }
  });
  const titleEl = document.getElementById("page-title");
  if (titleEl) {
    titleEl.textContent = {
      dashboard: "Executive Dashboard",
      upload: "Auto-Ingest Data Files",
      matrix: "52-Week Matrix",
      config: "Assumptions & Rules",
    }[name] || name;
  }
}
window.showSection = showSection;

function showToast(msg, type = "info") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => {
    t.classList.remove("show");
  }, 4000);
}

function fmtMoney(num, maxDec = 0) {
  if (num === null || num === undefined) return "$0";
  return (num < 0 ? "-$" : "$") + Math.abs(num).toLocaleString("en-US", {
    minimumFractionDigits: maxDec,
    maximumFractionDigits: maxDec,
  });
}

async function loadRuns() {
  try {
    const res = await fetch(`${API}/runs`);
    const runs = await res.json();
    const select = document.getElementById("active-run-select");
    if (!runs || runs.length === 0) {
      select.innerHTML = '<option value="">No runs yet</option>';
      return;
    }
    select.innerHTML = runs.map((r) => `<option value="${r.run_id}">${runLabel(r)}</option>`).join("");
    if (currentRunId) select.value = currentRunId;

    if (!currentRunId && runs.length > 0) {
      currentRunId = runs[0].run_id;
      loadRunDetails(currentRunId);
    }
  } catch (e) {
    showToast("Failed to load runs: " + e.message, "error");
  }
}

async function onRunSelectChange(runId) {
  if (!runId) return;
  currentRunId = runId;
  await loadRunDetails(runId);
}

async function loadRunDetails(runId) {
  try {
    const res = await fetch(`${API}/runs/${runId}/analytics`);
    if (!res.ok) {
      showToast("Run analytics not ready yet", "warning");
      return;
    }
    currentAnalytics = await res.json();
    renderKPIs(currentAnalytics.kpis);
    renderCharts(currentAnalytics, activeTimeframe);
    loadMatrix(runId);
    const sel = document.getElementById("active-run-select");
    const opt = sel && sel.selectedOptions && sel.selectedOptions[0];
    document.getElementById("topbar-date-chip").textContent = opt ? `Forecast ${opt.textContent.split(" · ")[0]}` : `Run: ${runId.slice(0, 8)}`;
    if (opt) document.getElementById("topbar-date-chip").title = opt.textContent;
  } catch (e) {
    console.error(e);
  }
}

function renderKPIs(kpis) {
  if (!kpis) return;
  document.getElementById("stat-opening-cash").textContent = fmtMoney(kpis.opening_cash);
  if (kpis.as_of) document.getElementById("stat-opening-date").textContent = `As-of ${kpis.as_of}`;
  document.getElementById("stat-lowest-cash").textContent = fmtMoney(kpis.lowest_cash);
  document.getElementById("stat-lowest-week").textContent = `Occurs at Week ${kpis.lowest_week}`;
  
  const badgeLow = document.getElementById("badge-low-point");
  if (kpis.lowest_cash < 0) {
    badgeLow.textContent = "Runway Alert";
    badgeLow.className = "badge warning";
  } else {
    badgeLow.textContent = "Safe Buffer";
    badgeLow.className = "badge verified";
  }

  document.getElementById("stat-ending-cash").textContent = fmtMoney(kpis.ending_cash);
  const netSign = kpis.net_change >= 0 ? "+" : "";
  const pct = kpis.opening_cash > 0 ? Math.round((kpis.net_change / kpis.opening_cash) * 100) : 0;
  document.getElementById("stat-net-growth").textContent = `${netSign}${fmtMoney(kpis.net_change)} (${netSign}${pct}%)`;

  document.getElementById("stat-total-totals").textContent = `${fmtMoney(kpis.total_inflow / 1e6, 2)}M / ${fmtMoney(kpis.total_outflow / 1e6, 2)}M`;
  document.getElementById("stat-avg-net").textContent = `${kpis.avg_weekly_net >= 0 ? "+" : ""}${fmtMoney(kpis.avg_weekly_net)}/wk avg net cash`;

  let totalAr = kpis.total_ar;
  let totalAp = kpis.total_ap;
  if (!totalAr && currentAnalytics && currentAnalytics.ar_ap) totalAr = currentAnalytics.ar_ap.total_ar;
  if (!totalAp && currentAnalytics && currentAnalytics.ar_ap) totalAp = currentAnalytics.ar_ap.total_ap;
  if (!totalAr && currentAnalytics && currentAnalytics.revenue_streams && currentAnalytics.revenue_streams["A/R Collection"]) {
    totalAr = currentAnalytics.revenue_streams["A/R Collection"].reduce((a, b) => a + b, 0);
  }
  if (!totalAp && currentAnalytics && currentAnalytics.cogs_breakdown && currentAnalytics.cogs_breakdown["COGS Standard"]) {
    totalAp = currentAnalytics.cogs_breakdown["COGS Standard"].reduce((a, b) => a + b, 0);
  }

  if (document.getElementById("stat-total-ar")) {
    document.getElementById("stat-total-ar").textContent = fmtMoney(totalAr || 0);
  }
  if (document.getElementById("stat-total-ap")) {
    document.getElementById("stat-total-ap").textContent = fmtMoney(totalAp || 0);
  }
}

function setChartTimeframe(weeksStr) {
  activeTimeframe = parseInt(weeksStr, 10);
  document.querySelectorAll('.chart-controls .pill[onclick^="setChartTimeframe"]').forEach((el) => {
    el.classList.toggle("active", el.textContent.includes(weeksStr));
  });
  if (currentAnalytics) {
    renderCharts(currentAnalytics, activeTimeframe);
  }
}

// ML timing line + p10-p90 band on the Cash Position Trajectory, next to the rule-based line.
// Source: GET /api/ml/runs/{run}/compare (about 3.5 s the first time, then cached on the server; also cached per run in the page and drawn after the main chart).
const mlTrajCache = {};

async function overlayMlTrajectory(chart, runId, limit) {
  const note = document.getElementById("traj-ml-note");
  const legend = document.getElementById("traj-legend");
  if (!chart || !runId || !note) return;
  let c = mlTrajCache[runId];
  if (c === undefined) {
    note.textContent = "Loading the ML timing line...";
    try {
      const r = await fetch(`${API}/ml/runs/${runId}/compare`);
      c = r.ok ? await r.json() : null;
    } catch (_) { c = null; }
    mlTrajCache[runId] = c;
  }
  if (chartTrajectory !== chart) return; // chart was rebuilt while the call was running
  if (!c) {
    if (legend) legend.style.display = "none";
    note.textContent = "ML timing line not available (train the model on the ML Forecast page).";
    return;
  }
  const ML = "#f0a43a";
  const cut = (a) => a.slice(0, limit);
  chart.data.datasets.push(
    { label: "Timing range low (p10)", data: cut(c.bands.p10), borderColor: "rgba(240,164,58,0.35)", borderWidth: 1, pointRadius: 0, fill: false, tension: 0.25, hideTip: true },
    { label: "Timing range high (p90)", data: cut(c.bands.p90), borderColor: "rgba(240,164,58,0.35)", borderWidth: 1, pointRadius: 0, fill: "-1", backgroundColor: "rgba(240,164,58,0.14)", tension: 0.25, hideTip: true },
    { label: "Paid when customers actually pay (ML timing)", data: cut(c.ending_cash_ml), borderColor: ML, borderWidth: 2.5, borderDash: [7, 5], pointRadius: 0, pointHoverRadius: 5, fill: false, tension: 0.25 },
  );
  chart.update();
  if (legend) legend.style.display = "flex";
  const diff = c.ending_cash_rules.map((v, i) => Math.abs(v - c.ending_cash_ml[i]));
  const last = diff.reduce((m, d, i) => (d > 1 ? i + 1 : m), 0);
  note.textContent = last
    ? `Same documents, different payment dates. The lines differ through week ${last}. After that almost no booked documents are left, so both lines are a flat run-rate assumption, not a forecast.`
    : "The two lines are identical for this run.";
}

// Expected receipts: known (rules) + expected new revenue (ML revenue trend model), from GET /api/ml/runs/{run}/receipts-outlook.
const rcCache = {};
let chartReceipts = null;
let rcMode = "cum"; // "cum" running total, "wk" per week

function setReceiptsMode(m) {
  rcMode = m;
  document.getElementById("rc-mode-cum").classList.toggle("active", m === "cum");
  document.getElementById("rc-mode-wk").classList.toggle("active", m === "wk");
  renderReceiptsOutlook(currentRunId, activeTimeframe);
}

const rcOn = { documents: true, known: true, forecast: true, range: true };
document.addEventListener("click", (e) => {
  const chip = e.target.closest && e.target.closest("#rc-checks .rc-chip");
  if (!chip) return;
  rcOn[chip.dataset.layer] = !rcOn[chip.dataset.layer];
  chip.classList.toggle("on", rcOn[chip.dataset.layer]);
  chip.setAttribute("aria-pressed", String(rcOn[chip.dataset.layer]));
  renderReceiptsOutlook(currentRunId, activeTimeframe);
});

async function renderReceiptsOutlook(runId, limit) {
  const canvas = document.getElementById("chart-receipts-outlook");
  if (!canvas || !runId) return;
  let c = rcCache[runId];
  if (c === undefined) {
    try {
      const r = await fetch(`${API}/ml/runs/${runId}/receipts-outlook`);
      c = r.ok ? await r.json() : null;
    } catch (_) { c = null; }
    rcCache[runId] = c;
  }
  if (!c) return;
  const on = (k) => rcOn[k];
  const n = Math.min(limit || 52, c.weeks.length);
  const add = (a) => a.slice(0, n);
  const run = (a) => { let t = 0; return a.slice(0, n).map((v) => (t += v)); };
  const shape = rcMode === "cum" ? run : add;
  const docs = c.documents;
  const known = c.documents.map((d, i) => d + c.run_rate[i]);
  const withMl = known.map((k, i) => k + c.forecast_added[i]);
  const low = known.map((k, i) => k + c.forecast_added_low[i]);
  const high = known.map((k, i) => k + c.forecast_added_high[i]);
  const line = (label, data, color, extra = {}) => ({ type: "line", label, data: shape(data), borderColor: color, borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 5, tension: rcMode === "cum" ? 0.15 : 0.25, fill: false, ...extra });
  const datasets = [
    line("Booked invoices and orders", docs, "#a9c3f5", { hidden: !on("documents"), borderWidth: 2 }),
    line("Known (booked + run-rate)", known, "#5b8def", { hidden: !on("known") }),
    line("Known + expected new revenue", withMl, "#f0a43a", { hidden: !on("forecast"), borderDash: [7, 5] }),
    line("Range low", low, "rgba(240,164,58,0.4)", { hidden: !on("range"), borderWidth: 1, hideTip: true }),
    line("Range high", high, "rgba(240,164,58,0.4)", { hidden: !on("range"), borderWidth: 1, hideTip: true, fill: "-1", backgroundColor: "rgba(240,164,58,0.14)" }),
  ];
  if (chartReceipts) { try { chartReceipts.destroy(); } catch (_) {} chartReceipts = null; }
  chartReceipts = new Chart(canvas.getContext("2d"), {
    data: { labels: c.weeks.slice(0, n).map((w) => w.slice(5)), datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false }, tooltip: { filter: (it) => !it.dataset.hideTip,
        callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${fmtMoney(ctx.parsed.y)}` } } },
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.06)" }, ticks: { color: "#8c93a3", font: { family: "JetBrains Mono", size: 10 }, maxTicksLimit: 12, maxRotation: 0, autoSkip: true } },
        y: { grid: { color: "rgba(255,255,255,0.06)" }, ticks: { color: "#8c93a3", font: { family: "JetBrains Mono", size: 10 }, callback: (v) => fmtMoney(v) } },
      },
    },
  });
  const sum = (a) => a.slice(0, n).reduce((x, y) => x + y, 0);
  const m = (v) => "$" + (v / 1e6).toFixed(2) + "M";
  const m1 = (v) => "$" + (v / 1e6).toFixed(1) + "M";
  const kTot = sum(known), mlTot = sum(c.forecast_added), docTot = sum(docs);
  const set = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };
  set("rc-known", m(kTot));
  set("rc-known-sub", `${m(docTot)} booked, ${m(kTot - docTot)} run-rate`);
  set("rc-ml", m(mlTot));
  set("rc-ml-sub", `${Math.round((mlTot / (kTot + mlTot)) * 100)}% of the total`);
  set("rc-total", m(kTot + mlTot));
  set("rc-total-label", `Total receipts, ${n} weeks`);
  set("rc-total-sub", `range ${m(kTot + sum(c.forecast_added_low))} to ${m(kTot + sum(c.forecast_added_high))}`);
  set("rc-v-documents", m(docTot));
  set("rc-v-known", m(kTot));
  set("rc-v-forecast", m(kTot + mlTot));
  set("rc-v-range", `${m1(kTot + sum(c.forecast_added_low))} to ${m1(kTot + sum(c.forecast_added_high))}`);
}

function renderCharts(analytics, limit = 52) {
  if (!analytics || !window.Chart) return;

  const labels = analytics.labels.slice(0, limit);
  const trajectory = analytics.cash_trajectory.slice(0, limit);
  const inflows = analytics.inflows.slice(0, limit);
  const outflows = analytics.outflows.slice(0, limit);
  const revServpro = analytics.revenue_streams.SERVPRO.slice(0, limit);
  const revOther = analytics.revenue_streams["Other Resellers"].slice(0, limit);
  const revAR = analytics.revenue_streams["A/R Collection"].slice(0, limit);
  const revAmazon = (analytics.revenue_streams.Amazon || []).slice(0, limit);

  const canvasTraj = document.getElementById("chart-cash-trajectory");
  if (canvasTraj) {
    const existingTraj = Chart.getChart(canvasTraj);
    if (existingTraj) existingTraj.destroy();
    if (chartTrajectory) {
      try { chartTrajectory.destroy(); } catch (_) {}
      chartTrajectory = null;
    }

    const ctxTraj = canvasTraj.getContext("2d");
    const grad = ctxTraj.createLinearGradient(0, 0, 0, 300);
    grad.addColorStop(0, "rgba(91, 141, 239, 0.28)");
    grad.addColorStop(1, "rgba(91, 141, 239, 0.0)");

    chartTrajectory = new Chart(ctxTraj, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Paid on rule dates",
            data: trajectory,
            borderColor: "#5b8def",
            backgroundColor: grad,
            borderWidth: 2.5,
            fill: true,
            tension: 0.25,
            pointRadius: limit > 30 ? 1.5 : 3.5,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            filter: (item) => !item.dataset.hideTip,
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${fmtMoney(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.06)" },
            ticks: { color: "#8c93a3", font: { family: "JetBrains Mono", size: 10 }, maxTicksLimit: 12, maxRotation: 0, autoSkip: true },
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.06)" },
            ticks: {
              color: "#8c93a3",
              font: { family: "JetBrains Mono", size: 10 },
              callback: (val) => fmtMoney(val),
            },
          },
        },
      },
    });
    overlayMlTrajectory(chartTrajectory, currentRunId, limit);
    renderReceiptsOutlook(currentRunId, limit);
  }

  let arData = (analytics.ar_ap && Array.isArray(analytics.ar_ap.ar_trajectory) && analytics.ar_ap.ar_trajectory.length > 0)
    ? analytics.ar_ap.ar_trajectory.slice(0, limit)
    : (analytics.revenue_streams && analytics.revenue_streams["A/R Collection"] ? analytics.revenue_streams["A/R Collection"].slice(0, limit) : []);

  let apData = (analytics.ar_ap && Array.isArray(analytics.ar_ap.ap_trajectory) && analytics.ar_ap.ap_trajectory.length > 0)
    ? analytics.ar_ap.ap_trajectory.slice(0, limit)
    : (analytics.cogs_breakdown && analytics.cogs_breakdown["COGS Standard"] ? analytics.cogs_breakdown["COGS Standard"].slice(0, limit) : []);

  const canvasArAp = document.getElementById("chart-ar-ap-trajectory");
  if (canvasArAp) {
    const existingArAp = Chart.getChart(canvasArAp);
    if (existingArAp) existingArAp.destroy();
    if (chartArAp) {
      try { chartArAp.destroy(); } catch (_) {}
      chartArAp = null;
    }

    const ctxArAp = canvasArAp.getContext("2d");
    const gradAr = ctxArAp.createLinearGradient(0, 0, 0, 300);
    gradAr.addColorStop(0, "rgba(76, 195, 138, 0.30)");
    gradAr.addColorStop(1, "rgba(76, 195, 138, 0.0)");

    const gradAp = ctxArAp.createLinearGradient(0, 0, 0, 300);
    gradAp.addColorStop(0, "rgba(242, 103, 123, 0.30)");
    gradAp.addColorStop(1, "rgba(242, 103, 123, 0.0)");

    chartArAp = new Chart(ctxArAp, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Accounts Receivable (A/R Inflow)",
            data: arData,
            borderColor: "#4cc38a",
            backgroundColor: gradAr,
            borderWidth: 2.5,
            fill: true,
            tension: 0.25,
            pointRadius: limit > 30 ? 2 : 4,
            pointHoverRadius: 6,
          },
          {
            label: "Accounts Payable (A/P Outflow)",
            data: apData,
            borderColor: "#f2677b",
            backgroundColor: gradAp,
            borderWidth: 2.5,
            fill: true,
            tension: 0.25,
            pointRadius: limit > 30 ? 2 : 4,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            display: true,
            labels: { color: "#8c93a3", font: { size: 11, family: "Plus Jakarta Sans" } },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${fmtMoney(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.06)" },
            ticks: { color: "#8c93a3", font: { family: "JetBrains Mono", size: 10 }, maxTicksLimit: 12, maxRotation: 0, autoSkip: true },
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.06)" },
            ticks: {
              color: "#8c93a3",
              font: { family: "JetBrains Mono", size: 10 },
              callback: (val) => fmtMoney(val),
            },
          },
        },
      },
    });
  }

  const canvasIO = document.getElementById("chart-inflows-outflows");
  if (canvasIO) {
    const existingIO = Chart.getChart(canvasIO);
    if (existingIO) existingIO.destroy();
    if (chartInflowsOutflows) {
      try { chartInflowsOutflows.destroy(); } catch (_) {}
      chartInflowsOutflows = null;
    }

    const ctxIO = canvasIO.getContext("2d");
    chartInflowsOutflows = new Chart(ctxIO, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Inflows (Revenue)",
            data: inflows,
            backgroundColor: "#4cc38a",
            borderRadius: 3,
          },
          {
            label: "Outflows (COGS & Opex)",
            data: outflows,
            backgroundColor: "#f2677b",
            borderRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#8c93a3", font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${fmtMoney(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#8c93a3", font: { family: "JetBrains Mono", size: 9 }, maxTicksLimit: 13 },
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.06)" },
            ticks: {
              color: "#8c93a3",
              font: { family: "JetBrains Mono", size: 10 },
              callback: (val) => fmtMoney(val),
            },
          },
        },
      },
    });
  }

  const canvasRev = document.getElementById("chart-revenue-streams");
  if (canvasRev) {
    const existingRev = Chart.getChart(canvasRev);
    if (existingRev) existingRev.destroy();
    if (chartRevenueStreams) {
      try { chartRevenueStreams.destroy(); } catch (_) {}
      chartRevenueStreams = null;
    }

    const ctxRev = canvasRev.getContext("2d");
    chartRevenueStreams = new Chart(ctxRev, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        { label: "A/R Collection", data: revAR, backgroundColor: "#5b8def" },
        { label: "SERVPRO", data: revServpro, backgroundColor: "#a78bfa" },
        { label: "Amazon", data: revAmazon, backgroundColor: "#f5a524" },
        { label: "Other Resellers ($42k/wk)", data: revOther, backgroundColor: "#22d3ee" },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#8c93a3", font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${fmtMoney(ctx.parsed.y)}`,
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          grid: { display: false },
          ticks: { color: "#8c93a3", font: { family: "JetBrains Mono", size: 9 }, maxTicksLimit: 13 },
        },
        y: {
          stacked: true,
          grid: { color: "rgba(255, 255, 255, 0.06)" },
          ticks: {
            color: "#8c93a3",
            font: { family: "JetBrains Mono", size: 10 },
            callback: (val) => fmtMoney(val),
          },
        },
      },
    },
  });
  }
}

function onDragOver(e) {
  e.preventDefault();
  document.getElementById("dropzone").classList.add("dragover");
}

function onDragLeave(e) {
  e.preventDefault();
  document.getElementById("dropzone").classList.remove("dragover");
}

function onDrop(e) {
  e.preventDefault();
  document.getElementById("dropzone").classList.remove("dragover");
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    handleFiles(e.dataTransfer.files);
  }
}

function onFilesSelected(files) {
  if (files && files.length > 0) {
    handleFiles(files);
  }
}

function handleFiles(fileList) {
  selectedFiles = Array.from(fileList);
  const tagsContainer = document.getElementById("file-tags-list");
  tagsContainer.innerHTML = "";

  selectedFiles.forEach((file) => {
    let tag = "File";
    const fn = file.name.toLowerCase();
    if (fn.includes("invoice")) tag = "Invoices";
    else if (fn.includes("bill")) tag = "Bills";
    else if (fn.includes("sales") && fn.includes("order")) tag = "Sales Orders";
    else if (fn.includes("purchase") || fn.includes("po")) tag = "Purchase Orders";
    else if (fn.includes("bank")) tag = "Bank Statement";

    const el = document.createElement("div");
    el.className = "file-tag";
    el.innerHTML = `
      <span class="file-tag-name">${file.name}</span>
      <span class="file-tag-type">${tag}</span>
      <span class="file-tag-count">(${(file.size / 1024).toFixed(0)} KB)</span>
    `;
    tagsContainer.appendChild(el);
  });

  document.getElementById("detected-files-card").classList.remove("hidden");
  showToast(`Selected ${selectedFiles.length} files for ingestion.`, "info");
}

async function executeBatchUpload() {
  if (selectedFiles.length === 0) {
    showToast("Please drag & drop or select files first.", "warning");
    return;
  }

  const btn = document.getElementById("btn-execute-batch");
  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "⏳ Processing Ingestion & Matrix...";

  const formData = new FormData();
  selectedFiles.forEach((f) => formData.append("files", f));

  const ocVal = document.getElementById("batch-opening-cash").value;
  if (ocVal) formData.append("opening_cash", ocVal);

  const asOfVal = document.getElementById("batch-as-of").value;
  if (asOfVal) formData.append("as_of_date", asOfVal);

  try {
    const res = await fetch(`${API}/forecast/auto-run`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }
    const data = await res.json();
    currentRunId = data.run_id;
    showToast("Forecast generated successfully!", "success");
    await loadRuns();
    await loadRunDetails(currentRunId);
    showSection("dashboard");
  } catch (e) {
    showToast("Execution error: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = origText;
  }
}

async function runQuickDemo() {
  const btn = document.getElementById("btn-quick-demo");
  btn.textContent = "⏳ Calculating...";
  btn.disabled = true;
  try {
    const res = await fetch(`${API}/forecast/quick-demo`, { method: "POST" });
    if (!res.ok) throw new Error("Demo failed");
    const data = await res.json();
    currentRunId = data.run_id;
    showToast("August 31 forecast executed cleanly!", "success");
    await loadRuns();
    await loadRunDetails(currentRunId);
    showSection("dashboard");
  } catch (e) {
    showToast("Demo error: " + e.message, "error");
  } finally {
    btn.textContent = "⚡ Baseline (Aug 31)";
    btn.disabled = false;
  }
}

async function syncZohoLive() {
  const btn = document.getElementById("btn-sync-zoho");
  const origText = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
  }
  try {
    const d = document.getElementById("sync-date");
    const q = d && d.value ? `?run_date=${encodeURIComponent(d.value)}` : "";
    if (btn) btn.innerHTML = `⏳ Syncing${d && d.value ? " for " + fmtUSDate(fridayOnOrBefore(d.value)) : ""}…`;
    const res = await fetch(`${API}/forecast/sync-zoho-live${q}`, { method: "POST" });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Sync failed");
    }
    const data = await res.json();
    currentRunId = data.run_id;
    const bankStr = data.live_opening_cash ? ` (Live Bank: $${data.live_opening_cash.toLocaleString()})` : "";
    const archStr = data.archive_folder ? ` Zoho data archived in ${data.archive_folder.split(/[\\/]/).slice(-2).join("\\")}` : "";
    showToast(`Synced Live from Zoho Books!${bankStr}${archStr}`, "success");
    await loadRuns();
    document.getElementById("active-run-select").value = currentRunId;
    await loadRunDetails(currentRunId);
    showSection("dashboard");
  } catch (e) {
    showToast("Zoho Sync error: " + e.message, "error");
    checkZohoStatus();
  } finally {
    if (btn) {
      btn.innerHTML = origText;
      btn.disabled = false;
    }
  }
}
window.syncZohoLive = syncZohoLive;

async function loadMatrix(runId) {
  if (!runId) return;
  try {
    const res = await fetch(`${API}/runs/${runId}/matrix`);
    if (!res.ok) return;
    currentMatrixData = await res.json();
    renderMatrixTable(currentMatrixData, 52);
  } catch (e) {
    console.error(e);
  }
}

function onMatrixTimeframeChange(weeks) {
  if (currentMatrixData) {
    renderMatrixTable(currentMatrixData, parseInt(weeks, 10));
  }
}

function renderMatrixTable(matrixData, limit = 52) {
  const container = document.getElementById("matrix-container");
  if (!matrixData || !matrixData.weeks) {
    container.innerHTML = '<div class="empty-state">No matrix data.</div>';
    return;
  }
  if (!matrixData.layout) {
    renderMatrixTableLegacy(matrixData, limit);
    return;
  }
  const weeks = matrixData.weeks.slice(0, limit);
  const n = weeks.length;
  const fmtDate = (iso) => {
    if (!iso) return "";
    const [y, m, d] = iso.split("-");
    return `${m}/${d}/${y.slice(2)}`;
  };
  const cellTxt = (v) => {
    if (v === null || v === undefined || Math.abs(v) < 0.005) return "—";
    return fmtMoney(v);
  };

  let html = '<table class="matrix-table cfm" id="matrix-main-table"><thead><tr>';
  html += '<th class="sticky-col col-code">Code</th><th class="sticky-col col-acct">Account</th>';
  weeks.forEach((w) => { html += `<th class="col-week">${fmtDate(w.week_ending_friday)}</th>`; });
  html += "</tr></thead><tbody>";

  matrixData.layout.forEach((row) => {
    const kind = row.kind;
    if (kind === "section" || kind === "group") {
      html += `<tr class="cfm-${kind}"><td class="sticky-col col-code">${row.code || ""}</td>` +
              `<td class="sticky-col col-acct">${row.label}</td><td colspan="${n}"></td></tr>`;
      return;
    }
    const clickable = row.field && weeks.some((w) => {
      const c = w[row.field];
      return c && c.line_items && c.line_items.length;
    });
    html += `<tr class="cfm-${kind}"><td class="sticky-col col-code">${row.code || ""}</td>` +
            `<td class="sticky-col col-acct">${row.label}</td>`;
    for (let i = 0; i < n; i++) {
      const v = row.values[i];
      const neg = v < -0.005 ? " neg" : "";
      const c = row.field ? weeks[i][row.field] : null;
      const hasItems = clickable && c && c.line_items && c.line_items.length;
      const click = hasItems ? ` onclick="inspectCell(${i}, '${row.field}', '${row.label.replace(/'/g, "\\'")}')"` : "";
      html += `<td class="num${neg}${hasItems ? " has-items" : ""}"${click}>${cellTxt(v)}</td>`;
    }
    html += "</tr>";
  });
  html += "</tbody></table>";
  container.innerHTML = html;
}

function renderMatrixTableLegacy(matrixData, limit = 52) {
  const container = document.getElementById("matrix-container");
  if (!matrixData || !matrixData.weeks) {
    container.innerHTML = '<div class="empty-state">No matrix data.</div>';
    return;
  }

  const weeks = matrixData.weeks.slice(0, limit);
  const rowsConfig = [
    { key: "opening_cash", label: "Opening Cash Position", isTotal: true },
    { key: "header_rev", label: "REVENUES", isHeader: true },
    { key: "servpro_corporate", label: "SERVPRO Corporate", code: "1100.1" },
    { key: "other_resellers", label: "Other Resellers", code: "1100.2" },
    { key: "amazon", label: "Amazon", code: "1100.3" },
    { key: "adjustments", label: "Adjustments", code: "1101" },
    { key: "discount_given", label: "Discount Given", code: "1102" },
    { key: "freight_billed", label: "Freight Billed", code: "1103" },
    { key: "ar_collection", label: "A/R Collection", code: "AR" },
    { key: "total_revenue", label: "Total Revenue", isTotal: true },
    { key: "header_cogs", label: "COGS", isHeader: true },
    { key: "cogs_standard", label: "Cost of Goods Sold", code: "3100" },
    { key: "inbound_freight", label: "Inbound Freight", code: "3101" },
    { key: "inbound_duty", label: "Inbound Duty & Govt Fees", code: "3102" },
    { key: "total_cogs", label: "Total COGS", isTotal: true },
    { key: "header_ops", label: "OPERATIONS", isHeader: true },
    { key: "ops_amazon_fba", label: "Amazon FBA Fees", code: "2102" },
    { key: "ops_ea_salaries", label: "Operations Salaries", code: "2106" },
    { key: "ops_outbound_freight", label: "Outbound Freight Costs", code: "2107" },
    { key: "total_operations", label: "Total Operations", isTotal: true },
    { key: "gross_profit", label: "GROSS PROFIT", isTotal: true },
    { key: "total_marketing", label: "Total Marketing", isTotal: true },
    { key: "total_selling", label: "Total Selling", isTotal: true },
    { key: "total_finance_admin", label: "Total Finance & Admin", isTotal: true },
    { key: "total_it", label: "Total IT", isTotal: true },
    { key: "total_non_operating", label: "Total Non-Operating", isTotal: true },
    { key: "cc_payment_due", label: "Credit Card Payment Due" },
    { key: "loan_repayments", label: "Loan Repayments" },
    { key: "cc_charges_deferred", label: "CC Charges Deferred (non-cash)" },
    { key: "ending_cash", label: "Ending Cash Position", isTotal: true },
  ];

  let html = '<table class="matrix-table" id="matrix-main-table"><thead><tr>';
  html += '<th class="sticky-col">Account Line</th>';
  weeks.forEach((w) => {
    const d = w.week_ending_friday ? w.week_ending_friday.slice(5) : "";
    html += `<th>${d}</th>`;
  });
  html += "</tr></thead><tbody>";

  rowsConfig.forEach((cfg) => {
    if (cfg.isHeader) {
      html += `<tr class="header-row"><td class="sticky-col" colspan="${weeks.length + 1}">${cfg.label}</td></tr>`;
      return;
    }
    const rowClass = cfg.isTotal ? "total-row" : "";
    html += `<tr class="${rowClass}"><td class="sticky-col">${cfg.code ? `<span style="color:var(--text-muted);margin-right:6px;font-family:var(--font-mono);font-size:10px;">${cfg.code}</span>` : ""}${cfg.label}</td>`;

    weeks.forEach((w, wIdx) => {
      const val = w[cfg.key];
      let amt = 0;
      let cellObj = null;
      if (typeof val === "number") amt = val;
      else if (val && typeof val.amount === "number") {
        amt = val.amount;
        cellObj = val;
      }
      const amtStr = amt !== 0 ? fmtMoney(amt) : "—";
      const clickAttr = cellObj && cellObj.line_items && cellObj.line_items.length > 0 ? `onclick="inspectCell(${wIdx}, '${cfg.key}', '${cfg.label}')"` : "";
      html += `<td class="num" ${clickAttr}>${amtStr}</td>`;
    });
    html += "</tr>";
  });

  html += "</tbody></table>";
  container.innerHTML = html;
}

function filterMatrixTable() {
  const query = document.getElementById("matrix-search").value.toLowerCase();
  const rows = document.querySelectorAll("#matrix-main-table tbody tr");
  rows.forEach((r) => {
    if (r.classList.contains("header-row") || r.classList.contains("cfm-section") || r.classList.contains("cfm-group")) return;
    const text = r.textContent.toLowerCase();
    r.style.display = text.includes(query) ? "" : "none";
  });
}

function inspectCell(weekIdx, key, label) {
  if (!currentMatrixData || !currentMatrixData.weeks) return;
  const week = currentMatrixData.weeks[weekIdx];
  const cell = week[key];
  if (!cell || !cell.line_items) return;

  document.getElementById("modal-title").textContent = label;
  document.getElementById("modal-sub").textContent = `Week ending ${week.week_ending_friday} · Total: ${fmtMoney(cell.amount)}`;

  const body = document.getElementById("modal-body");
  body.innerHTML = cell.line_items
    .map(
      (li) => `
    <div class="drilldown-item">
      <div>
        <div class="drilldown-desc">${li.label || "Line Item"}</div>
        <div class="drilldown-ref">${li.raw_ref || "Direct ledger"}</div>
      </div>
      <div class="drilldown-amt">${fmtMoney(li.amount)}</div>
    </div>
  `
    )
    .join("");

  document.getElementById("drilldown-modal").classList.remove("hidden");
}

function closeDrilldown() {
  document.getElementById("drilldown-modal").classList.add("hidden");
}

async function loadConfigTable(table) {
  try {
    const res = await fetch(`${API}/config/${table}`);
    const data = await res.json();
    document.getElementById("config-json-textarea").value = JSON.stringify(data, null, 2);
  } catch (e) {
    showToast("Failed to load config: " + e.message, "error");
  }
}

async function saveActiveConfig() {
  const table = document.getElementById("config-table-select").value;
  try {
    const text = document.getElementById("config-json-textarea").value;
    const body = JSON.parse(text);
    const res = await fetch(`${API}/config/${table}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("Save failed");
    showToast("Configuration saved.", "success");
  } catch (e) {
    showToast("Error saving config: " + e.message, "error");
  }
}

function downloadCurrentRunExcel() {
  if (!currentRunId) {
    showToast("No active run selected.", "warning");
    return;
  }
  window.location.href = `${API}/runs/${currentRunId}/export/xlsx`;
}

// ---------- helpers: dates, run labels ----------
function pad2(n) { return String(n).padStart(2, "0"); }
function isoLocal(dt) { return `${dt.getFullYear()}-${pad2(dt.getMonth() + 1)}-${pad2(dt.getDate())}`; }
function fridayOnOrBefore(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() - ((dt.getDay() - 5 + 7) % 7));
  return isoLocal(dt);
}
function fmtUSDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${m}/${d}/${y.slice(2)}`;
}
function runLabel(r) {
  let when = "";
  if (r.created_at) {
    const c = new Date(r.created_at);
    const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    if (!isNaN(c)) when = ` · ${pad2(c.getDate())} ${MON[c.getMonth()]} ${pad2(c.getHours())}:${pad2(c.getMinutes())}`;
  }
  return `${fmtUSDate(r.run_date)}${when}`;
}

// ---------- Zoho connection status ----------
async function checkZohoStatus() {
  const b = document.getElementById("global-status");
  if (!b) return;
  b.className = "status-badge checking";
  b.textContent = "Checking Zoho…";
  try {
    const res = await fetch(`${API}/zoho/status`);
    const j = await res.json();
    b.className = "status-badge " + (j.ok ? "live" : "error");
    b.textContent = j.ok ? `Zoho connected · org ${j.org_id}` : "Zoho not connected";
    b.title = (j.message || "") + " — click to re-check";
  } catch (e) {
    b.className = "status-badge error";
    b.textContent = "Zoho status unknown";
    b.title = "Could not reach the forecast server — click to re-check";
  }
}
window.checkZohoStatus = checkZohoStatus;

// ---------- opening cash (bank balance override) ----------
async function openOpeningCash() {
  if (!currentRunId) { showToast("Select a run first.", "warning"); return; }
  try {
    const res = await fetch(`${API}/runs/${currentRunId}/opening-cash`);
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Not available"); }
    const j = await res.json();
    document.getElementById("oc-sub").textContent = `Forecast ${fmtUSDate(j.run_date)} (${currentRunId.slice(0, 6)})`;
    const rows = j.accounts.map((a) => `<tr><td>${a.name}</td><td class="num">${fmtMoney(a.balance, 2)}</td></tr>`).join("");
    const adj = (j.manual_adjustments || []).map((a) => `<tr><td>${a.label}</td><td class="num">${fmtMoney(a.amount, 2)}</td></tr>`).join("");
    document.getElementById("oc-table").innerHTML =
      rows + `<tr class="sub"><td>Zoho cash</td><td class="num">${fmtMoney(j.zoho_cash, 2)}</td></tr>` + adj +
      `<tr class="tot"><td>Opening cash in this forecast${j.override !== null ? " (bank override)" : ""}</td><td class="num">${fmtMoney(j.opening_cash, 2)}</td></tr>`;
    document.getElementById("oc-amount").value = j.override !== null ? j.override : "";
    document.getElementById("oc-date").value = (j.override_as_of || j.run_date || "").slice(0, 10);
    document.getElementById("opening-modal").classList.remove("hidden");
  } catch (e) {
    showToast("Opening cash: " + e.message, "error");
  }
}
function closeOpeningCash(ev) {
  if (ev && ev.target && ev.target.id !== "opening-modal") return;
  document.getElementById("opening-modal").classList.add("hidden");
}
async function postOpeningCash(amount, asOf) {
  const res = await fetch(`${API}/opening-cash`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount: amount, as_of_date: asOf, run_id: currentRunId, entered_by: "UI" }),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Save failed"); }
  document.getElementById("opening-modal").classList.add("hidden");
  await loadRunDetails(currentRunId);
}
async function applyOpeningCash() {
  const amt = parseFloat(document.getElementById("oc-amount").value);
  const asOf = document.getElementById("oc-date").value;
  if (isNaN(amt) || !asOf) { showToast("Enter the bank balance and its date.", "warning"); return; }
  try { await postOpeningCash(amt, asOf); showToast(`Opening cash set to ${fmtMoney(amt, 2)} for this run.`, "success"); }
  catch (e) { showToast("Opening cash: " + e.message, "error"); }
}
async function clearOpeningCash() {
  try { await postOpeningCash(0, document.getElementById("oc-date").value || isoLocal(new Date())); showToast("Opening cash back to Zoho cash + logged adjustments.", "success"); }
  catch (e) { showToast("Opening cash: " + e.message, "error"); }
}
window.openOpeningCash = openOpeningCash; window.closeOpeningCash = closeOpeningCash;
window.applyOpeningCash = applyOpeningCash; window.clearOpeningCash = clearOpeningCash;

// ---------- re-run from an archived snapshot ----------
async function rerunFromArchive(input) {
  const file = input.files && input.files[0];
  input.value = "";
  if (!file) return;
  const btn = document.getElementById("btn-rerun-archive");
  const orig = btn.innerHTML;
  btn.innerHTML = "⏳ Re-running…"; btn.disabled = true;
  try {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API}/forecast/run-from-snapshot`, { method: "POST", body: fd });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Re-run failed"); }
    const j = await res.json();
    currentRunId = j.run_id;
    await loadRuns();
    document.getElementById("active-run-select").value = currentRunId;
    await loadRunDetails(currentRunId);
    showToast(`Forecast rebuilt from ${file.name}.`, "success");
  } catch (e) {
    showToast("Re-run error: " + e.message, "error");
  } finally { btn.innerHTML = orig; btn.disabled = false; }
}
window.rerunFromArchive = rerunFromArchive;

// ---------- open the run's archive folder ----------
async function openRunArchive() {
  if (!currentRunId) { showToast("Select a run first.", "warning"); return; }
  try {
    const res = await fetch(`${API}/runs/${currentRunId}/open-archive`, { method: "POST" });
    const j = await res.json();
    if (!res.ok) throw new Error(j.detail || "No archive folder");
    showToast(j.opened ? "Archive folder opened." : `Archive folder: ${j.folder}`, j.opened ? "success" : "info");
  } catch (e) { showToast(e.message, "warning"); }
}
window.openRunArchive = openRunArchive;

document.addEventListener("DOMContentLoaded", () => {
  const sd = document.getElementById("sync-date");
  if (sd) sd.value = fridayOnOrBefore(isoLocal(new Date()));
  checkZohoStatus();
  loadRuns();
  loadConfigTable("assumptions");
});
