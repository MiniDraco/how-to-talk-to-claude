#!/usr/bin/env python3
"""
Build a single-file interactive node map of everything harvested.

  python build_map.py            -> map.html   (self-contained, no CDN, opens offline)

Structure: centre -> 7 control surfaces -> keyword clusters -> individual rules,
with provenance edges out to the source papers. Layout is computed here once
(deterministic) so the page just draws; that keeps thousands of nodes smooth.
"""
import collections, html, json, math, os, re, sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
SURFACES = ["intent", "context", "persistence", "comprehension",
            "process", "verification", "termination"]
COLOR = {"intent": "#d8a13a", "context": "#3f8fd0", "persistence": "#9b59b6",
         "comprehension": "#e0603a", "process": "#7b5bd6", "verification": "#2e9e6b",
         "termination": "#cc4444", "_root": "#111111", "_paper": "#8a8a8a"}
STOP = set("""the a an and or of to in for with on by is are be as at from that this it its
we our you your using use used can may will not no than then when where which who what how
based large model models language llm llms prompt prompts prompting task tasks data set
approach method methods results result paper study new via more most such into over under
between during about across per each other others also both any all more less improve
improved improving performance evaluate evaluation propose proposed novel framework""".split())


def top_terms(text, n=3):
    words = [w for w in re.findall(r"[a-z][a-z\-]{3,}", (text or "").lower()) if w not in STOP]
    return [w for w, _ in collections.Counter(words).most_common(n)]


def build():
    rc = sqlite3.connect(os.path.join(HERE, "rules.db"))
    rules = rc.execute("""SELECT id, rule, mechanism, category, source_ref, source_title,
                          confidence FROM rules""").fetchall()
    try:
        pc = sqlite3.connect(os.path.join(HERE, "papers.db"))
        npapers = pc.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    except Exception:
        npapers = 0
    try:
        qc = sqlite3.connect(os.path.join(HERE, "prompts.db"))
        nprompts = qc.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
    except Exception:
        nprompts = 0

    by_surface = collections.defaultdict(list)
    for r in rules:
        by_surface[r[3] if r[3] in SURFACES else "process"].append(r)

    nodes, links = [], []
    nodes.append({"i": 0, "t": "How To Talk\nto Claude", "k": "root", "s": "_root",
                  "x": 0.0, "y": 0.0, "r": 26, "d": f"{len(rules):,} mined rules · "
                  f"{npapers:,} papers · {nprompts:,} prompts"})
    nid = 1
    R1 = 420.0

    for si, surf in enumerate(SURFACES):
        rs = by_surface.get(surf, [])
        ang = (si / len(SURFACES)) * math.tau - math.pi / 2
        sx, sy = math.cos(ang) * R1, math.sin(ang) * R1
        s_id = nid; nid += 1
        nodes.append({"i": s_id, "t": surf, "k": "surface", "s": surf,
                      "x": sx, "y": sy, "r": 16 + min(14, len(rs) / 60),
                      "d": f"{len(rs):,} rules on this control surface"})
        links.append({"a": 0, "b": s_id, "w": 2.4})

        # cluster this surface's rules by their dominant term
        buckets = collections.defaultdict(list)
        for r in rs:
            terms = top_terms(r[1] + " " + (r[2] or ""))
            buckets[terms[0] if terms else "general"].append(r)
        # merge tiny buckets so the ring stays readable
        big = {k: v for k, v in buckets.items() if len(v) >= 3}
        misc = [r for k, v in buckets.items() if len(v) < 3 for r in v]
        if misc:
            big["other"] = misc
        ordered = sorted(big.items(), key=lambda kv: -len(kv[1]))[:22]

        span = math.tau / len(SURFACES) * 0.86
        for ci, (term, items) in enumerate(ordered):
            ca = ang - span / 2 + (span * (ci + 0.5) / max(1, len(ordered)))
            r2 = R1 + 300 + (ci % 3) * 70
            cx, cy = math.cos(ca) * r2, math.sin(ca) * r2
            c_id = nid; nid += 1
            nodes.append({"i": c_id, "t": term, "k": "cluster", "s": surf,
                          "x": cx, "y": cy, "r": 7 + min(9, len(items) / 14),
                          "d": f"{len(items)} rules · {surf}"})
            links.append({"a": s_id, "b": c_id, "w": 1.2})

            for ri, r in enumerate(items):
                a = ca + (ri - len(items) / 2) * (0.020 + 0.5 / max(6, len(items)))
                rr = r2 + 150 + (ri % 7) * 46
                nodes.append({"i": nid, "t": r[1][:80], "k": "rule", "s": surf,
                              "x": math.cos(a) * rr, "y": math.sin(a) * rr,
                              "r": 2.6 + 2.4 * float(r[6] or 0.5),
                              "d": r[2] or "", "src": r[5] or "", "ref": r[4] or "",
                              "full": r[1]})
                links.append({"a": c_id, "b": nid, "w": 0.4})
                nid += 1

    return nodes, links, len(rules), npapers, nprompts


