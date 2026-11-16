"""Genera el reporte HTML autocontenido (sin dependencias externas, funciona offline).

Patrones tomados de herramientas de control horario (Dayforce, ADP, Indigo):
- Bandeja "por excepción": se revisa solo lo que falló, ordenado por severidad.
- Severidad con ícono + texto (nunca solo color): Alta = registro incompleto o
  ausencia, Media = desvío respecto del turno, Baja = aviso informativo.
- Mapa empleado × día para ver patrones (llegadas tarde repetidas, un día crítico).
- Línea de tiempo turno programado vs. tiempo trabajado para entender cada caso.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

FUENTE = Path(__file__).parent / "assets" / "inter-latin-wght.woff2"

PLANTILLA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Control de fichajes</title>
<style>
@font-face{font-family:"Inter var";font-style:normal;font-weight:100 900;font-display:swap;
  src:url(data:font/woff2;base64,__FUENTE__) format("woff2")}
:root{
  color-scheme:light;
  --page:#f3f5f8; --surface:#ffffff; --surface-2:#f8f9fb; --hover:#f1f4f8;
  --ink:#101828; --ink-2:#475467; --muted:#7a8494; --line:#e4e7ec; --grid:#eef0f4; --axis:#cfd4dc;
  --bar:#0e1726; --bar-ink:#e9eef5; --bar-muted:#8b97a8;
  --accent:#2a6fdb; --accent-soft:#e8f0fc;
  --alta:#d03b3b; --alta-soft:#fdecec; --alta-ink:#b42323;
  --media:#f2a50c; --media-soft:#fef4dc; --media-ink:#93600a;
  --baja:#2a78d6; --baja-soft:#e7f0fb; --baja-ink:#1f5fae;
  --ok:#14a34a; --ok-soft:#dff3e6; --ok-ink:#11743a;
  --worked:#2a78d6; --sched:#c9d3e1;
  --shadow:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.06);
}
@media (prefers-color-scheme:dark){
  :root:where(:not([data-theme="light"])){
    color-scheme:dark;
    --page:#0b0f15; --surface:#121821; --surface-2:#161d27; --hover:#1a2230;
    --ink:#e7ecf3; --ink-2:#a9b4c2; --muted:#7c8899; --line:#232d3b; --grid:#1c2531; --axis:#334052;
    --bar:#0a0e14; --accent:#5b9bf0; --accent-soft:#16243a;
    --alta:#e5544f; --alta-soft:#341a1c; --alta-ink:#f28b86;
    --media:#f2b02e; --media-soft:#33280f; --media-ink:#f5c45f;
    --baja:#3987e5; --baja-soft:#14243a; --baja-ink:#7fb0ef;
    --ok:#22b55a; --ok-soft:#12291c; --ok-ink:#5fd08a;
    --worked:#3987e5; --sched:#2c3a4e;
    --shadow:none;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --page:#0b0f15; --surface:#121821; --surface-2:#161d27; --hover:#1a2230;
  --ink:#e7ecf3; --ink-2:#a9b4c2; --muted:#7c8899; --line:#232d3b; --grid:#1c2531; --axis:#334052;
  --bar:#0a0e14; --accent:#5b9bf0; --accent-soft:#16243a;
  --alta:#e5544f; --alta-soft:#341a1c; --alta-ink:#f28b86;
  --media:#f2b02e; --media-soft:#33280f; --media-ink:#f5c45f;
  --baja:#3987e5; --baja-soft:#14243a; --baja-ink:#7fb0ef;
  --ok:#22b55a; --ok-soft:#12291c; --ok-ink:#5fd08a;
  --worked:#3987e5; --sched:#2c3a4e;
  --shadow:none;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);
  font:14px/1.5 "Inter var",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-feature-settings:"cv11","ss01";-webkit-font-smoothing:antialiased}
button,input,select{font:inherit;color:inherit}
.num{font-variant-numeric:tabular-nums}
svg.i{width:16px;height:16px;flex:none;vertical-align:-3px}

/* barra superior */
.top{background:var(--bar);color:var(--bar-ink)}
.top .in{max-width:1240px;margin:0 auto;padding:14px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;font-weight:650;letter-spacing:-.01em;font-size:15px}
.brand .mk{width:30px;height:30px;border-radius:8px;background:#2a6fdb;display:grid;place-items:center}
.top .meta{color:var(--bar-muted);font-size:12.5px;display:flex;gap:6px 16px;flex-wrap:wrap;margin-left:auto;align-items:center}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid #273244;border-radius:999px;padding:3px 10px;color:var(--bar-ink)}
.chip .dot{width:7px;height:7px;border-radius:50%;background:#22b55a}
.chip.warn .dot{background:#f2a50c}
.theme{background:none;border:1px solid #273244;border-radius:8px;color:var(--bar-ink);padding:5px 9px;cursor:pointer;display:inline-flex;gap:6px;align-items:center}
.theme:hover{background:#18212f}

.wrap{max-width:1240px;margin:0 auto;padding:22px 20px 64px}
.head{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.head h1{margin:0;font-size:22px;letter-spacing:-.02em;font-weight:680}
.head p{margin:2px 0 0;color:var(--ink-2)}

.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow)}
.card>.hd{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;padding:14px 16px 0}
.card>.hd h2{margin:0;font-size:14px;font-weight:620;letter-spacing:-.005em}
.card>.hd .sub{color:var(--muted);font-size:12.5px}
.card>.bd{padding:14px 16px 16px}

/* KPIs */
.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-bottom:14px}
@media (max-width:1000px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.kpis .kpi:first-child{grid-column:1/-1}}
.kpi{padding:14px 16px}
.kpi .lb{display:flex;align-items:center;gap:7px;color:var(--ink-2);font-size:12.5px;font-weight:520}
.kpi .v{font-size:28px;font-weight:680;letter-spacing:-.025em;margin-top:6px;line-height:1.1}
.kpi .v small{font-size:14px;color:var(--muted);font-weight:520;letter-spacing:0;margin-left:4px}
.kpi .ft{color:var(--muted);font-size:12px;margin-top:4px}
.meter{height:6px;border-radius:3px;background:var(--grid);margin-top:10px;overflow:hidden;display:flex;gap:2px}
.meter i{display:block;height:100%}
.kpi.alta .lb svg{color:var(--alta)} .kpi.media .lb svg{color:var(--media)} .kpi.baja .lb svg{color:var(--baja)}
.kpi.ok .lb svg{color:var(--ok)}

.row{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(0,1fr);gap:14px;margin-bottom:14px}
@media (max-width:900px){.row{grid-template-columns:minmax(0,1fr)}}

/* gráfico de barras apiladas */
.row>.card{display:flex;flex-direction:column}
.row>.card>.bd{flex:1;display:flex;flex-direction:column}
.chart{position:relative;flex:1;min-height:210px;margin-left:28px}
.chart .gl{position:absolute;left:0;right:0;border-top:1px solid var(--grid)}
.chart .gl span{position:absolute;left:-28px;top:-8px;width:22px;text-align:right;font-size:11px;color:var(--muted)}
.chart .gl.base{border-top-color:var(--axis)}
.cols{position:absolute;inset:0;display:flex;align-items:flex-end;gap:3px}
.col{flex:1;height:100%;display:flex;flex-direction:column-reverse;gap:2px;cursor:pointer;border-radius:4px 4px 0 0;position:relative}
.col.we::before{content:"";position:absolute;inset:0 -1.5px;background:var(--surface-2);z-index:0}
.col span{display:block;position:relative;z-index:1}
.col span:last-child{border-radius:4px 4px 0 0}
.col .a{background:var(--alta)} .col .m{background:var(--media)} .col .b{background:var(--baja)}
.col:hover span{filter:brightness(1.08)}
.col.sel{outline:2px solid var(--accent);outline-offset:2px}
.xax{display:flex;gap:3px;margin:6px 0 0 28px;font-size:11px;color:var(--muted);overflow:hidden}
.xax div{flex:1;min-width:0;white-space:nowrap;overflow:visible}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--ink-2)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{width:10px;height:10px;border-radius:3px;display:inline-block}

/* por tipo */
.types{display:flex;flex-direction:column;gap:2px}
.type{display:grid;grid-template-columns:minmax(0,1fr) 40px;align-items:center;gap:4px 10px;padding:7px 8px;border-radius:8px;cursor:pointer;border:1px solid transparent}
.type:hover{background:var(--hover)}
.type.on{background:var(--accent-soft);border-color:color-mix(in srgb,var(--accent) 35%,transparent)}
.type .nm{display:flex;align-items:center;gap:8px;font-size:13px;min-width:0}
.type .nm b{font-weight:520;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.type .n{text-align:right;font-weight:600;font-size:13px}
.type .tr{grid-column:1/-1;height:6px;border-radius:3px;background:var(--grid);overflow:hidden}
.type .tr i{display:block;height:100%;border-radius:3px}

/* mapa empleado × día */
.hm{overflow-x:auto}
.hm table{border-collapse:separate;border-spacing:3px;width:100%;min-width:640px}
.hm th{font-size:11px;color:var(--muted);font-weight:500;padding:0 0 4px;text-align:center;white-space:nowrap}
.hm th.wd{color:var(--ink-2)}
.hm td.who{white-space:nowrap;padding-right:10px;font-size:13px;text-align:left;width:1%}
.hm td.who b{font-weight:560}
.hm td.who span{color:var(--muted);font-size:11.5px;margin-left:4px}
.hm td.c{height:26px;min-width:16px;border-radius:5px;cursor:pointer;background:var(--grid);position:relative}
.hm td.c.ok{background:var(--ok-soft);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--ok) 30%,transparent)}
.hm td.c.alta{background:var(--alta)} .hm td.c.media{background:var(--media)} .hm td.c.baja{background:var(--baja)}
.hm td.c.off{background:repeating-linear-gradient(135deg,transparent 0 4px,var(--grid) 4px 5px)}
.hm td.c:hover{outline:2px solid var(--ink);outline-offset:1px}
.hm td.c.n::after{content:attr(data-n);position:absolute;inset:0;display:grid;place-items:center;font-size:10.5px;font-weight:650;color:#fff}
.hm td.c.media.n::after{color:#1a1204}
.hm td.tot{font-size:12px;color:var(--ink-2);text-align:right;padding-left:8px;white-space:nowrap;width:1%}

/* bandeja */
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line)}
.seg{display:inline-flex;flex-wrap:wrap;max-width:100%;background:var(--surface-2);border:1px solid var(--line);border-radius:9px;padding:2px}
.seg button{border:0;background:none;padding:5px 12px;border-radius:7px;cursor:pointer;color:var(--ink-2);font-weight:520;font-size:13px;display:inline-flex;gap:6px;align-items:center}
.seg button.on{background:var(--surface);color:var(--ink);box-shadow:var(--shadow)}
.seg button .ct{font-size:11.5px;color:var(--muted);font-weight:500}
.search{flex:1;min-width:200px;position:relative}
.search svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--muted)}
.toolbar .search input[type=search]{width:100%;padding:7px 10px 7px 32px}
.toolbar input[type=search],.toolbar select{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:7px 10px;outline:none}
.toolbar input:focus,.toolbar select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.toggle{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--ink-2);cursor:pointer;user-select:none}
.pills{display:flex;gap:6px;flex-wrap:wrap;padding:8px 16px 0}
.pill{display:inline-flex;gap:6px;align-items:center;background:var(--accent-soft);color:var(--accent);border-radius:999px;padding:3px 6px 3px 10px;font-size:12px;font-weight:550}
.pill button{border:0;background:none;cursor:pointer;color:inherit;padding:0 3px;font-size:14px;line-height:1}

.tbl{overflow-x:auto}
table.t{width:100%;border-collapse:collapse;font-size:13px}
table.t th{text-align:left;font-size:11.5px;font-weight:560;color:var(--muted);padding:10px 12px;border-bottom:1px solid var(--line);white-space:nowrap;cursor:pointer;user-select:none;background:var(--surface-2)}
table.t th:hover{color:var(--ink)}
table.t td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:middle}
table.t tbody tr{cursor:pointer}
table.t tbody tr:hover td{background:var(--hover)}
table.t tr.done td{opacity:.55}
table.t tr.done td:first-child{opacity:1}
.sev{display:inline-flex;align-items:center;gap:6px;font-weight:560;font-size:12.5px;white-space:nowrap}
.sev.alta{color:var(--alta-ink)} .sev.media{color:var(--media-ink)} .sev.baja{color:var(--baja-ink)} .sev.ok{color:var(--ok-ink)}
.sev.alta svg{color:var(--alta)} .sev.media svg{color:var(--media)} .sev.baja svg{color:var(--baja)} .sev.ok svg{color:var(--ok)}
.who{white-space:nowrap} .who b{font-weight:560} .who span{color:var(--muted);font-size:12px;margin-left:4px}
.nw{white-space:nowrap}
.det{color:var(--ink-2);max-width:440px}
.marks{display:flex;gap:4px;flex-wrap:wrap}
.mk{font-size:11.5px;font-variant-numeric:tabular-nums;background:var(--surface-2);border:1px solid var(--line);border-radius:5px;padding:1px 6px;color:var(--ink-2)}
.cb{width:16px;height:16px;accent-color:var(--accent);cursor:pointer}
.more{display:block;margin:12px auto 4px;border:1px solid var(--line);background:var(--surface);border-radius:9px;padding:7px 16px;cursor:pointer;font-weight:550}
.more:hover{background:var(--hover)}
.foot{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px 16px;color:var(--muted);font-size:12.5px}
.empty{padding:40px 16px;text-align:center;color:var(--muted)}
.empty b{display:block;color:var(--ink);font-size:15px;margin-bottom:4px}

/* tooltip */
.tip{position:fixed;z-index:50;pointer-events:none;background:var(--bar);color:#e9eef5;border-radius:8px;padding:8px 10px;font-size:12.5px;
  box-shadow:0 8px 24px rgba(0,0,0,.25);max-width:260px;opacity:0;transition:opacity .08s}
.tip.on{opacity:1}
.tip b{display:block;font-weight:600;margin-bottom:3px}
.tip .r{display:flex;align-items:center;gap:7px;color:#c6cfdb}
.tip .r i{width:8px;height:8px;border-radius:2px;display:inline-block}

/* panel lateral */
.scrim{position:fixed;inset:0;background:rgba(8,12,18,.35);opacity:0;pointer-events:none;transition:opacity .15s;z-index:40}
.scrim.on{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;bottom:0;width:min(520px,100vw);background:var(--surface);border-left:1px solid var(--line);
  transform:translateX(100%);transition:transform .2s ease,visibility .2s;visibility:hidden;z-index:45;display:flex;flex-direction:column}
.drawer.on{transform:none;visibility:visible;box-shadow:-12px 0 32px rgba(0,0,0,.12)}
.drawer .dh{padding:18px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:12px}
.drawer .dh h3{margin:0;font-size:17px;letter-spacing:-.01em}
.drawer .dh p{margin:2px 0 0;color:var(--ink-2)}
.drawer .x{border:1px solid var(--line);background:var(--surface);border-radius:8px;width:32px;height:32px;cursor:pointer;display:grid;place-items:center;flex:none}
.drawer .db{padding:18px 20px;overflow-y:auto;display:flex;flex-direction:column;gap:20px}
.drawer h4{margin:0 0 10px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600}
.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.fact{background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.fact .k{font-size:11.5px;color:var(--muted)} .fact .v{font-size:16px;font-weight:620;margin-top:2px}
.tl{position:relative;padding-left:76px}
.tl .ln{position:relative;height:26px;margin-bottom:8px;background:var(--surface-2);border-radius:6px}
.tl .ln::before{content:attr(data-l);position:absolute;left:-76px;top:4px;font-size:12px;color:var(--ink-2);width:70px}
.tl .sch{position:absolute;top:3px;bottom:3px;border-radius:5px;background:repeating-linear-gradient(135deg,var(--sched) 0 5px,transparent 5px 9px);
  box-shadow:inset 0 0 0 1.5px var(--sched)}
.tl .wk{position:absolute;top:3px;bottom:3px;border-radius:5px;background:var(--worked)}
.tl .pm{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink);border-radius:1px}
.tl .pm.miss{background:var(--alta);width:3px}
.tl .ax{position:relative;height:18px;font-size:11px;color:var(--muted)}
.tl .ax span{position:absolute;transform:translateX(-50%)}
.tl .ax span:first-child{transform:none}
.tl .ax span:last-child{transform:translateX(-100%)}
.tl .gr{position:absolute;top:0;bottom:22px;width:1px;background:var(--grid)}
.alist{display:flex;flex-direction:column;gap:8px}
.aitem{border:1px solid var(--line);border-radius:10px;padding:10px 12px;display:grid;grid-template-columns:auto 1fr;gap:4px 10px;align-items:start}
.aitem .sev{grid-row:span 2;padding-top:1px}
.aitem b{font-weight:600} .aitem p{margin:0;color:var(--ink-2);font-size:13px}
.okbox{border:1px solid var(--line);border-radius:10px;padding:12px;color:var(--ok-ink);background:var(--ok-soft);display:flex;gap:8px;align-items:center}
@media print{.top,.toolbar,.drawer,.scrim{display:none}}
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="i-alta" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M15 9l-6 6M9 9l6 6" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></symbol>
  <symbol id="i-media" viewBox="0 0 24 24"><path d="M10.3 3.6 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0Z" fill="currentColor"/><path d="M12 9v4.5" stroke="#1a1204" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="17" r="1.25" fill="#1a1204"/></symbol>
  <symbol id="i-baja" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M12 11v6" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="7.5" r="1.3" fill="#fff"/></symbol>
  <symbol id="i-ok" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="m7.5 12.5 3 3 6-6.5" stroke="#fff" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="i-clock" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M12 7.5V12l3 2" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="m20 20-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></symbol>
  <symbol id="i-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="2" fill="none"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></symbol>
  <symbol id="i-users" viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5M16 4.8a3.5 3.5 0 0 1 0 6.4M18.5 14.8c1.6.8 2.6 2.6 3 5.2" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></symbol>
</svg>

<div class="top"><div class="in">
  <div class="brand"><span class="mk"><svg class="i" style="width:18px;height:18px;color:#fff"><use href="#i-clock"/></svg></span>Control de fichajes</div>
  <div class="meta">
    <span class="chip" id="fuente"><span class="dot"></span><span></span></span>
    <span id="generado"></span>
    <button class="theme" id="theme" title="Cambiar tema"><svg class="i"><use href="#i-sun"/></svg><span>Auto</span></button>
  </div>
</div></div>

<div class="wrap">
  <div class="head">
    <div><h1>Resumen de asistencia</h1><p id="periodo"></p></div>
    <div class="legend" id="legend-top"></div>
  </div>

  <section class="kpis" id="kpis"></section>

  <section class="row">
    <div class="card">
      <div class="hd"><h2>Anomalías por jornada</h2><span class="sub">Tocá una barra para filtrar el día</span></div>
      <div class="bd">
        <div class="chart" id="chart"></div>
        <div class="xax" id="xax"></div>
        <div class="legend" style="margin-top:12px" id="legend-chart"></div>
      </div>
    </div>
    <div class="card">
      <div class="hd"><h2>Por tipo de anomalía</h2><span class="sub" id="tipos-sub"></span></div>
      <div class="bd"><div class="types" id="types"></div></div>
    </div>
  </section>

  <section class="card" style="margin-bottom:14px">
    <div class="hd"><h2>Mapa de asistencia</h2><span class="sub">Peor severidad de cada jornada · tocá una celda para ver el detalle</span></div>
    <div class="bd">
      <div class="hm" id="hm"></div>
      <div class="legend" style="margin-top:12px" id="legend-hm"></div>
    </div>
  </section>

  <section class="card">
    <div class="hd" style="padding-bottom:12px"><h2>Bandeja de revisión</h2><span class="sub" id="pend"></span></div>
    <div class="toolbar">
      <div class="seg" id="tabs"><button data-tab="anom" class="on">Anomalías</button><button data-tab="dias">Todas las jornadas</button></div>
      <div class="seg" id="sevs"></div>
      <div class="search"><svg class="i"><use href="#i-search"/></svg><input id="q" type="search" placeholder="Buscar empleado, legajo o detalle"></div>
      <select id="fEmp"><option value="">Todos los empleados</option></select>
      <label class="toggle"><input type="checkbox" class="cb" id="hideDone"> Ocultar revisadas</label>
    </div>
    <div class="pills" id="pills"></div>
    <div class="tbl"><table class="t" id="tabla"></table></div>
    <div id="masWrap"></div>
    <div class="foot"><span id="nota"></span><span>Las marcas de "revisada" se guardan en este navegador.</span></div>
  </section>
</div>

<div class="tip" id="tip"></div>
<div class="scrim" id="scrim"></div>
<aside class="drawer" id="drawer" aria-hidden="true">
  <div class="dh"><div><h3 id="dTitle"></h3><p id="dSub"></p></div><button class="x" id="dClose" aria-label="Cerrar"><svg class="i"><use href="#i-x"/></svg></button></div>
  <div class="db" id="dBody"></div>
</aside>

<script>
const DATA = __DATA__;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const SEV = {alta:{l:"Alta", n:0}, media:{l:"Media", n:1}, baja:{l:"Baja", n:2}, ok:{l:"OK", n:3}};
const ico = (k, cls="i") => `<svg class="${cls}"><use href="#i-${k}"/></svg>`;
const sevTag = s => `<span class="sev ${s}">${ico(s)}${SEV[s].l}</span>`;
const DIAS = ["dom","lun","mar","mié","jue","vie","sáb"];
const dt = iso => new Date(iso + "T12:00:00");
const fDia = iso => { const d = dt(iso); return `${DIAS[d.getDay()]} ${iso.slice(8)}/${iso.slice(5,7)}`; };
const fLargo = iso => dt(iso).toLocaleDateString("es-AR", {weekday:"long", day:"numeric", month:"long"});
const fmt = n => n.toLocaleString("es-AR");
const store = {
  get(k, d){ try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch {} }
};

// ---------- tema ----------
const temas = ["auto","light","dark"], nombresTema = {auto:"Auto", light:"Claro", dark:"Oscuro"};
let tema = store.get("cf-tema", "auto");
function aplicarTema(){ if (tema === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", tema);
  $("#theme span").textContent = nombresTema[tema]; }
$("#theme").onclick = () => { tema = temas[(temas.indexOf(tema) + 1) % 3]; store.set("cf-tema", tema); aplicarTema(); };
aplicarTema();

// ---------- cabecera ----------
const fallo = /falló/.test(DATA.fuente);
$("#fuente").classList.toggle("warn", fallo);
$("#fuente span:last-child").textContent = DATA.fuente;
$("#generado").textContent = "Actualizado " + DATA.generado;
$("#periodo").textContent = DATA.periodo;

// ---------- índices ----------
const A = DATA.anomalias.map((a, i) => ({...a, id: a.legajo + "|" + a.jornada + "|" + a.tipo + "|" + i}));
const byDay = {}; A.forEach(a => (byDay[a.legajo + "|" + a.jornada] ??= []).push(a));
const diaIdx = {}; DATA.dias.forEach(d => diaIdx[d.legajo + "|" + d.jornada] = d);
const worst = list => list.reduce((w, a) => SEV[a.severidad].n < SEV[w].n ? a.severidad : w, "ok");
const nombres = {}; DATA.dias.concat(A).forEach(r => { if (r.nombre) nombres[r.legajo] = r.nombre; });
const legajos = [...new Set(DATA.dias.map(d => d.legajo).concat(A.map(a => a.legajo)))]
  .sort((a, b) => (nombres[a] || a).localeCompare(nombres[b] || b));
const quien = l => nombres[l] ? `<b>${esc(nombres[l])}</b><span>#${esc(l)}</span>` : `<b>#${esc(l)}</b>`;
const quienTxt = l => (nombres[l] ? nombres[l] + " " : "") + "#" + l;
let revisadas = new Set(store.get("cf-revisadas", []));
const guardarRev = () => store.set("cf-revisadas", [...revisadas]);
const claveRev = a => a.legajo + "|" + a.jornada + "|" + a.tipo;

const rango = []; for (let d = dt(DATA.rango[0]), f = dt(DATA.rango[1]); d <= f; d.setDate(d.getDate() + 1))
  rango.push(d.toISOString().slice(0, 10));

// ---------- estado de filtros ----------
const F = {tab:"anom", sev:"", tipo:"", dia:"", emp:"", q:"", ocultar:false, col:null, asc:true, ver:25};

// ---------- tooltip ----------
const tip = $("#tip");
function showTip(e, html){ tip.innerHTML = html; tip.classList.add("on");
  const r = tip.getBoundingClientRect(); let x = e.clientX + 14, y = e.clientY + 14;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
  tip.style.left = x + "px"; tip.style.top = y + "px"; }
const hideTip = () => tip.classList.remove("on");

// ---------- KPIs ----------
function kpis(){
  const n = s => A.filter(a => a.severidad === s).length;
  const jornadas = DATA.dias.length;
  const limpias = DATA.dias.filter(d => !byDay[d.legajo + "|" + d.jornada]).length;
  const pct = jornadas ? Math.round(limpias / jornadas * 100) : 100;
  const horas = DATA.dias.reduce((s, d) => s + (d.horas || 0), 0);
  const pend = A.filter(a => !revisadas.has(claveRev(a))).length;
  const tot = A.length || 1;
  $("#kpis").innerHTML = `
    <div class="card kpi ok"><div class="lb">${ico("ok")}Jornadas sin anomalías</div>
      <div class="v num">${pct}%<small>${fmt(limpias)} de ${fmt(jornadas)}</small></div>
      <div class="meter"><i style="width:${pct}%;background:var(--ok)"></i></div></div>
    <div class="card kpi alta"><div class="lb">${ico("alta")}Severidad alta</div><div class="v num">${n("alta")}</div>
      <div class="ft">Registros incompletos y ausencias</div></div>
    <div class="card kpi media"><div class="lb">${ico("media")}Severidad media</div><div class="v num">${n("media")}</div>
      <div class="ft">Desvíos respecto del turno</div></div>
    <div class="card kpi baja"><div class="lb">${ico("baja")}Severidad baja</div><div class="v num">${n("baja")}</div>
      <div class="ft">Avisos para controlar</div></div>
    <div class="card kpi"><div class="lb">${ico("users")}Personal y horas</div>
      <div class="v num">${legajos.length}<small>empleados</small></div>
      <div class="ft num">${fmt(Math.round(horas))} h trabajadas · ${pend} sin revisar</div></div>`;
  $("#pend").textContent = `${pend} de ${A.length} anomalías sin revisar`;
}

// ---------- leyendas ----------
const leg = (k, extra="") => `<span><i style="background:var(--${k})"></i>${extra || SEV[k].l}</span>`;
$("#legend-chart").innerHTML = leg("alta") + leg("media") + leg("baja");
$("#legend-hm").innerHTML = `<span><i style="background:var(--ok-soft);box-shadow:inset 0 0 0 1px var(--ok)"></i>Sin anomalías</span>` +
  leg("alta") + leg("media") + leg("baja") +
  `<span><i style="background:repeating-linear-gradient(135deg,transparent 0 3px,var(--axis) 3px 4px)"></i>Sin fichajes ni turno</span>`;

// ---------- gráfico por día ----------
function chart(){
  const per = {}; rango.forEach(d => per[d] = {alta:0, media:0, baja:0});
  A.forEach(a => per[a.jornada] && per[a.jornada][a.severidad]++);
  const tot = d => per[d].alta + per[d].media + per[d].baja;
  const max = Math.max(1, ...rango.map(tot));
  const paso = max <= 4 ? 1 : max <= 8 ? 2 : max <= 20 ? 5 : 10;
  const tope = Math.ceil(max / paso) * paso;
  let g = "";
  for (let v = 0; v <= tope; v += paso)
    g += `<div class="gl ${v === 0 ? "base" : ""}" style="bottom:${v / tope * 100}%"><span class="num">${v}</span></div>`;
  const cols = rango.map(d => { const p = per[d], we = [0,6].includes(dt(d).getDay());
    const seg = k => p[k] ? `<span class="${k[0]}" style="height:calc(${p[k] / tope * 100}% - 2px)"></span>` : "";
    return `<div class="col ${we ? "we" : ""} ${F.dia === d ? "sel" : ""}" data-d="${d}">${seg("alta")}${seg("media")}${seg("baja")}</div>`; }).join("");
  $("#chart").innerHTML = g + `<div class="cols">${cols}</div>`;
  const cada = Math.ceil(rango.length / (innerWidth < 600 ? 4 : 8));
  $("#xax").innerHTML = rango.map((d, i) => `<div>${i % cada === 0 ? d.slice(8) + "/" + d.slice(5,7) : ""}</div>`).join("");
  document.querySelectorAll(".col").forEach(c => {
    const d = c.dataset.d, p = per[d];
    c.onmousemove = e => showTip(e, `<b>${fDia(d)} · ${tot(d)} anomalía${tot(d) === 1 ? "" : "s"}</b>` +
      ["alta","media","baja"].filter(k => p[k]).map(k => `<div class="r"><i style="background:var(--${k})"></i>${SEV[k].l}: ${p[k]}</div>`).join(""));
    c.onmouseleave = hideTip;
    c.onclick = () => { F.dia = F.dia === d ? "" : d; F.tab = "anom"; render(); };
  });
}

// ---------- por tipo ----------
function tipos(){
  const t = {}; A.forEach(a => { (t[a.tipo] ??= {n:0, titulo:a.titulo, sev:a.severidad}).n++; });
  const lista = Object.entries(t).sort((x, y) => SEV[x[1].sev].n - SEV[y[1].sev].n || y[1].n - x[1].n);
  const max = Math.max(1, ...lista.map(([, v]) => v.n));
  $("#tipos-sub").textContent = `${A.length} en total`;
  $("#types").innerHTML = lista.map(([k, v]) => `<div class="type ${F.tipo === k ? "on" : ""}" data-t="${k}">
      <div class="nm"><span class="sev ${v.sev}">${ico(v.sev)}</span><b>${esc(v.titulo)}</b></div><div class="n num">${v.n}</div>
      <div class="tr"><i style="width:${v.n / max * 100}%;background:var(--${v.sev})"></i></div></div>`).join("")
    || `<div class="empty"><b>Sin anomalías</b>Todo en orden en el período.</div>`;
  document.querySelectorAll(".type").forEach(el => el.onclick = () => { F.tipo = F.tipo === el.dataset.t ? "" : el.dataset.t; F.tab = "anom"; render(); });
}

// ---------- mapa empleado × día ----------
function mapa(){
  const head = `<tr><th></th>${rango.map(d => { const w = dt(d).getDay();
    return `<th class="${w === 1 ? "wd" : ""}">${DIAS[w][0].toUpperCase()}<br>${d.slice(8)}</th>`; }).join("")}<th>Total</th></tr>`;
  const filas = legajos.map(l => {
    let total = 0;
    const celdas = rango.map(d => { const k = l + "|" + d, an = byDay[k] || [], dia = diaIdx[k];
      total += an.length;
      const cls = an.length ? worst(an) : dia ? "ok" : "off";
      return `<td class="c ${cls} ${an.length > 1 ? "n" : ""}" data-n="${an.length}" data-k="${k}"></td>`; }).join("");
    return `<tr><td class="who">${quien(l)}</td>${celdas}<td class="tot num">${total}</td></tr>`; }).join("");
  $("#hm").innerHTML = `<table>${head}${filas}</table>`;
  document.querySelectorAll("#hm td.c").forEach(td => {
    const [l, d] = td.dataset.k.split("|"), an = byDay[td.dataset.k] || [], dia = diaIdx[td.dataset.k];
    td.onmousemove = e => showTip(e, `<b>${esc(quienTxt(l))} · ${fDia(d)}</b>` +
      (dia ? `<div class="r">Fichajes: ${dia.fichajes.join(" · ")}</div>` : "") +
      (an.length ? an.map(a => `<div class="r"><i style="background:var(--${a.severidad})"></i>${esc(a.titulo)}</div>`).join("")
                 : `<div class="r">${dia ? "Sin anomalías" : "Sin fichajes"}</div>`));
    td.onmouseleave = hideTip;
    td.onclick = () => { if (an.length || dia) abrir(l, d); };
  });
}

// ---------- bandeja ----------
function sevButtons(){
  const base = A.filter(a => (!F.emp || a.legajo === F.emp) && (!F.dia || a.jornada === F.dia) && (!F.tipo || a.tipo === F.tipo));
  const c = s => base.filter(a => !s || a.severidad === s).length;
  $("#sevs").innerHTML = [["", "Todas"], ["alta", "Alta"], ["media", "Media"], ["baja", "Baja"]].map(([s, l]) =>
    `<button data-s="${s}" class="${F.sev === s ? "on" : ""}">${s ? `<span class="sev ${s}">${ico(s)}</span>` : ""}${l}<span class="ct num">${c(s)}</span></button>`).join("");
  $("#sevs").style.display = F.tab === "anom" ? "" : "none";
  document.querySelectorAll("#sevs button").forEach(b => b.onclick = () => { F.sev = b.dataset.s; render(); });
}
function pills(){
  const p = [];
  if (F.dia) p.push(["dia", "Jornada: " + fDia(F.dia)]);
  if (F.tipo) p.push(["tipo", "Tipo: " + (A.find(a => a.tipo === F.tipo)?.titulo || F.tipo)]);
  $("#pills").innerHTML = p.map(([k, l]) => `<span class="pill">${esc(l)}<button data-k="${k}" aria-label="Quitar filtro">×</button></span>`).join("");
  $("#pills").style.display = p.length ? "" : "none";
  document.querySelectorAll(".pill button").forEach(b => b.onclick = () => { F[b.dataset.k] = ""; render(); });
}
const COLS = {
  anom: [
    {k:"rev", t:"", v:a => revisadas.has(claveRev(a)) ? 1 : 0,
     h:a => `<input type="checkbox" class="cb" data-rev="${esc(claveRev(a))}" ${revisadas.has(claveRev(a)) ? "checked" : ""} aria-label="Marcar como revisada">`},
    {k:"sev", t:"Severidad", v:a => SEV[a.severidad].n, h:a => sevTag(a.severidad)},
    {k:"jornada", t:"Jornada", v:a => a.jornada, h:a => `<span class="num nw">${fDia(a.jornada)}</span>`},
    {k:"emp", t:"Empleado", v:a => nombres[a.legajo] || a.legajo, h:a => `<span class="who">${quien(a.legajo)}</span>`},
    {k:"tipo", t:"Anomalía", v:a => a.titulo, h:a => `<b class="nw" style="font-weight:560">${esc(a.titulo)}</b>`},
    {k:"det", t:"Detalle", v:a => a.detalle, h:a => `<div class="det">${esc(a.detalle)}</div>`},
    {k:"fich", t:"Fichajes", v:a => a.fichajes.length, h:a => `<div class="marks">${a.fichajes.map(m => `<span class="mk">${m}</span>`).join("") || "—"}</div>`},
  ],
  dias: [
    {k:"est", t:"Estado", v:d => SEV[worst(byDay[d.legajo + "|" + d.jornada] || [])].n, h:d => sevTag(worst(byDay[d.legajo + "|" + d.jornada] || []))},
    {k:"jornada", t:"Jornada", v:d => d.jornada, h:d => `<span class="num nw">${fDia(d.jornada)}</span>`},
    {k:"emp", t:"Empleado", v:d => nombres[d.legajo] || d.legajo, h:d => `<span class="who">${quien(d.legajo)}</span>`},
    {k:"prog", t:"Turno", v:d => d.programado, h:d => `<span class="num">${esc(d.programado === "franco" ? "Franco" : d.programado || "—")}</span>`},
    {k:"fich", t:"Fichajes", v:d => d.fichajes.length, h:d => `<div class="marks">${d.fichajes.map(m => `<span class="mk">${m}</span>`).join("")}</div>`},
    {k:"horas", t:"Horas", v:d => d.horas ?? -1, h:d => d.horas == null ? `<span class="sev alta">Incompleta</span>` : `<span class="num">${d.horas.toFixed(2)} h</span>`},
    {k:"nota", t:"Anomalías", v:d => (byDay[d.legajo + "|" + d.jornada] || []).length,
     h:d => esc((byDay[d.legajo + "|" + d.jornada] || []).map(a => a.titulo).join(" · ") || "—")},
  ]
};
function filas(){
  const q = F.q.toLowerCase().trim();
  const base = F.tab === "anom" ? A : DATA.dias;
  return base.filter(r => (!F.emp || r.legajo === F.emp) && (!F.dia || r.jornada === F.dia) &&
    (F.tab !== "anom" || ((!F.sev || r.severidad === F.sev) && (!F.tipo || r.tipo === F.tipo) && (!F.ocultar || !revisadas.has(claveRev(r))))) &&
    (!q || (JSON.stringify(r) + " " + (nombres[r.legajo] || "")).toLowerCase().includes(q)));
}
function tabla(){
  const cols = COLS[F.tab];
  let rows = filas();
  if (F.col) { const c = cols.find(c => c.k === F.col); rows = [...rows].sort((a, b) => { const x = c.v(a), y = c.v(b);
    return (x > y ? 1 : x < y ? -1 : 0) * (F.asc ? 1 : -1); }); }
  else if (F.tab === "anom") rows = [...rows].sort((a, b) => b.jornada.localeCompare(a.jornada) || SEV[a.severidad].n - SEV[b.severidad].n);
  const t = $("#tabla");
  t.innerHTML = `<thead><tr>${cols.map(c => `<th data-k="${c.k}">${c.t}${F.col === c.k ? (F.asc ? " ↑" : " ↓") : ""}</th>`).join("")}</tr></thead>` +
    `<tbody>${rows.slice(0, F.ver).map((r, i) => `<tr data-i="${i}" class="${F.tab === "anom" && revisadas.has(claveRev(r)) ? "done" : ""}">${cols.map(c => `<td>${c.h(r)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  if (!rows.length) t.innerHTML += `<tbody><tr><td colspan="${cols.length}"><div class="empty"><b>Nada para mostrar</b>Probá quitar algún filtro.</div></td></tr></tbody>`;
  $("#masWrap").innerHTML = rows.length > F.ver ? `<button class="more" id="mas">Mostrar ${Math.min(25, rows.length - F.ver)} más de ${rows.length - F.ver} restantes</button>` : "";
  if ($("#mas")) $("#mas").onclick = () => { F.ver += 25; tabla(); };
  t.querySelectorAll("th").forEach(th => th.onclick = () => { F.asc = F.col === th.dataset.k ? !F.asc : true; F.col = th.dataset.k; tabla(); });
  t.querySelectorAll("tbody tr[data-i]").forEach(tr => tr.onclick = e => {
    if (e.target.matches("input")) return; const r = rows[+tr.dataset.i]; abrir(r.legajo, r.jornada); });
  t.querySelectorAll("input[data-rev]").forEach(cb => cb.onchange = () => {
    cb.checked ? revisadas.add(cb.dataset.rev) : revisadas.delete(cb.dataset.rev); guardarRev(); kpis(); tabla(); });
  $("#nota").textContent = `Mostrando ${Math.min(F.ver, rows.length)} de ${rows.length} fila${rows.length === 1 ? "" : "s"}` +
    (DATA.no_parseados ? ` · ${DATA.no_parseados} fichaje(s) con fecha ilegible fueron ignorados` : "");
}

// ---------- panel de detalle ----------
const corte = (() => { const [h, m] = DATA.corte.split(":"); return +h * 60 + +m; })();
const min = hhmm => { const [h, m] = hhmm.split(":"); let v = +h * 60 + +m - corte; return v < 0 ? v + 1440 : v; };
const pos = v => (v / 1440 * 100) + "%";
function abrir(l, d){
  const k = l + "|" + d, an = byDay[k] || [], dia = diaIdx[k];
  $("#dTitle").innerHTML = esc(quienTxt(l));
  $("#dSub").textContent = fLargo(d);
  let sched = null;
  const prog = dia?.programado || an.find(a => a.tipo === "ausencia")?.detalle.match(/\d\d:\d\d–\d\d:\d\d/)?.[0];
  if (prog && prog.includes("–")) { const [a, b] = prog.split("–"); let s = min(a), e = min(b); if (e <= s) e += 1440; sched = [s, Math.min(e, 1440)]; }
  const f = dia?.fichajes || [];
  const pares = []; for (let i = 0; i + 1 < f.length; i += 2) pares.push([min(f[i]), min(f[i + 1])]);
  const impar = f.length % 2 === 1;
  const ticks = []; for (let h = 0; h <= 24; h += 4) ticks.push(h * 60);
  const lbl = v => { const t = (v + corte) % 1440; return String(Math.floor(t / 60)).padStart(2, "0") + ":" + String(t % 60).padStart(2, "0"); };
  const tl = `<div class="tl">
      ${ticks.map(t => `<div class="gr" style="left:calc(76px + (100% - 76px) * ${t / 1440})"></div>`).join("")}
      <div class="ln" data-l="Turno">${sched ? `<div class="sch" style="left:${pos(sched[0])};width:${pos(sched[1] - sched[0])}"></div>` : ""}</div>
      <div class="ln" data-l="Trabajado">${pares.map(([a, b]) => `<div class="wk" style="left:${pos(a)};width:${pos(Math.max(b - a, 4))}"></div>`).join("")}
        ${f.map((m, i) => `<div class="pm ${impar && i === f.length - 1 ? "miss" : ""}" style="left:${pos(min(m))}" title="${m}"></div>`).join("")}</div>
      <div class="ax">${ticks.map(t => `<span style="left:${pos(t)}">${lbl(t)}</span>`).join("")}</div></div>`;
  const facts = `<div class="facts">
      <div class="fact"><div class="k">Turno</div><div class="v num">${esc(prog ? prog : dia?.programado === "franco" ? "Franco" : "—")}</div></div>
      <div class="fact"><div class="k">Fichajes</div><div class="v num">${f.length}</div></div>
      <div class="fact"><div class="k">Horas</div><div class="v num">${dia?.horas != null ? dia.horas.toFixed(2) + " h" : "—"}</div></div></div>`;
  const lista = an.length ? `<div class="alist">${an.map(a => `<div class="aitem">${sevTag(a.severidad)}<b>${esc(a.titulo)}</b><p>${esc(a.detalle)}</p></div>`).join("")}</div>`
    : `<div class="okbox">${ico("ok")}Jornada sin anomalías.</div>`;
  $("#dBody").innerHTML = facts + `<div><h4>Línea de tiempo</h4>${tl}</div>` +
    `<div><h4>Fichajes</h4><div class="marks">${f.map(m => `<span class="mk">${m}</span>`).join("") || "Sin fichajes"}</div></div>` +
    `<div><h4>Anomalías</h4>${lista}</div>`;
  $("#drawer").classList.add("on"); $("#scrim").classList.add("on"); $("#drawer").setAttribute("aria-hidden", "false");
}
function cerrar(){ $("#drawer").classList.remove("on"); $("#scrim").classList.remove("on"); $("#drawer").setAttribute("aria-hidden", "true"); }
$("#dClose").onclick = cerrar; $("#scrim").onclick = cerrar;
addEventListener("keydown", e => { if (e.key === "Escape") cerrar(); });

// ---------- controles ----------
$("#fEmp").innerHTML += legajos.map(l => `<option value="${esc(l)}">${esc(quienTxt(l))}</option>`).join("");
$("#fEmp").onchange = e => { F.emp = e.target.value; render(); };
$("#q").oninput = e => { F.q = e.target.value; tabla(); };
$("#hideDone").onchange = e => { F.ocultar = e.target.checked; tabla(); };
document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => { F.tab = b.dataset.tab; F.col = null; render(); });
addEventListener("resize", () => chart());

function render(){
  F.ver = 25;
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === F.tab));
  kpis(); chart(); tipos(); mapa(); sevButtons(); pills(); tabla();
}
render();
</script>
</body>
</html>
"""


