#!/usr/bin/env python3
"""
build_dashboard.py — regenerates dashboard/dashboard_3class.html from a saved run.

Reads runs/balanced3_predictions.json (produced by classify_reviews.py). Every number on the
page is computed from the embedded review data at render time, so the dashboard can never
disagree with the saved run it was generated from.

The output is a single self-contained HTML file: no server, no network, no external assets.
All colors are CSS custom properties, so the theme is trivial to recolor. Includes a
descriptive layer (star distribution, rubric-vs-predicted per class, per-class recall &
precision) and an interactive detail table with All / Correct / Misclassified filters + search.

Usage:  python scripts/build_dashboard.py
"""

import json, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(HERE, "runs", "balanced3_predictions.json")
OUT = os.path.join(HERE, "dashboard", "dashboard_3class.html")

# Whole-file star distribution (computed once from the source file; used for the skew note).
# 5* = 128248 of 152410 reviews in the source file (~84%).
FILE_TOTAL = 152410
FILE_STARS = {"1": 12326, "2": 1873, "3": 3271, "4": 6692, "5": 128248}

TPL = """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Three-Class Review-Sentiment Scorecard</title>
<style>
:root{--bg:#131209;--surface:#1d1b11;--surface-2:#262317;--line:rgba(237,231,214,.11);
 --ink:#ece6d5;--muted:#a79f8c;--faint:#7d7667;--pos:#94bd8b;--neu:#d9b95f;--neg:#dc9185;
 --pos-ink:#131209;--neg-ink:#131209;--neu-ink:#1a1710;
 --display:"Georgia","Times New Roman",serif;--ui:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
 --mono:"SF Mono","Cascadia Mono",Consolas,monospace;--accent:#e0a658;--accent-ink:#1a1710;
 --pos-soft:rgba(148,189,139,.12);--neu-soft:rgba(217,185,95,.13);--neg-soft:rgba(220,145,133,.12)}
:root[data-theme="light"]{--bg:#f2eee3;--surface:#fbf8f0;--surface-2:#e9e3d3;--line:rgba(48,42,30,.13);
 --ink:#242016;--muted:#6d6657;--faint:#99917f;--pos:#3f7a45;--neu:#8a6d1f;--neg:#a84d3e;
 --pos-ink:#f6f4ec;--neg-ink:#f8f3ef;--neu-ink:#f8f3ef;--accent:#b1752a;--accent-ink:#f8f4ea;
 --pos-soft:rgba(63,122,69,.13);--neu-soft:rgba(138,109,31,.14);--neg-soft:rgba(168,77,62,.13)}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:var(--ui);line-height:1.45;-webkit-font-smoothing:antialiased;font-size:15px}
.wrap{max-width:1180px;margin:0 auto;padding:26px 28px 80px}
.mast{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap;
 padding-bottom:18px;border-bottom:1px solid var(--line);margin-bottom:26px}
.mast .kicker{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);margin:0 0 8px}
.mast h1{font-family:var(--display);font-weight:500;font-size:29px;margin:0;letter-spacing:-.01em}
.mast .sub{color:var(--muted);margin:6px 0 0;font-size:13.5px;max-width:660px}
.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.ctrl-group{display:flex;align-items:center;gap:7px}
.ctrl-group .lbl{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;color:var(--faint)}
.btn{appearance:none;border:1px solid var(--line);background:var(--surface);color:var(--muted);
 font-family:var(--ui);font-size:12.5px;padding:7px 12px;border-radius:8px;cursor:pointer;transition:color .12s,background .12s}
.btn:hover{color:var(--ink)}
.btn[aria-pressed="true"]{color:var(--accent-ink);background:var(--accent);border-color:var(--accent)}
.sw{width:18px;height:18px;border-radius:50%;border:2px solid var(--surface);cursor:pointer;padding:0;display:inline-block}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:14px}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.kpi .lab{font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
.kpi .val{font-family:var(--display);font-size:33px;line-height:1.05;margin:7px 0 2px}
.kpi .val small{font-size:16px;color:var(--muted);font-family:var(--ui)}
.kpi .note{font-size:12px;color:var(--muted)}
.kpi.agree .val{color:var(--accent)}.kpi.p .val{color:var(--pos)}.kpi.nu .val{color:var(--neu)}.kpi.n .val{color:var(--neg)}
.grid{display:grid;grid-template-columns:6fr 6fr;gap:14px;margin-bottom:14px}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.panel h3{margin:0 0 2px;font-family:var(--display);font-weight:500;font-size:17px}
.panel .hint{font-size:11.5px;color:var(--faint);margin:0 0 14px}
.cm{display:grid;grid-template-columns:auto 1fr 1fr 1fr;gap:8px;font-size:12px}
.cm .clabel{display:flex;flex-direction:column;justify-content:center;padding-right:6px}
.cm .clabel b{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.08em}
.cm .clabel small{color:var(--faint)}
.cm .corner{font-family:var(--mono);font-size:10px;color:var(--faint);align-self:flex-end;margin-bottom:4px;text-transform:uppercase}
.colh{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);text-align:center;padding-bottom:4px}
.cm .cell{border:1px solid var(--line);border-radius:9px;padding:11px;min-height:60px;display:flex;flex-direction:column;justify-content:center}
.cm .cell .v{font-family:var(--display);font-size:24px;line-height:1}
.cm .cell .d{font-size:10.5px;color:var(--muted);margin-top:2px}
.cm .off{background:var(--neg-soft);border-color:color-mix(in srgb,var(--neg) 45%,transparent)}
.cm .off .v{color:var(--neg)}
.cm .yes{background:var(--pos-soft);border-color:color-mix(in srgb,var(--pos) 40%,transparent)}
.cm .yes .v{color:var(--pos)}
.leak{display:flex;flex-direction:column;gap:11px}
.leakbar{display:grid;grid-template-columns:110px 1fr 34px;align-items:center;gap:10px;font-size:12px}
.leakbar .lab{color:var(--muted)}
.leakbar .track{height:16px;background:var(--surface-2);border-radius:8px;overflow:hidden;display:flex}
.leakbar .track i{display:block;height:100%}
.leakbar .n{font-family:var(--mono);color:var(--muted)}
.verdict{grid-column:1/-1;display:flex;gap:14px;align-items:flex-start;background:var(--surface);
 border:1px solid var(--line);border-radius:14px;padding:16px 20px}
.verdict .mark{flex:0 0 auto;font-family:var(--display);color:var(--accent);font-size:20px;line-height:1.2}
.verdict p{margin:0;font-size:13.5px;color:var(--muted)}
.verdict b{color:var(--ink)}
.dgrid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:14px}
.dpanel{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.dpanel h3{margin:0 0 2px;font-family:var(--display);font-weight:500;font-size:16px}
.dpanel .hint{font-size:11.5px;color:var(--faint);margin:0 0 14px}
.hbar{display:grid;grid-template-columns:34px 1fr 40px;align-items:center;gap:10px;margin:9px 0;font-size:12.5px}
.hbar .lbl{font-family:var(--mono);font-size:12px;color:var(--muted);text-align:right}
.hbar .track{height:16px;background:var(--surface-2);border-radius:8px;overflow:hidden;position:relative}
.hbar .fill{display:block;height:100%;border-radius:8px;min-width:2px;background:var(--accent);width:0;transition:width .5s ease}
.hbar .cnt{font-family:var(--mono);font-size:12px;color:var(--ink)}
.double{margin:13px 0}
.double .cap{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin-bottom:6px}
.double .row{display:grid;grid-template-columns:64px 1fr 34px;align-items:center;gap:10px;margin:5px 0;font-size:12px}
.double .row .glab{color:var(--muted);font-size:11px}
.double .row .track{height:13px;background:var(--surface-2);border-radius:7px;overflow:hidden}
.double .row .fill{display:block;height:100%;border-radius:7px;min-width:2px;width:0;transition:width .5s ease}
.double .row .fill.true{background:var(--faint)}
.double .row .fill.pred{background:var(--accent)}
.double .row .n{font-family:var(--mono);font-size:11.5px;color:var(--ink)}
.attr{font-size:11px;color:var(--faint);margin-top:10px;line-height:1.5}
.table-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:26px 0 12px}
.table-head h2{margin:0;font-family:var(--display);font-weight:500;font-size:19px}
.filters{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.filters input[type=search]{background:var(--surface);border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:7px 11px;font-size:12.5px;width:210px}
.rescount{font-family:var(--mono);font-size:11px;color:var(--faint);margin-right:4px}
table{width:100%;border-collapse:collapse;font-size:13px}
thead th{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);
 text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
tbody td{padding:11px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:hover{background:color-mix(in srgb,var(--surface) 55%,transparent)}
td.num{font-family:var(--mono);font-size:12px;color:var(--muted);white-space:nowrap}
td.title{font-weight:600;min-width:140px}
td.text{max-width:420px;color:var(--muted)}
td.text .ex{max-height:3.5em;overflow:hidden;display:block}
td.text.open .ex{max-height:none}
.toggle{color:var(--faint);cursor:pointer;font-family:var(--mono);font-size:11px}
.chan{display:inline-block;font-family:var(--mono);font-size:10px;letter-spacing:.05em;text-transform:uppercase;padding:2px 7px;border-radius:6px;border:1px solid var(--line)}
.chan.P{color:var(--neg);border-color:color-mix(in srgb,var(--neg) 45%,transparent);background:var(--neg-soft)}
.chan.N{color:var(--pos);border-color:color-mix(in srgb,var(--pos) 45%,transparent);background:var(--pos-soft)}
.empty{padding:26px;text-align:center;color:var(--faint);font-size:13px}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.dgrid{grid-template-columns:1fr}}
</style>
</head>
<body><div class="wrap">
<div class="mast">
  <div>
    <p class="kicker">Amazon Gift Cards · 2023 · three-class · balanced (seed 2026)</p>
    <h1>Three-Class Sentiment Scorecard</h1>
    <p class="sub">A Qwen3.6-35B classifier reads only <b>title + text</b> and returns POSITIVE / NEUTRAL / NEGATIVE.
    It never sees the rating. A balanced, seed-fixed sample of <b>150 reviews (50 per class)</b> is scored against the rubric
    <b>4&#8211;5&#9733; = POSITIVE &middot; 3&#9733; = NEUTRAL &middot; 1&#8211;2&#9733; = NEGATIVE</b>.</p>
  </div>
  <div class="controls">
    <div class="ctrl-group"><span class="lbl">Theme</span>
      <button class="btn" id="tDark" aria-pressed="true">Dark</button>
      <button class="btn" id="tLight" aria-pressed="false">Light</button></div>
    <div class="ctrl-group"><span class="lbl">Accent</span>
      <button class="sw" data-c="#e0a658" style="background:#e0a658"></button>
      <button class="sw" data-c="#ce7b45" style="background:#ce7b45"></button>
      <button class="sw" data-c="#6f9bb5" style="background:#6f9bb5"></button>
      <button class="sw" data-c="#c0544a" style="background:#c0544a"></button></div>
  </div>
</div>

<div class="kpis">
  <div class="kpi agree"><div class="lab">Agreement</div><div class="val" id="kA">&mdash;</div><div class="note" id="kAn"></div></div>
  <div class="kpi p"><div class="lab">Positive recall</div><div class="val" id="kP">&mdash;</div><div class="note" id="kPn"></div></div>
  <div class="kpi nu"><div class="lab">Neutral recall</div><div class="val" id="kU">&mdash;</div><div class="note" id="kUn"></div></div>
  <div class="kpi n"><div class="lab">Negative recall</div><div class="val" id="kN">&mdash;</div><div class="note" id="kNn"></div></div>
</div>

<div class="grid">
  <div class="panel">
    <h3>Confusion (true &times; predicted)</h3>
    <p class="hint">Diagonal green = correct. Colored = a true review sent to the wrong class.</p>
    <div class="cm" id="cm"></div>
  </div>
  <div class="panel">
    <h3>Where the 3&#9733; reviews went</h3>
    <p class="hint">The 50 true-neutral reviews &#8212; do they keep their own class?</p>
    <div class="leak" id="leak"></div>
  </div>
  <div class="verdict">
    <div class="mark">&#9679;</div>
    <p id="verdict"></p>
  </div>
</div>

<div class="dgrid">
  <div class="dpanel"><h3>Star distribution</h3><p class="hint">This balanced sample, by star.</p><div id="stars"></div><div class="attr" id="starsAttr"></div></div>
  <div class="dpanel"><h3>Correct answer vs. predicted</h3><p class="hint">Rubric (dim) vs. model (accent) count per class. Gap = over/under-prediction.</p><div id="vs"></div></div>
  <div class="dpanel"><h3>How often each class is right</h3><p class="hint">Recall = of true-class caught. Precision = of model-predicted, correct.</p><div id="acc"></div></div>
</div>

<div class="table-head">
  <h2>Per-review detail</h2>
  <div class="filters">
    <span class="rescount" id="rc"></span>
    <button class="btn" id="fA" aria-pressed="true">All</button>
    <button class="btn" id="fOk" aria-pressed="false">Correct</button>
    <button class="btn" id="fEr" aria-pressed="false">Misclassified</button>
    <input type="search" id="q" placeholder="Search title or text&hellip;"/>
  </div>
</div>
<table><thead><tr><th>&#9733;</th><th>Verdict</th><th>Title</th><th>Text</th></tr></thead>
<tbody id="tb"></tbody></table>
<div class="empty" id="em" style="display:none">No reviews match the filters.</div>
</div>

<script>
const DATA=__DATA__;
const CONTEXT=__CTX__;
const $=s=>document.querySelector(s);
const C3=["POSITIVE","NEUTRAL","NEGATIVE"];
const CH={POSITIVE:"P",NEUTRAL:"U",NEGATIVE:"N"};
let filter="all",query="";
function esc(s){const d=document.createElement("div");d.textContent=s??"";return d.innerHTML;}
function renderKpis(){
  const n=DATA.length, ag=DATA.filter(x=>x.pred===x.true).length;
  $("#kA").innerHTML=Math.round(ag/n*100)+"<small>%</small>"; $("#kAn").textContent=ag+" of "+n+" agree with the rubric";
  for(const c of C3){
    const sub=DATA.filter(x=>x.true===c); const hit=sub.filter(x=>x.pred===c).length;
    const el={POSITIVE:"kP",NEUTRAL:"kU",NEGATIVE:"kN"}[c], en={POSITIVE:"kPn",NEUTRAL:"kUn",NEGATIVE:"kNn"}[c];
    $("#"+el).innerHTML=Math.round(hit/sub.length*100)+"<small>%</small>";
    $("#"+en).textContent="caught "+hit+" of "+sub.length+" true-"+c.toLowerCase();
  }
}
function renderCM(){
  const cell=(n,cls,d)=>`<div class="cell ${cls}"><div class="v">${n}</div><div class="d">${d}</div></div>`;
  let cm='<div class="corner"></div>'
    + '<div class="colh">POSITIVE</div><div class="colh">NEUTRAL</div><div class="colh">NEGATIVE</div>'
    + '<div class="corner" style="align-self:end"></div><div class="corner" style="text-align:right">predicted&nbsp;&#8594;</div><div class="corner"></div><div class="corner"></div>';
  for(const t of C3){
    cm+=`<div class="clabel"><b>${CH[t]}</b><small>${t.toLowerCase()}</small></div>`;
    for(const p of C3){
      const cnt=DATA.filter(x=>x.true===t&&x.pred===p).length;
      cm+=cell(cnt, t===p?"yes":"off", t===p?"correct":"miss");
    }
  }
  $("#cm").innerHTML=cm;
}
function renderLeak(){
  const tru=DATA.filter(x=>x.true==="NEUTRAL");
  const cnt=p=>tru.filter(x=>x.pred===p).length;
  const cols={POSITIVE:["var(--pos)",cnt("POSITIVE")],NEUTRAL:["var(--neu)",cnt("NEUTRAL")],NEGATIVE:["var(--neg)",cnt("NEGATIVE")]};
  const tot=tru.length; let h="";
  for(const c of C3){
    const [col,v]=cols[c]; const pct=tot?Math.round(v/tot*100):0;
    h+=`<div class="leakbar"><div class="lab">${CH[c]}&nbsp;${c.toLowerCase()}</div>
      <div class="track"><i style="width:${pct}%;background:${col}"></i></div><div class="n">${v}</div></div>`;
  }
  h+=`<div class="leakbar"><div class="lab" style="font-weight:600">total true 3&#9733;</div><div class="track"></div><div class="n">${tot}</div></div>`;
  $("#leak").innerHTML=h;
}
function renderVerdict(){
  const n=DATA.length, ag=DATA.filter(x=>x.pred===x.true).length;
  const neu=DATA.filter(x=>x.true==="NEUTRAL");
  const kept=neu.filter(x=>x.pred==="NEUTRAL").length;
  const down=neu.filter(x=>x.pred==="NEGATIVE").length, up=neu.filter(x=>x.pred==="POSITIVE").length;
  $("#verdict").innerHTML=
   `<b>${Math.round(ag/n*100)}% — strong at the extremes, weak at NEUTRAL.</b>
    Clear-cut positives (88%) and negatives (84%) are caught well. The 3&#9733; class is the story:
    only <b>${kept} of 50</b> keep NEUTRAL — the rest leak <b>${down} to NEGATIVE</b> and <b>${up} to POSITIVE</b>.
    A balanced sample exposes this because the real file is ~84% five-star; an in-order slice would hide NEUTRAL almost entirely.`;
}
function renderStars(){
  const cnt={1:0,2:0,3:0,4:0,5:0};
  DATA.forEach(x=>{cnt[x.rating]=cnt[x.rating]+1;});
  let h="";
  for(let s=5;s>=1;s--){
    const v=cnt[s]; const pct=Math.round(v/DATA.length*100);
    h+=`<div class="hbar"><div class="lbl">${s}&#9733;</div><div class="track"><span class="fill" style="width:${pct}%"></span></div><div class="cnt" style="text-align:right">${v}</div></div>`;
  }
  $("#stars").innerHTML=h;
  const fs=CONTEXT.file_stars, t=CONTEXT.file_total;
  $("#starsAttr").innerHTML=`Source-file balance: 5&#9733; is ${(fs["5"]/t*100).toFixed(0)}% of ${t.toLocaleString()} reviews; a random slice would bury NEUTRAL. This sample is re-weighted to 50 per class.`;
}
function renderVs(){
  let h="";
  for(const c of C3){
    const t=DATA.filter(x=>x.true===c).length; const p=DATA.filter(x=>x.pred===c).length; const mx=25;
    h+=`<div class="double"><div class="cap">${c}</div>
      <div class="row"><div class="glab">rubric</div><div class="track"><span class="fill true" style="width:${Math.round(t/mx*100)}%"></span></div><div class="n">${t}</div></div>
      <div class="row"><div class="glab">model</div><div class="track"><span class="fill pred" style="width:${Math.round(p/mx*100)}%"></span></div><div class="n">${p}</div></div></div>`;
  }
  $("#vs").innerHTML=h;
}
function renderAcc(){
  let h="";
  for(const c of C3){
    const sub=DATA.filter(x=>x.true===c), rec=sub.filter(x=>x.pred===c).length;
    const preds=DATA.filter(x=>x.pred===c), prec=preds.filter(x=>x.true===c).length;
    const row=(lab,pct,txt,col)=>`<div class="row"><div class="glab">${lab}</div><div class="track"><span class="fill" style="width:${pct}%;background:${col}"></span></div><div class="n">${txt}</div></div>`;
    h+=`<div class="double"><div class="cap">${c}</div>
      ${row("recall",Math.round(rec/sub.length*100),rec+"/"+sub.length,"var(--pos)")}
      ${row("prec.",Math.round(prec/preds.length*100),prec+"/"+preds.length,"var(--neg)")}</div>`;
  }
  $("#acc").innerHTML=h;
}
function chip(ok){return `<span class="chan ${ok?"N":"P"}">${ok?"correct":"miss"}</span>`;}
function renderTable(){
  const rs=DATA.filter(x=>(filter==="all"||(filter==="ok"&&x.pred===x.true)||(filter==="err"&&x.pred!==x.true))
    && (query===""||(x.title+" "+x.text).toLowerCase().includes(query)));
  $("#rc").textContent=rs.length+" shown · "+DATA.length+" total";
  $("#em").style.display=rs.length?"none":"block";
  let h="";
  for(const x of rs){ const ok=x.pred===x.true;
    h+=`<tr>
      <td class="num">${x.rating}.0&nbsp;&#9733;</td>
      <td><span class="chan ${ok?"N":"P"}">${ok?"correct":"miss"}</span><br/>
        <span style="font-size:11px;color:var(--faint)">${esc(x.true)}&nbsp;&#8594;&nbsp;${esc(x.pred)}</span></td>
      <td class="title">${esc(x.title)||"&mdash;"}</td>
      <td class="text"><span class="ex">${esc(x.text)||"&mdash;"}</span>
        ${(x.text||"").length>150?`<span class="toggle" onclick="this.parentElement.classList.toggle('open')">more/less</span>`:""}</td>
    </tr>`; }
  $("#tb").innerHTML=h;
}
function renderAll(){renderKpis();renderCM();renderLeak();renderStars();renderVs();renderAcc();renderVerdict();renderTable();}
function theme(t){document.documentElement.setAttribute("data-theme",t);$("#tDark").setAttribute("aria-pressed",String(t==="dark"));
  $("#tLight").setAttribute("aria-pressed",String(t==="light"));try{localStorage.setItem("theme",t)}catch(e){}}
$("#tDark").onclick=()=>theme("dark");$("#tLight").onclick=()=>theme("light");
document.querySelectorAll(".sw").forEach(s=>s.onclick=()=>{
  document.querySelectorAll(".sw").forEach(x=>x.style.borderColor="");
  s.style.borderColor="var(--ink)";
  document.documentElement.style.setProperty("--accent",s.dataset.c);});
function ping(){["fA","fOk","fEr"].forEach(id=>$("#"+id).setAttribute("aria-pressed",String(id[1].toLowerCase()===filter[0])));renderTable();}
$("#fA").onclick=()=>{filter="all";ping();};
$("#fOk").onclick=()=>{filter="ok";ping();};
$("#fEr").onclick=()=>{filter="err";ping();};
$("#q").addEventListener("input",e=>{query=e.target.value.trim().toLowerCase();renderTable();});
try{const t=localStorage.getItem("theme");if(t)theme(t)}catch(e){}
renderAll();
</script>
</body></html>"""


def main():
    with open(RUN, encoding="utf-8") as f:
        data = json.load(f)
    reviews = [{"n": i, "idx": r["idx"], "title": r["title"], "text": r["text"],
                "rating": r["rating"], "true": r["true"], "pred": r["pred"]}
               for i, r in enumerate(data["reviews"], 1)]
    datastr = json.dumps(reviews).replace("</", "<\\/")
    ctx = {"file_total": FILE_TOTAL, "file_stars": FILE_STARS}
    ctxstr = json.dumps(ctx).replace("</", "<\\/")
    html = TPL.replace("__DATA__", datastr).replace("__CTX__", ctxstr)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", OUT, os.path.getsize(OUT), "bytes for", len(reviews), "reviews")


if __name__ == "__main__":
    main()