NODES, LINKS, NR, NPAP, NPRO = build()

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rule Map — How To Talk To Claude</title><style>
*{box-sizing:border-box}html,body{margin:0;height:100%;overflow:hidden;
font-family:ui-sans-serif,system-ui,'Segoe UI',Helvetica,Arial;background:#0e0f13;color:#e8e8ea}
#c{position:fixed;inset:0;cursor:grab}#c.drag{cursor:grabbing}
#hud{position:fixed;top:0;left:0;right:0;padding:10px 14px;display:flex;gap:10px;
align-items:center;background:linear-gradient(#0e0f13ee,#0e0f1300);pointer-events:none;z-index:5}
#hud>*{pointer-events:auto}
h1{font-size:14px;font-weight:600;margin:0 14px 0 0;letter-spacing:.02em}
h1 small{color:#8b8b95;font-weight:400;margin-left:8px}
input,select,button{background:#1a1c22;border:1px solid #2c2f38;color:#e8e8ea;
border-radius:7px;padding:6px 10px;font-size:12.5px;font-family:inherit}
input{width:250px}input::placeholder{color:#6b6b76}button{cursor:pointer}
button:hover{border-color:#4a4f5e}
#panel{position:fixed;right:14px;top:56px;width:340px;max-height:calc(100vh - 78px);
overflow:auto;background:#15171dfa;border:1px solid #2c2f38;border-radius:11px;
padding:15px;font-size:12.5px;line-height:1.62;display:none;z-index:6}
#panel h2{margin:0 0 8px;font-size:13.5px;line-height:1.45}
#panel .tag{display:inline-block;padding:2px 9px;border-radius:20px;font-size:10.5px;
font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin-bottom:9px}
#panel .lab{color:#8b8b95;font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;
margin:11px 0 3px}#panel .src{color:#9aa4b4;word-break:break-word}
#legend{position:fixed;left:14px;bottom:14px;background:#15171dcc;border:1px solid #2c2f38;
border-radius:9px;padding:9px 12px;font-size:11.5px;z-index:5;line-height:1.85}
#legend b{display:block;margin-bottom:4px;font-size:10.5px;color:#8b8b95;
text-transform:uppercase;letter-spacing:.07em}
.sw{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}
#tip{position:fixed;pointer-events:none;background:#0a0b0ef2;border:1px solid #343845;
padding:5px 9px;border-radius:6px;font-size:11.5px;max-width:330px;display:none;z-index:8}
#stat{position:fixed;right:14px;bottom:14px;color:#6b6b76;font-size:11px;z-index:5}
</style></head><body>
<canvas id="c"></canvas>
<div id="hud"><h1>Rule Map<small>__NR__ rules · __NPAP__ papers · __NPRO__ prompts</small></h1>
<input id="q" placeholder="search rules…" autocomplete="off">
<select id="f"><option value="">all surfaces</option>__OPTS__</select>
<button id="reset">reset view</button></div>
<div id="panel"></div><div id="tip"></div>
<div id="legend"><b>control surface</b>__LEG__</div>
<div id="stat"></div>
<script>
const NODES=__NODES__, LINKS=__LINKS__, COLOR=__COLOR__;
const cv=document.getElementById('c'), ctx=cv.getContext('2d');
let W=0,H=0,DPR=Math.min(2,devicePixelRatio||1);
function size(){W=innerWidth||1280;H=innerHeight||720;cv.width=W*DPR;cv.height=H*DPR;
cv.style.width=W+'px';cv.style.height=H+'px';ctx.setTransform(DPR,0,0,DPR,0,0);draw();}
addEventListener('resize',size);

