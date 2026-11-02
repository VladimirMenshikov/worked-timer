"""HTML-страница «Статистика по проектам» (аналог /stats в ai-work-hours)."""

STATS_HTML = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Work Timer — статистика</title>
<style>
  :root { --bg:#f8fafc; --fg:#0f172a; --muted:#475569; --card:#fff; --line:#94a3b8; --track:#e2e8f0;
          --tile:#f8fafc; --btn-hover:#f1f5f9; --err:#dc2626; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f172a; --fg:#e2e8f0; --muted:#94a3b8; --card:#1e293b; --line:#475569; --track:#334155;
            --tile:#0f172a; --btn-hover:#334155; --err:#f87171; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.4 system-ui,sans-serif; }
  main { max-width:64rem; margin:0 auto; padding:16px; }
  .top { display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:16px; }
  h1 { font-size:18px; margin:0 0 8px; }
  .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:8px; }
  button, a.btn { background:var(--card); color:var(--fg); border:1px solid var(--line); border-radius:4px;
                  padding:6px 12px; font:inherit; cursor:pointer; text-decoration:none; }
  button:hover:not(:disabled), a.btn:hover { background:var(--btn-hover); }
  button:disabled { opacity:.5; cursor:default; }
  input[type=date] { background:var(--card); color:var(--fg); border:1px solid var(--line); border-radius:4px; padding:4px 6px; font:inherit; }
  .total { background:var(--card); border:1px solid var(--line); border-radius:4px; padding:10px 24px; text-align:center; }
  .total .big { font-size:24px; font-weight:700; } .muted { color:var(--muted); }
  #status { color:var(--muted); min-height:1.4em; margin:4px 0; } #status.err, .err { color:var(--err); }
  .card { background:var(--card); border:1px solid var(--line); border-radius:4px; padding:16px; margin-top:16px; }
  .stat { margin-bottom:16px; }
  .stat .h { display:flex; justify-content:space-between; gap:12px; margin-bottom:4px; }
  .stat .h b { overflow-wrap:anywhere; }
  .bar { height:16px; background:var(--track); border-radius:4px; }
  .bar > div { height:16px; border-radius:4px; }
  .tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px;
           border-top:1px solid var(--line); padding-top:16px; margin-top:8px; }
  .tile { background:var(--tile); border-radius:4px; padding:10px; text-align:center; }
  .tile .l { font-size:12px; color:var(--muted); } .tile .v { font-size:18px; font-weight:700; }
</style>
</head>
<body>
<main>
  <div class="top">
    <div>
      <h1 id="title">Статистика по проектам</h1>
      <div class="row">
        <button id="prev">← Предыдущий</button>
        <button id="cur">Текущий</button>
        <button id="next">Следующий →</button>
        <button id="refresh">⟳ Обновить</button>
        <a class="btn" href="/">← Назад к отчёту</a>
      </div>
      <div class="row">
        <span class="muted">Период:</span>
        <input type="date" id="from" aria-label="Дата начала"> <span>—</span>
        <input type="date" id="to" aria-label="Дата окончания">
        <button id="apply">Показать</button>
        <span class="err" id="rerr"></span>
      </div>
    </div>
    <div class="total">
      <div class="muted" id="tLabel">Время за месяц</div>
      <div class="big" id="tBig">—</div>
      <div class="muted" id="tDec"></div>
    </div>
  </div>
  <div id="status"></div>
  <div id="content"></div>
</main>
<script>
const MONTHS = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];
const COLORS = ["#3b82f6","#10b981","#f59e0b","#f43f5e","#a855f7","#06b6d4","#6366f1","#f97316","#ec4899","#14b8a6"];
const $ = id => document.getElementById(id);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
const pad = n => String(n).padStart(2, "0");
const fmtHMS = s => `${Math.floor(s/3600)}:${pad(Math.floor(s%3600/60))}:${pad(s%60)}`;
const dec = s => (s / 3600).toFixed(2);
const ruDate = v => v.split("-").reverse().join(".");
let cur = new Date(); cur = new Date(cur.getFullYear(), cur.getMonth(), 1);
let range = null; // {from, to} в формате YYYY-MM-DD; null — режим месяца

