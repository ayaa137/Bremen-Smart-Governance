"""Standalone inline-SVG evidence explorer; no map tiles, libraries or network requests."""
import json,html
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import to_hex

def create(frame,definitions,polygons,extent):
    data=[]
    for r in frame.itertuples():
        data.append(dict(code=r.geo_code,name=r.geo_name,year=2024,complete=bool(r.scoring_eligible),
                         **{f:None if pd.isna(getattr(r,f)) else float(getattr(r,f)) for f in ['unemployment','employment','benefit_receipt']}))
    defs={r.feature:dict(label=r.english_name,german=r.original_german_name,definition=r.definition,sheet=r.source_sheet) for r in definitions.itertuples() if r.feature in ['unemployment','employment','benefit_receipt']}
    paths=[]
    x0,x1,y0,y1=extent
    for code,parts in sorted(polygons.items()):
        commands=[]
        for rings in parts:
            for ring in rings:
                coords=[((p[0]-x0)/1000,(y1-p[1])/1000) for p in ring]
                commands.append('M'+' L'.join(f'{x:.6f},{y:.6f}' for x,y in coords)+' Z')
        paths.append(f'<path id="geo-{code}" data-code="{code}" d="{" ".join(commands)}" tabindex="0" role="button" fill-rule="nonzero"><title></title></path>')
    palette=[to_hex(c) for c in plt.get_cmap('cividis_r')(np.linspace(.1,.9,8))]
    payload=json.dumps(dict(rows=data,definitions=defs,palette=palette),ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
    template=r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'">
<title>Bremen Evidence Explorer · 2024 · Section 2 research prototype</title>
<style>
:root{font-family:system-ui,Segoe UI,sans-serif;color:#20313c;background:#f4f6f8}*{box-sizing:border-box}body{margin:0}main{max-width:1350px;margin:auto;padding:26px}header{border-bottom:1px solid #cbd4db;padding-bottom:20px}.kicker{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#496773}h1{font-size:clamp(25px,4vw,40px);margin:8px 0}p{line-height:1.55}label{font-weight:650;font-size:14px}select{font:inherit;background:white;color:#20313c;border:1px solid #8298a4;border-radius:5px;padding:9px;max-width:100%;display:block;margin:7px 0 15px;width:100%}.layout{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:22px;margin-top:22px}.panel{background:white;border:1px solid #d4dfe4;border-radius:10px;padding:20px}svg{width:100%;height:auto;max-height:650px}svg path{stroke:#5f6871;stroke-width:.028;cursor:pointer}svg path:hover,svg path:focus{stroke:#101010;stroke-width:.12;outline:none}svg path.selected{stroke:#1f151b;stroke-width:.105}.legend{display:flex;gap:12px;flex-wrap:wrap;margin:15px 0;font-size:12px}.legend span{white-space:nowrap}.swatch{display:inline-block;width:23px;height:14px;border:1px solid #888;vertical-align:middle;margin-right:5px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border-bottom:1px solid #e0e7ea;padding:10px 3px}td:last-child{text-align:right;font-variant-numeric:tabular-nums}.warning{background:#fff2dd;border-left:4px solid #bb7537;padding:10px;font-size:14px}.muted{font-size:13px;color:#47616e}details{margin-top:20px}summary{cursor:pointer;font-weight:650}.source{font-size:12px;color:#425966}.meta{background:#e8f0f4;padding:8px 10px;border-radius:5px;font-size:13px}@media(max-width:850px){.layout{grid-template-columns:1fr}main{padding:15px}}
</style></head><body><main>
<header><div class="kicker">Section 2 · university research prototype · fully offline</div>
<h1>Bremen Socioeconomic Evidence Explorer</h1><p><strong>2024 · 88 represented statistical Ortsteile · 79 complete economic cases.</strong> Inspect individual indicators and evidence gaps. These rates have different denominators and do not define official disadvantage categories.</p></header>
<div class="layout"><section class="panel" aria-label="Interactive map">
<label for="indicator">Economic indicator</label><select id="indicator"><option value="unemployment">Unemployment quotient</option><option value="employment">Insured-employment participation</option><option value="benefit_receipt">SGB II receipt: under 65</option></select>
<p id="definition"></p><div id="coverage" class="meta"></div><div class="legend" id="legend"></div>
<svg id="map" viewBox="-0.5 -0.5 __WIDTH__ __HEIGHT__" aria-label="Official Bremen polygon map; use keyboard or neighborhood selector">__PATHS__</svg>
<p class="muted">Higher numerical values are darker. Gray means missing, not zero. Polygon size is land area, not affected population. Hover, click or focus an area to inspect it.</p>
</section><aside class="panel" aria-label="Neighborhood evidence">
<label for="neighborhood">Choose an Ortsteil</label><select id="neighborhood"></select>
<div id="detail" aria-live="polite"></div><details><summary>Definitions and interpretation</summary><div id="definitions"></div></details>
<details open><summary>Source and geographic caveats</summary><p class="source">Statistics: Statistisches Landesamt Bremen, supplied Datentabelle.xls; shared ortsteil_analysis_ready.csv. Exact source worksheets and labels appear above.</p>
<p class="source">Boundaries: Landesamt GeoInformation Bremen, ATKIS Verwaltungsgrenzen, CC BY 4.0. Dataset revision: 11 December 2024; retrieved 10 October 2026. Original EPSG:25832 polygons; displayed with an affine SVG transform, no tiles or fabricated coordinates.</p>
<p class="source">87 official Ortsteil polygons plus the documented undivided Oberneuland Stadtteil crosswalk to statistical 361. All 88 represented mainland records match; the separate overseas-port enclave and Bremerhaven are outside this input scope. Exact legal boundary-validity and statistical reference days remain unverified. Basic geometry checks do not certify topology.</p>
<p class="source">Descriptive ecological evidence, not causal, individual-level or population-weighted city statistics. Missingness reasons are unknown. This prototype is not a deployed municipal service.</p>
<a href="https://geodienste.bremen.de/wfs_verwaltungsgrenzen?SERVICE=WFS&amp;REQUEST=GetCapabilities" rel="noopener">Official boundary service</a></details>
</aside></div><footer><p class="source">No composite index, deprivation ranking, TOPSIS or clustering. RQ1: observed neighborhood contrasts; RQ2: definitions, coverage and limitations determine appropriate indicator use.</p><noscript>This explorer requires JavaScript; use the standalone research report and supporting CSVs for static evidence.</noscript></footer>
</main><script id="evidence-data" type="application/json">__DATA__</script><script>
'use strict';
const payload=JSON.parse(document.getElementById('evidence-data').textContent);
const rows=payload.rows, byCode=new Map(rows.map(r=>[r.code,r]));
const feature=document.getElementById('indicator'),choice=document.getElementById('neighborhood');
let selected='443';
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
rows.slice().sort((a,b)=>a.name.localeCompare(b.name,'de')).forEach(r=>{const o=document.createElement('option');o.value=r.code;o.textContent=r.name+' ('+r.code+')';choice.appendChild(o);});
function bounds(f){return f==='employment'?[40,45,50,55,60,65,70,75,80]:[0,5,10,15,20,25,30,35];}
function color(v,f){if(v===null)return '#d5d5d5';const b=bounds(f);let k=b.slice(1).findIndex(x=>v<x);if(k<0)k=b.length-2;return payload.palette[Math.round(k*7/(b.length-2))];}
function value(v){return v===null?'Missing':v.toFixed(1)+'%';}
function details(code){selected=code;choice.value=code;const r=byCode.get(code);const f=feature.value;const missing=['unemployment','employment','benefit_receipt'].filter(k=>r[k]===null).length;
document.querySelectorAll('#map path').forEach(p=>p.classList.toggle('selected',p.dataset.code===code));
document.getElementById('detail').innerHTML='<h2>'+esc(r.name)+' <small>('+r.code+')</small></h2><p>2024 · Ortsteil statistical unit · '+(3-missing)+'/3 primary indicators observed</p><table><tbody>'+['unemployment','employment','benefit_receipt'].map(k=>'<tr><th>'+esc(payload.definitions[k].label)+'</th><td>'+value(r[k])+'</td></tr>').join('')+'</tbody></table>'+(missing?'<p class="warning">Missing evidence: '+missing+' primary indicator(s). Missing values are not zero; this unit is excluded from the shared complete-case comparison.</p>':'<p class="muted">Included in the 79-case comparison. Observation does not establish individual disadvantage.</p>')+'<p class="muted">Selected map value: '+value(r[f])+'. Original precision is retained in supporting CSVs.</p>'+(code==='361'?'<p class="warning">Documented geographic exception: undivided official Stadtteil polygon mapped explicitly to statistical code 361.</p>':'');}
function redraw(){const f=feature.value,d=payload.definitions[f],b=bounds(f);document.getElementById('definition').textContent=d.definition;const n=rows.filter(r=>r[f]!==null).length;document.getElementById('coverage').textContent='2024 · '+n+'/88 observed · '+(88-n)+' missing · unit: percent';document.getElementById('legend').innerHTML=b.slice(0,-1).map((lo,i)=>'<span><i class="swatch" style="background:'+color((lo+b[i+1])/2,f)+'"></i>'+lo+'–'+(i===b.length-2?'':'<')+b[i+1]+'%</span>').join('')+'<span><i class="swatch" style="background:#d5d5d5"></i>Missing</span>';document.querySelectorAll('#map path').forEach(p=>{const r=byCode.get(p.dataset.code);p.setAttribute('fill',color(r[f],f));p.setAttribute('aria-label',r.name+' '+value(r[f]));p.querySelector('title').textContent=r.name+' ('+r.code+') · '+value(r[f])+' · 2024';});details(selected);}
document.getElementById('definitions').innerHTML=Object.values(payload.definitions).map(d=>'<h3>'+esc(d.label)+'</h3><p>'+esc(d.definition)+'</p><p class="source">German heading: '+esc(d.german)+'<br>Worksheet: '+esc(d.sheet)+' · block 1 · 2024 · %</p>').join('');
feature.addEventListener('change',redraw);choice.addEventListener('change',()=>details(choice.value));document.querySelectorAll('#map path').forEach(p=>{const update=()=>details(p.dataset.code);p.addEventListener('mouseenter',update);p.addEventListener('click',update);p.addEventListener('focus',update);p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();update();}});});redraw();
window.runExplorerTests=function(){const tests=[];function check(x,label){if(!x)throw Error(label);tests.push(label);}check(rows.length===88&&byCode.size===88,'88 unique records');check(document.querySelectorAll('#map path').length===88,'88 polygon paths');check(rows.filter(r=>r.complete).length===79,'79 complete records');for(const f of ['unemployment','employment','benefit_receipt']){feature.value=f;feature.dispatchEvent(new Event('change'));check(document.getElementById('coverage').textContent.includes(f==='benefit_receipt'?'84/88':'79/88'),'coverage '+f);check(document.getElementById('definition').textContent===payload.definitions[f].definition,'definition '+f);check(document.getElementById('legend').textContent.includes('Missing'),'legend '+f);}document.getElementById('geo-122').dispatchEvent(new MouseEvent('click'));check(document.getElementById('detail').textContent.includes('Missing evidence: 3'),'missing click');choice.value='361';choice.dispatchEvent(new Event('change'));check(document.getElementById('detail').textContent.includes('geographic exception'),'Oberneuland selector');document.getElementById('geo-443').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));check(selected==='443','keyboard activation');check(value(byCode.get('443').unemployment)==='27.5%','observed display value');feature.value='unemployment';redraw();return {status:'PASS',tests:tests.length,details:tests};};
if(location.hash==='#selftest'){try{const result=window.runExplorerTests();document.documentElement.dataset.testStatus='PASS';const output=document.createElement('pre');output.id='browser-selftest-result';output.textContent=JSON.stringify(result);document.body.appendChild(output);}catch(e){document.documentElement.dataset.testStatus='FAIL';document.body.append('SELFTEST FAILURE: '+e.message);}}
</script></body></html>'''
    return (template.replace('__WIDTH__',f'{(x1-x0)/1000+1:.6f}').replace('__HEIGHT__',f'{(y1-y0)/1000+1:.6f}')
             .replace('__PATHS__','\n'.join(paths)).replace('__DATA__',payload))