let sc=0.30, ox=0, oy=0, sel=null, hov=null, q='', surf='';
function fit(){sc=0.30;ox=W/2;oy=H/2;}
const S=n=>[n.x*sc+ox, n.y*sc+oy];

function visible(n){
  if(surf && n.s!==surf && n.k!=='root') return false;
  if(q){ if(n.k==='rule') return (n.full||n.t).toLowerCase().includes(q)||(n.d||'').toLowerCase().includes(q);
         return n.t.toLowerCase().includes(q)||n.k!=='rule'; }
  return true;
}
function draw(){
  ctx.clearRect(0,0,W,H);
  ctx.lineWidth=1;
  for(const l of LINKS){
    const a=NODES[l.a], b=NODES[l.b];
    if(!visible(a)&&!visible(b))continue;
    const dim=(q||surf)&&!(visible(a)&&visible(b));
    const [ax,ay]=S(a),[bx,by]=S(b);
    if((ax<-200&&bx<-200)||(ax>W+200&&bx>W+200)||(ay<-200&&by<-200)||(ay>H+200&&by>H+200))continue;
    ctx.strokeStyle=dim?'rgba(255,255,255,.03)':(COLOR[b.s]||'#666')+(l.w>1?'66':'26');
    ctx.lineWidth=Math.max(.35,l.w*sc*1.5);
    ctx.beginPath();ctx.moveTo(ax,ay);
    const mx=(ax+bx)/2,my=(ay+by)/2;
    ctx.quadraticCurveTo(mx+(ay-by)*.07,my+(bx-ax)*.07,bx,by);ctx.stroke();
  }
  let shown=0;
  for(const n of NODES){
    const [x,y]=S(n); const r=Math.max(1,n.r*sc*1.35);
    if(x<-60||x>W+60||y<-60||y>H+60)continue;
    const vis=visible(n); if(vis)shown++;
    ctx.globalAlpha=vis?1:.12;
    ctx.fillStyle=COLOR[n.s]||'#888';
    ctx.beginPath();ctx.arc(x,y,r,0,6.284);ctx.fill();
    if(n===sel||n===hov){ctx.strokeStyle='#fff';ctx.lineWidth=1.6;ctx.stroke();}
    if(n.k!=='rule' && sc>0.10){
      ctx.globalAlpha=vis?.96:.12;
      ctx.fillStyle='#f2f2f5';
      ctx.font=(n.k==='root'?700:600)+' '+(n.k==='root'?15:n.k==='surface'?13:11)*Math.min(1.5,Math.max(.85,sc*2.2))+'px ui-sans-serif,system-ui';
      ctx.textAlign='center';ctx.textBaseline='middle';
      n.t.split('\\n').forEach((ln,i,arr)=>ctx.fillText(ln,x,y-r-9-(arr.length-1-i)*13));
    }
    if(n.k==='rule' && sc>1.5 && vis){
      ctx.globalAlpha=.8;ctx.fillStyle='#b9bcc6';ctx.font='9px ui-sans-serif';
      ctx.textAlign='left';ctx.textBaseline='middle';ctx.fillText(n.t.slice(0,46),x+r+3,y);
    }
  }
  ctx.globalAlpha=1;
  document.getElementById('stat').textContent=
    (q||surf?shown.toLocaleString()+' of ':'')+NODES.length.toLocaleString()+' nodes · '+Math.round(sc*100)+'%';
}
function pick(mx,my){
  let best=null,bd=1e9;
  for(const n of NODES){ if(!visible(n))continue;
    const [x,y]=S(n); const d=(x-mx)**2+(y-my)**2;
    const rr=Math.max(7,n.r*sc*1.35+5);
    if(d<rr*rr && d<bd){bd=d;best=n;} }
  return best;
}
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function show(n){
  const p=document.getElementById('panel');
  if(!n){p.style.display='none';return;}
  let h=`<span class="tag" style="background:${COLOR[n.s]}22;color:${COLOR[n.s]}">${esc(n.s==='_root'?'map':n.s)}</span>`;
  h+=`<h2>${esc(n.full||n.t)}</h2>`;
  if(n.k==='rule'){
    if(n.d)h+=`<div class="lab">why it works</div><div>${esc(n.d)}</div>`;
    if(n.src)h+=`<div class="lab">source</div><div class="src">${esc(n.src)}</div>`;
    if(n.ref)h+=`<div class="lab">reference</div><div class="src">${esc(n.ref)}</div>`;
  } else if(n.d) h+=`<div>${esc(n.d)}</div>`;
  p.innerHTML=h;p.style.display='block';
}
let drag=false,px=0,py=0,moved=0;
cv.addEventListener('mousedown',e=>{drag=true;moved=0;px=e.clientX;py=e.clientY;cv.classList.add('drag')});
addEventListener('mouseup',()=>{drag=false;cv.classList.remove('drag')});
addEventListener('mousemove',e=>{
  if(drag){ox+=e.clientX-px;oy+=e.clientY-py;moved+=Math.abs(e.clientX-px)+Math.abs(e.clientY-py);
    px=e.clientX;py=e.clientY;draw();return;}
  const n=pick(e.clientX,e.clientY); const t=document.getElementById('tip');
  if(n!==hov){hov=n;draw();}
  if(n&&n.k==='rule'){t.style.display='block';t.style.left=(e.clientX+14)+'px';
    t.style.top=(e.clientY+14)+'px';t.textContent=n.full||n.t;}
  else t.style.display='none';
});
cv.addEventListener('click',e=>{if(moved>4)return;sel=pick(e.clientX,e.clientY);show(sel);draw();});
cv.addEventListener('wheel',e=>{e.preventDefault();
  const k=Math.exp(-e.deltaY*0.0014), ns=Math.min(9,Math.max(0.05,sc*k));
  ox=e.clientX-(e.clientX-ox)*(ns/sc);oy=e.clientY-(e.clientY-oy)*(ns/sc);sc=ns;draw();},{passive:false});