def generar(resultado: dict, carpeta: Path, periodo: str, fuente: str, no_parseados: int = 0,
            rango: tuple[str, str] | None = None, corte: str = "05:00") -> Path:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    if rango is None:
        fechas = sorted({d["jornada"] for d in resultado["dias"]} | {a["jornada"] for a in resultado["anomalias"]})
        hoy = datetime.now().date().isoformat()
        rango = (fechas[0], fechas[-1]) if fechas else (hoy, hoy)
    datos = {
        "rango": list(rango),
        "corte": corte,
        "anomalias": resultado["anomalias"],
        "dias": resultado["dias"],
        "periodo": periodo,
        "fuente": fuente,
        "generado": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "no_parseados": no_parseados,
    }
    # </ escapado para que un nombre con "</script>" no rompa la página
    js = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    fuente_b64 = base64.b64encode(FUENTE.read_bytes()).decode("ascii") if FUENTE.exists() else ""
    contenido = PLANTILLA.replace("__FUENTE__", fuente_b64).replace("__DATA__", js)
    sello = datetime.now().strftime("%Y-%m-%d_%H%M")
    ruta = carpeta / f"reporte_{sello}.html"
    ruta.write_text(contenido, encoding="utf-8")
    (carpeta / "index.html").write_text(contenido, encoding="utf-8")
    return ruta
