"""HTML-страница локального веб-интерфейса (одна страница, без внешних зависимостей)."""

INDEX_HTML = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Work Timer — отчёт</title>
<style>
  :root {
    --bg:#f8fafc; --fg:#0f172a; --muted:#475569; --card:#fff; --line:#94a3b8; --line2:#cbd5e1;
    --head:#fef08a; --head-off:#f1f5f9; --head-off-fg:#94a3b8; --sub:#bae6fd;
    --row:#fffbeb; --row-empty:#fffbeb80; --week:#ffe4e6; --btn-hover:#f1f5f9;
    --accent-bg:#eff6ff; --accent:#1d4ed8; --run:#dc2626; --pause:#d97706;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg:#0f172a; --fg:#e2e8f0; --muted:#94a3b8; --card:#1e293b; --line:#475569; --line2:#334155;
      --head:#854d0e; --head-off:#1e293b; --head-off-fg:#64748b; --sub:#0c4a6e;
      --row:#292524; --row-empty:#1c1917; --week:#4c0519; --btn-hover:#334155;
      --accent-bg:#1e3a8a; --accent:#bfdbfe; --run:#f87171; --pause:#fbbf24;
    }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.4 system-ui,sans-serif; }
  main { max-width:80rem; margin:0 auto; padding:16px; }
  .top { display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:16px; min-width:900px; }
  h1 { font-size:18px; margin:0 0 8px; }
  .nav { display:flex; gap:8px; flex-wrap:wrap; }
  button { background:var(--card); color:var(--fg); border:1px solid var(--line); border-radius:4px;
           padding:6px 12px; font:inherit; cursor:pointer; }
  button:hover:not(:disabled) { background:var(--btn-hover); }
  button:disabled { opacity:.5; cursor:default; }
  .total { background:var(--card); border:1px solid var(--line); border-radius:4px; padding:10px 24px; text-align:center; }
  .total .big { font-size:24px; font-weight:700; }
  .total .small { color:var(--muted); }
  #status { color:var(--muted); margin:8px 0; min-height:1.4em; }
  #status.err { color:var(--run); }
  .week { background:var(--card); border:1px solid var(--line); border-radius:4px; margin-top:16px; overflow-x:auto; }
  .days { display:grid; grid-template-columns:repeat(7,1fr); min-width:900px; }
  .day { border-right:1px solid var(--line); }
  .day:last-child { border-right:0; }
  .dh { background:var(--head); text-align:center; font-size:12px; font-weight:700; padding:6px 8px; border-bottom:1px solid var(--line); }
  .dh.off { background:var(--head-off); color:var(--head-off-fg); }
  .cols { display:grid; grid-template-columns:2fr 1fr; background:var(--sub); font-size:10px; font-weight:600;
          border-bottom:1px solid var(--line); }
  .cols div { text-align:center; padding:4px; }
  .cols div:first-child { border-right:1px solid var(--line2); }
  .t { display:grid; grid-template-columns:2fr 1fr; min-height:44px; font-size:11px; background:var(--row);
       border-bottom:1px solid var(--line2); }
  .t .task { border-right:1px solid var(--line2); padding:4px; font-weight:500; overflow-wrap:anywhere; }
  .t .dur { padding:4px; font-weight:600; white-space:nowrap; }
  .t.empty { background:var(--row-empty); }
  .run { color:var(--run); } .paused { color:var(--pause); }
  .wt { background:var(--week); border-top:1px solid var(--line); padding:6px 12px; }
  .wt b { font-weight:700; }
  #plan { background:var(--card); border:1px solid var(--line); border-radius:4px; padding:12px 16px; margin-top:12px; }
  #plan[hidden] { display:none; }
  #plan h2 { font-size:15px; margin:0 0 8px; }
  .plan-cols { display:flex; flex-wrap:wrap; gap:24px; }
  .plan-cols > div { flex:1 1 320px; }
  table.pl { border-collapse:collapse; width:100%; max-width:420px; }
  table.pl td, table.pl th { border:1px solid var(--line2); padding:3px 6px; text-align:left; }
  table.pl input { width:100%; background:var(--bg); color:var(--fg); border:1px solid var(--line2); border-radius:3px; padding:3px 5px; font:inherit; }
  textarea { width:100%; min-height:150px; background:var(--bg); color:var(--fg); border:1px solid var(--line2);
             border-radius:4px; padding:6px; font:12px/1.4 ui-monospace,monospace; }
  .hint { color:var(--muted); font-size:12px; margin:4px 0 8px; }
  .msg { margin-top:8px; min-height:1.4em; } .msg.err { color:var(--run); } .msg.ok { color:#16a34a; }
  input.yr { width:80px; background:var(--bg); color:var(--fg); border:1px solid var(--line); border-radius:4px; padding:5px; font:inherit; }
</style>
</head>
<body>
<main>
  <div class="top">
    <div>
      <h1 id="title">Месяц</h1>
      <div class="nav">
        <button id="prev">← Предыдущий</button>
        <button id="cur">Текущий</button>
        <button id="next">Следующий →</button>
        <button id="refresh">⟳ Обновить</button>
        <button id="planBtn">📅 Плановые часы</button>
      </div>
    </div>
    <div class="total">
      <div class="small">Время за месяц</div>
      <div class="big" id="mTotal">—</div>
      <div class="small" id="mDec"></div>
    </div>
  </div>
  <section id="plan" hidden>
    <h2>Плановые часы (производственный календарь)</h2>
    <div class="nav" style="margin-bottom:10px">
      <button id="pyPrev">←</button>
      <input class="yr" id="pYear" type="number" min="2000" max="2100">
      <button id="pyNext">→</button>
    </div>
    <div class="plan-cols">
      <div>
        <table class="pl"><thead><tr><th>Месяц</th><th>Рабочих дней</th><th>Часов</th></tr></thead>
          <tbody id="pBody"></tbody></table>
        <p style="margin:10px 0 0"><button id="pSave">Сохранить месяцы</button></p>
        <div class="hint">Сохраняются только строки, где заполнены оба поля; существующие месяцы обновляются.</div>
      </div>
      <div>
        <b>Импорт списком</b>
        <div class="hint">Строка = месяц. Форматы: <code>2026;1;15;120</code> · <code>2026-01 15 120</code> ·
          <code>1 15 120</code> (год — из поля слева). Разделители: <code>;</code>, табуляция или пробел;
          запятая в часах допустима (<code>175,5</code>). Строка-заголовок пропускается.
          При любой ошибке не сохраняется ничего.</div>
        <textarea id="pText" spellcheck="false" placeholder="2026;1;15;120&#10;2026;2;19;152"></textarea>
        <p style="margin:8px 0 0"><button id="pImport">Импортировать</button></p>
      </div>
    </div>
    <div class="msg" id="pMsg"></div>
  </section>
  <div id="status"></div>
  <div id="weeks"></div>
</main>
<script>
const MONTHS = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];
const DOW = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"];
let cur = new Date(); cur = new Date(cur.getFullYear(), cur.getMonth(), 1);
const $ = id => document.getElementById(id);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
const pad = n => String(n).padStart(2, "0");
const dayKey = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
const fmtHM = s => { const m = Math.round(s / 60); return `${Math.floor(m/60)}:${pad(m%60)}`; };
const fmtHMS = s => `${Math.floor(s/3600)}:${pad(Math.floor(s%3600/60))}:${pad(s%60)}`;
const dec = s => (s / 3600).toFixed(2);