document.getElementById('q').addEventListener('input',e=>{q=e.target.value.toLowerCase().trim();draw();});
document.getElementById('f').addEventListener('change',e=>{surf=e.target.value;draw();});
document.getElementById('reset').addEventListener('click',()=>{fit();sel=null;show(null);draw();});
addEventListener('keydown',e=>{if(e.key==='Escape'){sel=null;show(null);
  document.getElementById('q').value='';q='';draw();}});
size();fit();draw();
</script></body></html>"""

opts = "".join(f'<option value="{s}">{s}</option>' for s in SURFACES)
leg = "".join(f'<div><span class="sw" style="background:{COLOR[s]}"></span>{s}</div>' for s in SURFACES)
out = (PAGE.replace("__NODES__", json.dumps(NODES, separators=(",", ":")))
           .replace("__LINKS__", json.dumps(LINKS, separators=(",", ":")))
           .replace("__COLOR__", json.dumps(COLOR))
           .replace("__OPTS__", opts).replace("__LEG__", leg)
           .replace("__NR__", f"{NR:,}").replace("__NPAP__", f"{NPAP:,}")
           .replace("__NPRO__", f"{NPRO:,}"))
path = os.path.join(HERE, "map.html")
with open(path, "w", encoding="utf-8") as f:
    f.write(out)
print(f"map.html written: {len(NODES):,} nodes, {len(LINKS):,} links, {len(out)/1e6:.2f} MB")