// Проект — часть названия задачи до первого «:».
function aggregate(sessions, start, end) {
  const totals = new Map(); let all = 0;
  for (const s of sessions) {
    const st = new Date(s.start);
    if (s.status !== "stopped" || s.elapsed <= 0 || st < start || st > end) continue;
    const full = s.task || "(без названия)";
    const name = full.split(":")[0].trim() || full;
    totals.set(name, (totals.get(name) || 0) + s.elapsed); all += s.elapsed;
  }
  return [...totals].map(([name, seconds]) => ({name, seconds, percent: all ? seconds / all * 100 : 0}))
    .sort((a, b) => b.seconds - a.seconds);
}

function render(stats, planHours) {
  const total = stats.reduce((a, s) => a + s.seconds, 0);
  const planPct = planHours > 0 ? (total / 3600 / planHours * 100).toFixed(1) : null;
  $("tLabel").textContent = range ? "Время за период" : "Время за месяц";
  $("tBig").textContent = fmtHMS(total);
  $("tDec").textContent = `${dec(total)} ч.` + (planPct ? ` (${planPct}%)` : "");
  const box = $("content"); box.replaceChildren();
  if (!stats.length) { box.append(el("p", "muted", "Нет данных за выбранный период.")); return; }
  const max = Math.max(...stats.map(s => s.seconds));
  const card = el("div", "card");
  stats.forEach((s, i) => {
    const row = el("div", "stat"), h = el("div", "h");
    h.append(el("b", "", s.name), el("span", "", `${dec(s.seconds)} ч. (${s.percent.toFixed(1)}%)`));
    const bar = el("div", "bar"), fill = el("div");
    fill.style.width = `${s.seconds / max * 100}%`; fill.style.background = COLORS[i % COLORS.length];
    fill.title = `${s.name}: ${s.percent.toFixed(1)}%`;
    bar.append(fill); row.append(h, bar); card.append(row);
  });
  const tiles = el("div", "tiles");
  const tile = (l, v) => { const t = el("div", "tile"); t.append(el("div", "l", l), el("div", "v", v)); tiles.append(t); };
  tile("Проектов", String(stats.length)); tile("Фактических часов", `${dec(total)} ч.`);
  if (planPct) tile("Выполнение плана", `${planPct}%`);
  card.append(tiles); box.append(card);
}

async function load() {
  let url, start, end, title;
  if (range) {
    const [fy, fm, fd] = range.from.split("-").map(Number), [ty, tm, td] = range.to.split("-").map(Number);
    start = new Date(fy, fm - 1, fd); end = new Date(ty, tm - 1, td, 23, 59, 59, 999);
    url = `/api/report?from=${range.from}&to=${range.to}`;
    title = `${ruDate(range.from)} – ${ruDate(range.to)}`;
  } else {
    const y = cur.getFullYear(), m = cur.getMonth();
    start = new Date(y, m, 1); end = new Date(y, m + 1, 0, 23, 59, 59, 999);
    url = `/api/report?year=${y}&month=${m + 1}`;
    title = `${MONTHS[m]} ${y}`;
  }
  $("title").textContent = "Статистика по проектам: " + title;
  $("status").className = ""; $("status").textContent = "Загрузка…";
  const btns = ["prev","cur","next","refresh","apply"]; btns.forEach(i => $(i).disabled = true);
  try {
    const res = await fetch(url), data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    render(aggregate(data.sessions, start, end), range ? null : data.planHours);
    $("status").textContent = "";
  } catch (e) {
    $("status").className = "err"; $("status").textContent = "Ошибка: " + e.message;
  } finally { btns.forEach(i => $(i).disabled = false); }
}

const goMonth = d => { range = null; $("rerr").textContent = ""; cur = d; load(); };
$("prev").onclick = () => goMonth(new Date(cur.getFullYear(), cur.getMonth() - 1, 1));
$("next").onclick = () => goMonth(new Date(cur.getFullYear(), cur.getMonth() + 1, 1));
$("cur").onclick = () => { const n = new Date(); goMonth(new Date(n.getFullYear(), n.getMonth(), 1)); };
$("refresh").onclick = load;
$("apply").onclick = () => {
  const f = $("from").value, t = $("to").value;
  if (!f || !t) { $("rerr").textContent = "Укажите обе даты"; return; }
  if (f > t) { $("rerr").textContent = "Дата начала позже даты окончания"; return; }
  $("rerr").textContent = ""; range = {from: f, to: t}; load();
};
setInterval(() => { if (!document.hidden) load(); }, 60000);
load();
</script>
</body>
</html>
"""