async function load() {
  const y = cur.getFullYear(), m = cur.getMonth() + 1;
  $("title").textContent = `Месяц: ${MONTHS[m-1]} ${y}`;
  $("status").className = ""; $("status").textContent = "Загрузка…";
  ["prev","cur","next","refresh"].forEach(i => $(i).disabled = true);
  try {
    const res = await fetch(`/api/report?year=${y}&month=${m}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    render(data);
    $("status").textContent = "";
  } catch (e) {
    $("status").className = "err"; $("status").textContent = "Ошибка: " + e.message;
  } finally {
    ["prev","cur","next","refresh"].forEach(i => $(i).disabled = false);
  }
}

function render(data) {
  const y = data.year, m = data.month - 1;
  const byDay = {};
  for (const s of data.sessions) {
    const k = dayKey(new Date(s.start));
    (byDay[k] = byDay[k] || []).push(s);
  }
  const first = new Date(y, m, 1), last = new Date(y, m + 1, 0);
  let d = new Date(first); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); // понедельник
  const box = $("weeks"); box.replaceChildren();
  let monthTotal = 0;
  while (d <= last) {
    const wk = el("div", "week"), grid = el("div", "days");
    const wkStart = new Date(d); let wkTotal = 0;
    for (let i = 0; i < 7; i++, d.setDate(d.getDate() + 1)) {
      const inMonth = d.getMonth() === m;
      const list = inMonth ? (byDay[dayKey(d)] || []) : [];
      const total = list.reduce((a, s) => a + s.elapsed, 0);
      wkTotal += total;
      const col = el("div", "day");
      col.append(el("div", "dh" + (inMonth ? "" : " off"),
        `${DOW[i]} ${pad(d.getDate())}.${pad(d.getMonth()+1)}` + (inMonth && total ? ` · ${fmtHM(total)} ч` : "")));
      const cols = el("div", "cols"); cols.append(el("div", "", "Задача"), el("div", "", "Продолж."));
      col.append(cols);
      for (const s of list) {
        const row = el("div", "t");
        row.append(el("div", "task", s.task || "—"));
        const mark = s.status === "running" ? "▶ " : s.status === "paused" ? "⏸ " : "";
        row.append(el("div", "dur " + (s.status === "stopped" ? "" : s.status === "running" ? "run" : "paused"), mark + fmtHMS(s.elapsed)));
        col.append(row);
      }
      if (!list.length) col.append(el("div", "t empty"));
      grid.append(col);
    }
    monthTotal += wkTotal;
    const end = new Date(wkStart); end.setDate(end.getDate() + 6);
    const wt = el("div", "wt");
    wt.append("Итог за неделю (" + wkStart.toLocaleDateString("ru-RU") + " — " + end.toLocaleDateString("ru-RU") + "): ");
    wt.append(el("b", "", fmtHMS(wkTotal)), ` (${dec(wkTotal)} ч.)`);
    wk.append(grid, wt); box.append(wk);
  }
  $("mTotal").textContent = fmtHMS(monthTotal);
  const pct = data.planHours > 0 ? ` (${(monthTotal / 3600 / data.planHours * 100).toFixed(1)}%)` : "";
  $("mDec").textContent = `${dec(monthTotal)} ч.${pct}`;
}

// ---- плановые часы
let planYear = cur.getFullYear();
async function api(url, body) {
  const res = await fetch(url, body === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Requested-With": "work-timer"},
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
function pMsg(text, ok) { const m = $("pMsg"); m.className = "msg " + (ok ? "ok" : "err"); m.textContent = text; }
async function loadPlan() {
  $("pYear").value = planYear;
  const body = $("pBody"); body.replaceChildren();
  let rows = [];
  try { rows = (await api(`/api/plan?year=${planYear}`)).rows; } catch (e) { pMsg("Ошибка: " + e.message, false); }
  const byMonth = Object.fromEntries(rows.map(r => [r.month, r]));
  MONTHS.forEach((name, i) => {
    const r = byMonth[i + 1], tr = el("tr");
    tr.append(el("td", "", name));
    for (const [key, step] of [["work_days", "1"], ["work_hours", "0.01"]]) {
      const td = el("td"), inp = el("input");
      inp.type = "number"; inp.min = "0"; inp.step = step; inp.dataset.key = key;
      inp.value = r ? r[key] : "";
      td.append(inp); tr.append(td);
    }
    tr.dataset.month = i + 1; body.append(tr);
  });
}
async function planSave() {
  const rows = [];
  for (const tr of $("pBody").children) {
    const [d, h] = tr.querySelectorAll("input");
    if (d.value !== "" && h.value !== "")
      rows.push({year: planYear, month: +tr.dataset.month, work_days: +d.value, work_hours: +h.value});
  }
  if (!rows.length) return pMsg("Нет заполненных месяцев", false);
  await planSend("/api/plan", {rows}, rows.length);
}
async function planImport() {
  const text = $("pText").value;
  if (!text.trim()) return pMsg("Вставьте список", false);
  await planSend("/api/plan/import", {text, year: planYear});
}
async function planSend(url, payload) {
  try {
    const r = await api(url, payload);
    pMsg(`Сохранено месяцев: ${r.saved}`, true);
    await loadPlan(); load();
  } catch (e) { pMsg("Ошибка: " + e.message, false); }
}
$("planBtn").onclick = () => { const p = $("plan"); p.hidden = !p.hidden; if (!p.hidden) { planYear = cur.getFullYear(); loadPlan(); } };
$("pyPrev").onclick = () => { planYear--; loadPlan(); };
$("pyNext").onclick = () => { planYear++; loadPlan(); };
$("pYear").onchange = () => { const y = +$("pYear").value; if (y >= 2000 && y <= 2100) { planYear = y; loadPlan(); } };
$("pSave").onclick = planSave;
$("pImport").onclick = planImport;

$("prev").onclick = () => { cur = new Date(cur.getFullYear(), cur.getMonth() - 1, 1); load(); };
$("next").onclick = () => { cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1); load(); };
$("cur").onclick = () => { const n = new Date(); cur = new Date(n.getFullYear(), n.getMonth(), 1); load(); };
$("refresh").onclick = load;
setInterval(() => { if (!document.hidden) load(); }, 60000);
load();
</script>
</body>
</html>
"""
