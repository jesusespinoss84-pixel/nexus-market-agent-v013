
function fmtNum(v,s=''){return v==null?'—':`${Number(v).toFixed(1)}${s}`}
function renderIntel(x){
 const news=(x.news_headlines||[]).slice(0,3);
 $('intelSub').textContent=`${x.name} · ${x.sector||'—'} / ${x.industry||'—'} · benchmark ${x.comparison_benchmark||'—'}`;
 $('intel').innerHTML=`<div class="intelgrid">
 <div><small>Inteligencia</small><b>${fmtNum(x.market_intelligence_score)}/100</b></div>
 <div><small>Fuerza relativa 3M</small><b>${fmtNum(x.relative_strength_3m_pct,'%')}</b><span>vs ${x.comparison_benchmark||'benchmark'}</span></div>
 <div><small>Volumen anormal</small><b>${x.abnormal_volume_ratio==null?'—':Number(x.abnormal_volume_ratio).toFixed(2)+'x'}</b><span>vs promedio 20 sesiones</span></div>
 <div><small>Volatilidad 30d</small><b>${fmtNum(x.volatility_30d_live,'%')}</b></div>
 <div><small>Próximos earnings</small><b>${x.earnings_days==null?'—':x.earnings_days+' días'}</b></div>
 <div><small>Sentimiento titulares</small><b>${fmtNum(x.news_sentiment_score)}/100</b><span>informativo, bajo peso</span></div>
 </div>${news.length?`<div class="newsmini"><b>Titulares recientes</b>${news.map(n=>`<span>${n}</span>`).join('')}</div>`:''}`;
}

const $=id=>document.getElementById(id);let DATA=[],FILTER='ALL',CURRENT=null,RANGE='1m';
const pct=v=>v==null?'—':`${v>=0?'+':''}${Number(v).toFixed(2)}%`;const cls=v=>v>0?'positive':v<0?'negative':'';const money=(v,c)=>v==null?'—':new Intl.NumberFormat('es-MX',{style:'currency',currency:c,maximumFractionDigits:2}).format(v);const dt=v=>v?new Date(v).toLocaleString('es-MX'):'—';
function pill(d){if(d==='PAPER CANDIDATE')return'pill paper';if(d==='VALIDADA · ESPERAR SETUP'||d==='INVESTIGAR'||d==='VIABLE A ESTUDIAR')return'pill investigate';if(d==='VULNERABLE')return'pill risk';if(d==='OBSERVAR'||d==='OPORTUNIDAD TÉCNICA')return'pill watch';return'pill none'}
function rows(){let a=DATA;if(FILTER==='MEX')a=a.filter(x=>x.market==='MEX');if(FILTER==='CHEAP')a=a.filter(x=>x.cheap_mexican_under_50);if(FILTER==='VIABLE')a=[...a].sort((x,y)=>y.composite_score-x.composite_score).slice(0,15);if(FILTER==='VULNERABLE')a=[...a].sort((x,y)=>y.vulnerability_score-x.vulnerability_score).slice(0,15);$('body').innerHTML=a.map(x=>`<tr data-s="${x.symbol}"><td><span class="name">${x.name}</span><span class="ticker">${x.symbol}${x.aliases?' · '+x.aliases:''}</span></td><td>${money(x.price,x.currency)}</td><td class="${cls(x.ret_1d)}">${pct(x.ret_1d)}</td><td class="${cls(x.ret_1w)}">${pct(x.ret_1w)}</td><td class="${cls(x.ret_1m)}">${pct(x.ret_1m)}</td><td class="${cls(x.ret_3m)}">${pct(x.ret_3m)}</td><td class="${cls(x.ret_ytd)}">${pct(x.ret_ytd)}</td><td class="${cls(x.ret_1y)}">${pct(x.ret_1y)}</td><td>${pct(x.volatility_30d)}</td><td class="negative">${pct(x.max_drawdown_1y)}</td><td>${x.viability_score}</td><td>${x.vulnerability_score}</td><td>${x.score}</td><td>${x.market_context_score}</td><td>${x.validation_score}</td><td class="comp">${x.composite_score}</td><td><span class="${pill(x.decision)}">${x.decision}</span></td></tr>`).join('');document.querySelectorAll('#body tr').forEach(tr=>tr.onclick=()=>select(tr.dataset.s))}
function brain(x){CURRENT=x;renderAIDecision(x);$('brain').innerHTML=`<h4>${x.name}<span class="ticker">${x.symbol}${x.aliases?' · '+x.aliases:''}</span></h4><p><b>${x.decision}</b></p><p>${x.reason}</p><dl><dt>Composite</dt><dd>${x.composite_score}/100</dd><dt>Técnico</dt><dd>${x.score}/100</dd><dt>Viability</dt><dd>${x.viability_score}/100</dd><dt>Vulnerability</dt><dd>${x.vulnerability_score}/100</dd><dt>Contexto</dt><dd>${x.market_context_score}/100</dd><dt>Validación propia</dt><dd>${x.validation_score}/100</dd><dt>Walk-forward</dt><dd>${x.validation_walk_forward||'—'}</dd><dt>Setup validado ahora</dt><dd>${x.validated_match?'SÍ':'NO'}</dd></dl>`}
async function loadLab(s){$('labSub').textContent=`${s} · validación histórica propia`;$('sens').innerHTML='<p>Consultando laboratorio…</p>';try{const d=await fetch(`/api/validation/${encodeURIComponent(s)}?_=${Date.now()}`,{cache:'no-store'}).then(r=>r.json());renderLab(d)}catch(e){$('sens').innerHTML='<p>Error al cargar la validación.</p>'}}
function renderLab(d){const top=d.top10||[];if(d.status==='NOT_RUN'){$('sens').innerHTML=`<p>Este activo todavía no tiene validación propia. Usa <b>Validar rápido</b> o <b>Validación completa</b>.</p>`;return}if(d.status==='NO_DATA'){$('sens').innerHTML='<p>No hubo datos históricos suficientes para validar este activo.</p>';return}if(d.status==='ERROR'){$('sens').innerHTML=`<p>Error: ${d.error||'desconocido'}</p>`;return}const wf=d.walk_forward||{};$('sens').innerHTML=`<p><b>${d.symbol}</b> · Score validación <b>${Number(d.validation_score||0).toFixed(1)}/100</b> · Robustez <b>${Number(d.robustness_score||0).toFixed(1)}/100</b><br><b>${d.tested_combinations||0}</b> combinaciones · <b>${d.stable_combinations||0}</b> con muestra suficiente · Walk-forward <b>${wf.label||'—'}</b> · Estado ${d.validated?'<b>VALIDADA</b>':'NO VALIDADA'}</p>`+top.slice(0,8).map((z,i)=>`<div class="labrow"><b>#${i+1} RSI ${z.rsi_min} · SMA ${z.sma20_distance_min}% · Score ≥${z.score_min}</b><span>PF ${Number(z.pf).toFixed(3)} · Exp ${Number(z.exp_r).toFixed(3)}R · ${z.trades} trades · Win ${Number(z.win_pct).toFixed(1)}%</span></div>`).join('')}


function renderAIDecision(x){
  if(!$('aiDecision'))return;
  const action=x.ai_action||'OBSERVAR';
  const tone=action==='PAPER BUY'?'positive':action==='PAUSAR'?'negative':'';
  $('aiDecision').innerHTML=`<div class="aibanner ${tone}"><small>Acción sugerida para PAPER / soporte de decisión</small><b>${esc(action)}</b><span>Fuerza interna ${Number(x.ai_strength_score||0).toFixed(1)}/100</span></div><p>${esc(x.reason||'')}</p><dl><dt>Composite</dt><dd>${x.composite_score}/100</dd><dt>Validación</dt><dd>${x.validation_score}/100</dd><dt>Robustez</dt><dd>${x.validation_robustness==null?'—':Number(x.validation_robustness).toFixed(1)+'/100'}</dd><dt>Vulnerabilidad</dt><dd>${x.vulnerability_score}/100</dd><dt>Inteligencia</dt><dd>${Number(x.market_intelligence_score||0).toFixed(1)}/100</dd></dl>${x.risk_plan?`<div class="riskplan"><b>Plan PAPER sugerido</b><span>Entrada ${money(x.risk_plan.entry_mxn,'MXN')} · Stop ${money(x.risk_plan.stop_mxn,'MXN')} · Objetivo ${money(x.risk_plan.target_mxn,'MXN')} · ${x.risk_plan.suggested_shares||0} acciones</span></div>`:''}<small>No es una probabilidad de ganancia ni una orden real.</small>`;
  if($('orderSymbol'))$('orderSymbol').value=x.symbol;
}

async function paperOrder(side){
  const symbol=$('orderSymbol').value;
  const body={symbol,side,budget_mxn:Number($('orderBudget').value||0),stop_pct:Number($('orderStop').value||2),target_pct:Number($('orderTarget').value||4)};
  $('orderResult').textContent='Procesando simulación…';
  try{
    const r=await fetch('/api/paper/order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'});
    const d=await r.json();
    $('orderResult').textContent=d.ok?`${side} PAPER ejecutada para ${symbol}.`: `No se pudo: ${d.error||'error'}`;
    if(d.ok){browserAlert(`NEXUS PAPER ${side}`,`${symbol} · operación simulada`);await refresh({forceSymbol:symbol});}
  }catch(e){$('orderResult').textContent='Error al ejecutar la simulación.'}
}

function browserAlert(title,body){
  if('Notification' in window && Notification.permission==='granted')new Notification(title,{body});
}

async function initControlCenter(){
  if(!$('orderSymbol'))return;
  try{
    const [rt,al]=await Promise.all([fetch('/api/real-trading/status').then(r=>r.json()),fetch('/api/alerts/status').then(r=>r.json())]);
    $('realTradingBox').innerHTML=`<b>Trading real: ${rt.enabled?'HABILITADO':'DESHABILITADO'}</b><span>Modo: ${esc(rt.execution_mode)}</span><span>Broker: ${esc(rt.broker||'sin configurar')}</span><span>${esc(rt.note||'')}</span><ul>${(rt.requirements||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;
    $('alertStatus').textContent=`Navegador: disponible · Telegram: ${al.telegram_configured?'configurado':'pendiente de configurar'}`;
  }catch(e){}
}

let SELECT_SEQ=0;

function dateLabel(raw,range){
  const d=new Date(raw);
  if(Number.isNaN(d.getTime())) return '';
  if(range==='1y') return d.toLocaleDateString('es-MX',{month:'short'});
  return d.toLocaleDateString('es-MX',{day:'2-digit',month:'short'});
}

async function select(s,opts={}){
  const x=DATA.find(z=>z.symbol===s);
  if(!x) return;
  const seq=++SELECT_SEQ;
  CURRENT=x;
  brain(x);
  renderIntel(x);
  $('symbol').value=s;
  $('chartTitle').textContent=`${x.name} · ${money(x.price,x.currency)}`;
  $('chartStats').innerHTML='<span class="loadingdot"></span> Cargando histórico…';
  loadLab(s);

  try{
    const r=await fetch(`/api/chart/${encodeURIComponent(s)}/${RANGE}?_=${Date.now()}`,{cache:'no-store'});
    const payload=await r.json();
    if(seq!==SELECT_SEQ || CURRENT?.symbol!==s) return; // descarta respuestas viejas
    const d=Array.isArray(payload)?payload:(payload.points||[]);
    const meta=Array.isArray(payload)?{}:(payload.meta||{});
    drawDynamic($('chart'),d,x,meta);
    if(!d||d.length<2){
      $('chartTitle').textContent=`${x.name} · ${money(x.price,x.currency)} · Sin histórico disponible`;
      $('chartStats').textContent='';
    }else{
      const ch=meta.change_pct;
      const c=ch>0?'positive':ch<0?'negative':'';
      $('chartStats').innerHTML=
        `<span class="${c}"><b>${ch==null?'—':(ch>=0?'+':'')+Number(ch).toFixed(2)+'%'}</b> en ${RANGE.toUpperCase()}</span>`+
        `<span>Máx. ${money(meta.high,x.currency)}</span><span>Mín. ${money(meta.low,x.currency)}</span>`;
    }
  }catch(e){
    if(seq!==SELECT_SEQ) return;
    $('chart').innerHTML='';
    $('chartTitle').textContent=`${x.name} · ${money(x.price,x.currency)} · Error al cargar histórico`;
    $('chartStats').textContent='';
  }
}

function drawDynamic(svg,d,asset,meta={}){
  svg.innerHTML='';
  if(!d||d.length<2)return;
  const vals=d.map(q=>Number(q.close)).filter(Number.isFinite);
  if(vals.length<2)return;
  const min=Math.min(...vals),max=Math.max(...vals),pad=(max-min)*.12||1;
  const lo=min-pad,hi=max+pad,w=1000,h=330,L=72,R=34,T=25,B=48,iw=w-L-R,ih=h-T-B;
  const x=i=>L+i/(d.length-1)*iw, y=q=>T+(hi-q)/(hi-lo)*ih;
  const first=vals[0],last=vals[vals.length-1],up=last>=first;
  const stroke=up?'#16a34a':'#dc2626';
  const fill=up?'rgba(22,163,74,.13)':'rgba(220,38,38,.12)';

  svg.insertAdjacentHTML('beforeend',
    `<defs>
      <linearGradient id="areaGrad" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="${stroke}" stop-opacity=".24"/>
        <stop offset="100%" stop-color="${stroke}" stop-opacity=".02"/>
      </linearGradient>
      <filter id="softGlow"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    </defs>`);

  for(let k=0;k<5;k++){
    const yy=T+k*ih/4,val=hi-k*(hi-lo)/4;
    svg.insertAdjacentHTML('beforeend',
      `<line x1="${L}" y1="${yy}" x2="${w-R}" y2="${yy}" class="gridline"/>
       <text x="8" y="${yy+4}" class="charttext">${val.toFixed(2)}</text>`);
  }

  const tickCount=Math.min(6,d.length);
  for(let k=0;k<tickCount;k++){
    const idx=Math.round(k*(d.length-1)/(tickCount-1));
    const xx=x(idx);
    svg.insertAdjacentHTML('beforeend',
      `<text x="${xx}" y="${h-14}" text-anchor="${k===0?'start':k===tickCount-1?'end':'middle'}" class="charttext">${dateLabel(d[idx].t,RANGE)}</text>`);
  }

  const pts=d.map((q,i)=>`${x(i)},${y(Number(q.close))}`).join(' ');
  const area=`${L},${T+ih} ${pts} ${x(d.length-1)},${T+ih}`;
  svg.insertAdjacentHTML('beforeend',
    `<polygon points="${area}" fill="url(#areaGrad)" class="chartarea2"/>
     <polyline points="${pts}" fill="none" stroke="${stroke}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" class="chartline2" filter="url(#softGlow)"/>`);

  // high / low markers and last price badge
  const hiIdx=vals.indexOf(max), loIdx=vals.indexOf(min);
  [
    [hiIdx,max,'MAX'],
    [loIdx,min,'MIN']
  ].forEach(([i,v,label])=>{
    svg.insertAdjacentHTML('beforeend',
      `<circle cx="${x(i)}" cy="${y(v)}" r="5" fill="#fff" stroke="${stroke}" stroke-width="3"/>
       <text x="${x(i)}" y="${y(v)-11}" text-anchor="middle" class="markertext">${label} ${v.toFixed(2)}</text>`);
  });
  const lx=x(d.length-1),ly=y(last);
  svg.insertAdjacentHTML('beforeend',
    `<circle cx="${lx}" cy="${ly}" r="6" fill="${stroke}" class="pulsepoint"/>
     <rect x="${Math.min(lx+10,w-120)}" y="${Math.max(ly-18,4)}" rx="8" width="100" height="28" fill="${stroke}"/>
     <text x="${Math.min(lx+60,w-70)}" y="${Math.max(ly+1,23)}" text-anchor="middle" fill="#fff" font-size="13" font-weight="700">${last.toFixed(2)}</text>`);

  // invisible hover targets with tooltip
  d.forEach((q,i)=>{
    const xx=x(i),yy=y(Number(q.close));
    svg.insertAdjacentHTML('beforeend',
      `<circle class="hoverpoint" cx="${xx}" cy="${yy}" r="10" fill="transparent" data-i="${i}"/>`);
  });

  const tooltip=document.createElementNS('http://www.w3.org/2000/svg','g');
  tooltip.setAttribute('id','chartTip');
  tooltip.setAttribute('visibility','hidden');
  tooltip.innerHTML='<rect rx="8" width="145" height="48" fill="#172033" opacity=".94"/><text x="10" y="19" fill="#fff" font-size="12" id="tipDate"></text><text x="10" y="38" fill="#fff" font-size="14" font-weight="700" id="tipPrice"></text>';
  svg.appendChild(tooltip);
  svg.querySelectorAll('.hoverpoint').forEach(el=>{
    el.addEventListener('mouseenter',()=>{
      const i=Number(el.dataset.i),q=d[i],xx=x(i),yy=y(Number(q.close));
      const gx=Math.min(Math.max(xx-72,L),w-R-145),gy=Math.max(yy-62,4);
      tooltip.setAttribute('transform',`translate(${gx},${gy})`);
      tooltip.setAttribute('visibility','visible');
      tooltip.querySelector('#tipDate').textContent=dateLabel(q.t,RANGE);
      tooltip.querySelector('#tipPrice').textContent=money(Number(q.close),asset.currency);
    });
    el.addEventListener('mouseleave',()=>tooltip.setAttribute('visibility','hidden'));
  });
}

function decisions(){
  const c={};DATA.forEach(x=>c[x.decision]=(c[x.decision]||0)+1);
  if($('decisionBars'))$('decisionBars').innerHTML=Object.entries(c).map(([k,v])=>`<div class="barrow"><span>${k}</span><div class="track"><div class="fill" style="width:${v/(DATA.length||1)*100}%"></div></div><b>${v}</b></div>`).join('')
}


function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function renderPaperLive(pf,tr){
  const pos=tr.positions||[];
  const closed=[...(tr.closed||[])].reverse().slice(0,8);
  const events=[...(tr.events||[])].reverse().slice(0,10);
  $('paperSummaryMini').innerHTML=`<span class="papersmall">Equity <b>${money(pf.equity_mxn,'MXN')}</b> · Realizado <b class="${cls(pf.realized_pnl_mxn)}">${money(pf.realized_pnl_mxn,'MXN')}</b> · No realizado <b class="${cls(pf.unrealized_pnl_mxn)}">${money(pf.unrealized_pnl_mxn,'MXN')}</b></span>`;
  $('openPositions').innerHTML=pos.length?pos.map(p=>{
    const up=Number(p.unrealized_mxn)>=0;
    const progress=Math.max(0,Math.min(100,(Number(p.last_price_mxn)-Number(p.stop_mxn))/Math.max(.01,Number(p.target_mxn)-Number(p.stop_mxn))*100));
    return `<div class="positioncard">
      <div class="positiontop"><div><b>${esc(p.name)}</b><span>${esc(p.symbol)} · ${Number(p.shares).toLocaleString('es-MX',{maximumFractionDigits:4})} acciones</span></div><span class="paperchip">PAPER</span></div>
      <div class="positionprice"><b>${money(p.last_price_mxn,'MXN')}</b><span class="${up?'positive':'negative'}">${money(p.unrealized_mxn,'MXN')}</span></div>
      <div class="riskbar"><span style="width:${progress}%"></span></div>
      <div class="positionmeta"><span>Entrada ${money(p.entry_price_mxn,'MXN')}</span><span>Stop ${money(p.stop_mxn,'MXN')}</span><span>Target ${money(p.target_mxn,'MXN')}</span></div>
      <small>Abierta ${dt(p.opened_utc)} · ${esc(p.strategy_id||'estrategia validada')}</small>
    </div>`;
  }).join(''):`<div class="emptylive">Sin posiciones abiertas. NEXUS esperará un setup actual que coincida con una estrategia validada.</div>`;
  $('closedTrades').innerHTML=closed.length?closed.map(p=>`<div class="traderow"><span><b>${esc(p.symbol)}</b><small>${esc(p.exit_reason)}</small></span><span class="${cls(p.pnl_mxn)}"><b>${money(p.pnl_mxn,'MXN')}</b><small>${Number(p.r_multiple||0).toFixed(2)}R</small></span></div>`).join(''):'<div class="emptyline">Aún no hay operaciones cerradas.</div>';
  $('tradeEvents').innerHTML=events.length?events.map(e=>`<div class="traderow"><span><b>${esc(e.type)}</b><small>${esc(e.symbol||'')}</small></span><span><b>${e.type==='BUY'?money(e.entry_price_mxn,'MXN'):money(e.exit_price_mxn,'MXN')}</b><small>${dt(e.t)}</small></span></div>`).join(''):'<div class="emptyline">Aún no hay eventos PAPER.</div>';
}


let LAST_ALERT_ID=sessionStorage.getItem('nexusLastAlertId')||'';
async function refreshAgentOps(){
  if(!$('autonomyStatus'))return;
  try{
    const [au,dec,feed,learn]=await Promise.all([
      fetch('/api/autonomy/status?_='+Date.now(),{cache:'no-store'}).then(r=>r.json()),
      fetch('/api/agent/decisions?limit=12&_='+Date.now(),{cache:'no-store'}).then(r=>r.json()),
      fetch('/api/alerts/feed?limit=10&_='+Date.now(),{cache:'no-store'}).then(r=>r.json()),
      Promise.all([fetch('/api/learning/status?_='+Date.now(),{cache:'no-store'}).then(r=>r.json()),fetch('/api/learning/audit?_='+Date.now(),{cache:'no-store'}).then(r=>r.json()),fetch('/api/learning/counterfactual?_='+Date.now(),{cache:'no-store'}).then(r=>r.json()),fetch('/api/learning/calibration?_='+Date.now(),{cache:'no-store'}).then(r=>r.json())]).then(([learn,audit,cf,cal])=>{window.__nexusAudit=audit;window.__nexusCF=cf;window.__nexusCal=cal;return learn})
    ]);
    $('autonomyStatus').innerHTML=`<b>Estado: ${au.enabled?'ACTIVO':'INACTIVO'}</b><span>Modo: PAPER únicamente</span><span>Auto entrada PAPER: ${au.auto_open?'SÍ':'NO'} · Auto salida por PAUSA: ${au.auto_close_on_pause?'SÍ':'NO'}</span><span>Trading real automático: NO</span>`;
    $('decisionLog').innerHTML=dec.length?dec.map(d=>`<div class="traderow"><span><b>${esc(d.symbol)} · ${esc(d.action)}</b><small>${dt(d.t)} · ${esc(d.reason||'')}</small></span><span><b>${Number(d.ai_strength_score||0).toFixed(1)}/100</b><small>${d.setup_validated?'setup validado':'sin setup'}</small></span></div>`).join(''):'<div class="emptyline">Aún no hay cambios de decisión registrados.</div>';
    if($('learningStatus')){
      $('learningStatus').innerHTML=`<b>Modo: ${esc(learn.mode||'SHADOW_LEARNING')}</b><span>Muestras registradas: ${Number(learn.total_samples||0)}</span><span>Ajuste actual al score IA: ${Number(learn.ai_adjustment_points||0)>=0?'+':''}${Number(learn.ai_adjustment_points||0).toFixed(2)} puntos</span><span>Acciones fraccionarias PAPER EE.UU.: ${learn.fractional_us_enabled?'SÍ':'NO'}</span><span>Cambio automático de pesos de estrategia: NO</span>`;
      const st=learn.stats||{}; const h=st['1440']||{}; const order=['PAPER BUY','ESPERAR SETUP','ESTUDIAR','PAUSAR'];
      $('learningStats').innerHTML=order.map(a=>{const x=h[a]||{};return `<div class="traderow"><span><b>${esc(a)}</b><small>Horizonte 1 día · ${Number(x.n||0)} muestras maduras</small></span><span><b>${x.decision_hit_rate_pct==null?'—':Number(x.decision_hit_rate_pct).toFixed(1)+'%'}</b><small>Ret. medio ${x.avg_return_pct==null?'—':pct(x.avg_return_pct)}</small></span></div>`}).join('');
      if($('learningAudit')){const a=window.__nexusAudit||{};const bs=a.by_symbol||{};const arr=Object.entries(bs).sort((x,y)=>(y[1].n||0)-(x[1].n||0)).slice(0,10);$('learningAudit').innerHTML=arr.length?arr.map(([k,v])=>`<div class="traderow"><span><b>${esc(k)}</b><small>${Number(v.n||0)} muestras maduras · ${esc(v.promotion||'EXPERIMENTAL')}</small></span><span><b>${v.decision_hit_rate_pct==null?'—':Number(v.decision_hit_rate_pct).toFixed(1)+'%'}</b><small>Ret. medio ${v.avg_return_pct==null?'—':pct(v.avg_return_pct)}</small></span></div>`).join(''):'<div class="emptyline">Todavía no hay suficientes resultados maduros.</div>';}
      if($('learningMaturity')){const m=learn.maturity||{};const hs=m.horizons||[];const labels={60:'1 hora',1440:'1 día',7200:'5 días'};let html=hs.map(x=>`<div class="traderow"><span><b>${labels[x.minutes]||x.minutes+' min'}</b><small>${Number(x.pending||0)} pendientes</small></span><span><b>${Number(x.matured||0)} maduras</b><small>${Number(x.coverage_pct||0).toFixed(1)}% cobertura</small></span></div>`).join('');html+=`<div class="traderow"><span><b>Ajuste IA acotado</b><small>Requiere ${Number(m.required_1d_paper_buy_samples||30)} PAPER BUY maduras a 1 día</small></span><span><b>${m.adjustment_ready?'LISTO':'ESPERANDO'}</b><small>Faltan ${Number(m.remaining_1d_paper_buy_samples||0)}</small></span></div>`;$('learningMaturity').innerHTML=html;}
      if($('counterfactual')){const cf=window.__nexusCF||{};const c=cf.counts||{};const rows=[['Oportunidades perdidas',c.OPORTUNIDAD_PERDIDA||0],['Entradas evitadas correctamente',c.ENTRADA_EVITADA||0],['Compras favorables',c.COMPRA_FAVORABLE||0],['Compras desfavorables',c.COMPRA_DESFAVORABLE||0]];$('counterfactual').innerHTML=rows.map(x=>`<div class="traderow"><span><b>${x[0]}</b><small>Horizonte PAPER 1 día</small></span><span><b>${x[1]}</b><small>eventos maduros</small></span></div>`).join('');}
      if($('calibration')){const cal=window.__nexusCal||{};const h=(cal.horizons||{})['1440']||{};const acts=['PAPER BUY','ESPERAR SETUP','ESTUDIAR','PAUSAR'];$('calibration').innerHTML=acts.map(a=>{const x=h[a]||{};return `<div class="traderow"><span><b>${esc(a)}</b><small>${Number(x.n||0)} maduras · evidencia ${esc(x.evidence||'INSUFICIENTE')}</small></span><span><b>${x.avg_net_after_friction_pct==null?'—':pct(x.avg_net_after_friction_pct)}</b><small>Neto fricción · bruto ${x.avg_gross_return_pct==null?'—':pct(x.avg_gross_return_pct)}</small></span></div>`}).join('');}

    }
    if(feed.length){
      const newest=feed[0];
      if(newest.id!==LAST_ALERT_ID){
        const unseen=[];for(const a of feed){if(a.id===LAST_ALERT_ID)break;unseen.push(a)}
        unseen.reverse().forEach(a=>browserAlert(a.title,a.body));
        LAST_ALERT_ID=newest.id;sessionStorage.setItem('nexusLastAlertId',LAST_ALERT_ID);
      }
    }
  }catch(e){console.error('agent ops',e)}
}

async function refresh(opts={}){
  const keepSymbol=opts.forceSymbol || CURRENT?.symbol || $('symbol')?.value || null;
  const q=`?_=${Date.now()}`;
  const [st,wl,bm,pf,eq,tr]=await Promise.all([
    fetch('/api/status'+q,{cache:'no-store'}).then(r=>r.json()),
    fetch('/api/watchlist'+q,{cache:'no-store'}).then(r=>r.json()),
    fetch('/api/benchmarks'+q,{cache:'no-store'}).then(r=>r.json()),
    fetch('/api/portfolio'+q,{cache:'no-store'}).then(r=>r.json()),
    fetch('/api/equity'+q,{cache:'no-store'}).then(r=>r.json()),
    fetch('/api/trades'+q,{cache:'no-store'}).then(r=>r.json())
  ]);
  DATA=wl;
  $('status').textContent='ACTIVO · LIVE PAPER';
  $('last').textContent=dt(st.last_scan_utc);
  $('count').textContent=st.assets_scanned??0;
  $('cheap').textContent=st.cheap_mexican_count??0;
  $('fx').textContent=st.usdmxn?Number(st.usdmxn).toFixed(2):'—';

  const rt=st.runtime||{};
  $('onlineState').textContent=rt.last_scan_ok===false?'Error en último escaneo':'Servidor activo';
  $('onlineState').className=rt.last_scan_ok===false?'negative':'positive';
  $('scanCadence').textContent=`cada ${st.scan_minutes||5} min`;
  $('liveCadence').textContent=`cada ${st.live_update_minutes||2} min`;
  $('lastLive').textContent=rt.last_live_update_utc?dt(rt.last_live_update_utc):'esperando primera marca';

  $('bench').innerHTML=bm.map(x=>`<div class="mini"><b>${x.name}</b><p>1M <span class="${cls(x.ret_1m)}">${pct(x.ret_1m)}</span> · YTD <span class="${cls(x.ret_ytd)}">${pct(x.ret_ytd)}</span></p></div>`).join('');
  $('portfolio').innerHTML=`<div class="mini"><b>${money(pf.equity_mxn,'MXN')}</b><p>Equity PAPER</p></div><div class="mini"><b class="${cls(pf.total_pnl_mxn)}">${money(pf.total_pnl_mxn,'MXN')}</b><p>P/L total</p></div><div class="mini"><b>${pf.win_rate_pct}%</b><p>Win rate</p></div><div class="mini"><b>${(pf.positions||[]).length}</b><p>Posiciones abiertas</p></div>`;
  renderPaperLive(pf,tr);

  $('symbol').innerHTML=DATA.map(x=>`<option value="${x.symbol}">${x.symbol} · ${x.name}</option>`).join('');
  if($('orderSymbol'))$('orderSymbol').innerHTML=DATA.map(x=>`<option value="${x.symbol}">${x.symbol} · ${x.name}</option>`).join('');
  rows();decisions();
  const target=(keepSymbol && DATA.some(x=>x.symbol===keepSymbol))?keepSymbol:(DATA[0]?.symbol||null);
  if(target){
    $('symbol').value=target;
    await select(target,{initial:!CURRENT});
  }
  await refreshAgentOps();
}

async function validate(mode){
  if(!CURRENT)return;
  const symbol=CURRENT.symbol;
  const b=mode==='full'?$('validateFull'):$('validateQuick');
  const old=b.textContent;b.disabled=true;b.textContent=mode==='full'?'Validando 1,800…':'Validando…';
  $('sens').innerHTML='<p>Ejecutando backtest. No cierres esta pestaña…</p>';
  try{
    const r=await fetch(`/api/validate/${encodeURIComponent(symbol)}?mode=${mode}&_=${Date.now()}`,{method:'POST',cache:'no-store'});
    const d=await r.json();
    renderLab(d);
    await refresh({forceSymbol:symbol}); // cerebro y laboratorio quedan sincronizados
  }finally{b.disabled=false;b.textContent=old}
}

document.querySelectorAll('.filter').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');FILTER=b.dataset.f;rows()
});
document.querySelectorAll('.range').forEach(b=>b.onclick=async()=>{
  document.querySelectorAll('.range').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');RANGE=b.dataset.range;
  if(CURRENT)await select(CURRENT.symbol)
});
$('symbol').onchange=()=>select($('symbol').value);
$('validateQuick').onclick=()=>validate('quick');
$('validateFull').onclick=()=>validate('full');
$('run').onclick=async()=>{
  const b=$('run');const symbol=CURRENT?.symbol;
  b.disabled=true;b.textContent='Analizando…';
  try{
    await fetch('/api/run-now?_'+Date.now(),{method:'POST',cache:'no-store'});
    await refresh({forceSymbol:symbol});
  }finally{b.disabled=false;b.textContent='Analizar ahora'}
};


$('liveNow').onclick=async()=>{
  const b=$('liveNow');b.disabled=true;const old=b.textContent;b.textContent='Actualizando…';
  try{
    await fetch('/api/live-now?_'+Date.now(),{method:'POST',cache:'no-store'});
    await refresh({forceSymbol:CURRENT?.symbol});
  }finally{b.disabled=false;b.textContent=old}
};


if($('paperBuy'))$('paperBuy').onclick=()=>paperOrder('BUY');
if($('paperSell'))$('paperSell').onclick=()=>paperOrder('SELL');
if($('enableBrowserAlerts'))$('enableBrowserAlerts').onclick=async()=>{
  if(!('Notification' in window)){$('alertStatus').textContent='Este navegador no soporta notificaciones.';return}
  const p=await Notification.requestPermission();$('alertStatus').textContent=p==='granted'?'Alertas del navegador activadas.':'Permiso de alertas no concedido.';
};
if($('testTelegram'))$('testTelegram').onclick=async()=>{
  $('alertStatus').textContent='Probando Telegram…';
  try{const d=await fetch('/api/alerts/test',{method:'POST'}).then(r=>r.json());$('alertStatus').textContent=d.ok?'Telegram respondió correctamente.':`Telegram pendiente: ${d.error||'sin configurar'}`;}catch(e){$('alertStatus').textContent='No se pudo probar Telegram.'}
};
initControlCenter();

// La gráfica aparece desde el primer arranque.
refresh().catch(e=>{
  console.error(e);
  $('chartTitle').textContent='No se pudo cargar el activo inicial';
});
setInterval(()=>refresh({forceSymbol:CURRENT?.symbol}),30000);


async function loadRiskGovernor(){
 if(!$('riskGovernor'))return;
 try{
  const [g,st]=await Promise.all([fetch('/api/risk-governor/status',{cache:'no-store'}).then(r=>r.json()),fetch('/api/risk-governor/stress',{cache:'no-store'}).then(r=>r.json())]);
  $('riskGovernor').innerHTML=`<b>Estado: ${esc(g.level||'—')}</b><span>Nuevas entradas PAPER: ${g.block_new_entries?'BLOQUEADAS':'permitidas'}</span><span>Exposición ${Number(g.exposure_pct||0).toFixed(1)}% · pérdida diaria ${Number(g.daily_loss_pct||0).toFixed(2)}% · drawdown ${Number(g.drawdown_pct||0).toFixed(2)}%</span><span>Mayor sector ${Number(g.max_sector_exposure_pct||0).toFixed(1)}%</span><small>${esc((g.reasons||[]).join(' · '))}</small>`;
  $('stressTests').innerHTML=(st.scenarios||[]).map(x=>`<div class="labrow"><b>${esc(x.name)}</b><span>Equity estrés ${money(x.equity_stressed_mxn,'MXN')} · impacto ${Number(x.loss_pct||0).toFixed(2)}% · shock ${Number(x.shock_pct||0).toFixed(1)}%</span></div>`).join('')||'<div class="emptyline">Sin escenarios.</div>';
 }catch(e){$('riskGovernor').textContent='No se pudo calcular el Risk Governor.'}
}
setTimeout(loadRiskGovernor,1200);setInterval(loadRiskGovernor,60000);

// V0.17 — IBKR Broker Gateway (READ / WHAT-IF / DRAFT only)
async function loadBrokerGateway(){
 if(!$('brokerStatus'))return;
 try{
  const d=await fetch('/api/broker/status',{cache:'no-store'}).then(r=>r.json());
  $('brokerStatus').innerHTML=`<b>IBKR Gateway: ${d.enabled?(d.authenticated?'AUTENTICADO':'CONFIGURADO / SIN SESIÓN'):'DESHABILITADO'}</b><span>Modo: ${esc(d.mode||'READ_PREVIEW_ONLY')}</span><span>Conectado: ${d.connected?'SÍ':'NO'} · Autenticado: ${d.authenticated?'SÍ':'NO'} · Cuenta configurada: ${d.account_configured?'SÍ':'NO'}</span><span>Transmisión real desde NEXUS: BLOQUEADA</span><small>${esc(d.message||'')} ${esc(d.render_note||'')}</small>`;
 }catch(e){$('brokerStatus').textContent='No se pudo consultar el Broker Gateway.'}
}
async function brokerAction(kind){
 const body={conid:Number($('brokerConid').value||0),side:$('brokerSide').value,quantity:Number($('brokerQty').value||0),price:Number($('brokerPrice').value||0),order_type:'LMT',tif:'DAY',symbol:CURRENT?.symbol||null,reason:CURRENT?.ai_action||null};
 $('brokerResult').textContent=kind==='preview'?'Solicitando What-If a IBKR…':'Creando borrador auditable…';
 try{
  const r=await fetch(`/api/broker/${kind}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'});
  const d=await r.json();
  if(kind==='draft'&&d.ok){$('brokerResult').textContent='Borrador creado. NO fue transmitido al mercado.';return}
  if(d.ok){const x=d.data||{};$('brokerResult').textContent=`What-If recibido. Comisión: ${x.amount?.commission||'—'} · Total: ${x.amount?.total||'—'} · Aviso: ${x.warn||'sin aviso'}`}
  else $('brokerResult').textContent=`No disponible: ${d.error||'sin conexión/autenticación IBKR'}`;
 }catch(e){$('brokerResult').textContent='No se pudo completar la consulta al Broker Gateway.'}
}
if($('brokerPreview'))$('brokerPreview').onclick=()=>brokerAction('preview');
if($('brokerDraft'))$('brokerDraft').onclick=()=>brokerAction('draft');
loadBrokerGateway();setInterval(loadBrokerGateway,60000);

// V0.17 — IBKR Broker Gateway (READ / WHAT-IF / DRAFT only)
async function loadBrokerGateway(){
 if(!$('brokerStatus'))return;
 try{const d=await fetch('/api/broker/status',{cache:'no-store'}).then(r=>r.json());$('brokerStatus').innerHTML=`<b>IBKR Gateway: ${d.enabled?(d.authenticated?'AUTENTICADO':'CONFIGURADO / SIN SESIÓN'):'DESHABILITADO'}</b><span>Modo: ${esc(d.mode||'READ_PREVIEW_ONLY')}</span><span>Conectado: ${d.connected?'SÍ':'NO'} · Autenticado: ${d.authenticated?'SÍ':'NO'} · Cuenta configurada: ${d.account_configured?'SÍ':'NO'}</span><span>Transmisión real desde NEXUS: BLOQUEADA</span><small>${esc(d.message||'')} ${esc(d.render_note||'')}</small>`;}catch(e){$('brokerStatus').textContent='No se pudo consultar el Broker Gateway.'}
}
async function brokerAction(kind){
 const body={conid:Number($('brokerConid').value||0),side:$('brokerSide').value,quantity:Number($('brokerQty').value||0),price:Number($('brokerPrice').value||0),order_type:'LMT',tif:'DAY',symbol:CURRENT?.symbol||null,reason:CURRENT?.ai_action||null};
 $('brokerResult').textContent=kind==='preview'?'Solicitando What-If a IBKR…':'Creando borrador auditable…';
 try{const r=await fetch(`/api/broker/${kind}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'});const d=await r.json();if(kind==='draft'&&d.ok){$('brokerResult').textContent='Borrador creado. NO fue transmitido al mercado.';return}if(d.ok){const x=d.data||{};$('brokerResult').textContent=`What-If recibido. Comisión: ${x.amount?.commission||'—'} · Total: ${x.amount?.total||'—'} · Aviso: ${x.warn||'sin aviso'}`}else $('brokerResult').textContent=`No disponible: ${d.error||'sin conexión/autenticación IBKR'}`;}catch(e){$('brokerResult').textContent='No se pudo completar la consulta al Broker Gateway.'}
}
if($('brokerPreview'))$('brokerPreview').onclick=()=>brokerAction('preview');if($('brokerDraft'))$('brokerDraft').onclick=()=>brokerAction('draft');loadBrokerGateway();setInterval(loadBrokerGateway,60000);

// V0.17.1 - Local Broker Bridge TWS PAPER / SOLO LECTURA
loadBrokerGateway = async function(){
 if(!$('brokerStatus'))return;
 try{
  const d=await fetch('/api/broker/status?_='+Date.now(),{cache:'no-store'}).then(r=>r.json());
  if(d.local_bridge){
   $('brokerStatus').innerHTML=`<b>IBKR TWS Paper: ${d.local_bridge_connected?'CONECTADO':'SIN CONEXIÓN'}</b><span>Puente: NEXUS LOCAL BROKER BRIDGE</span><span>Modo: ${esc(d.mode||'TWS_PAPER_READ_ONLY')}</span><span>Último reporte: ${d.local_bridge_received_utc?dt(d.local_bridge_received_utc):'—'}</span><span>Transmisión real desde NEXUS: BLOQUEADA</span><small>${esc(d.local_bridge_message||'')}</small>`;
  }else{
   $('brokerStatus').innerHTML=`<b>IBKR TWS Paper: ESPERANDO PUENTE LOCAL</b><span>Modo: PAPER / SOLO LECTURA</span><span>Transmisión real desde NEXUS: BLOQUEADA</span><small>${esc(d.local_bridge_message||'Esperando primer reporte desde la PC.')}</small>`;
  }
 }catch(e){$('brokerStatus').textContent='No se pudo consultar el Broker Gateway.'}
};
loadBrokerGateway();


// V0.17.7 FINAL IBKR PAPER BRIDGE
function brokerMoney(v,c='USD'){if(v===null||v===undefined||Number.isNaN(Number(v)))return '-';try{return new Intl.NumberFormat('es-MX',{style:'currency',currency:c,maximumFractionDigits:2}).format(Number(v))}catch(e){return Number(v).toFixed(2)+' '+c}}
loadBrokerGateway=async function(){if(!$('brokerStatus'))return;try{const d=await fetch('/api/broker/status?_='+Date.now(),{cache:'no-store'}).then(r=>r.json());const on=!!d.local_bridge_connected,a=d.local_bridge_account||{},cur=a.currency||'USD',age=d.local_bridge_age_seconds,ag=age==null?'-':age<60?'hace '+age+' s':'hace '+Math.floor(age/60)+' min';$('brokerStatus').innerHTML='<b>IBKR PAPER: '+(on?'CONECTADO':'OFFLINE')+'</b><span>Bridge local: '+(on?'ONLINE':'OFFLINE')+' | V'+esc(d.local_bridge_version||'-')+'</span><span>TWS API: '+(on?'CONECTADA':'SIN REPORTE RECIENTE')+'</span><span>Modo: PAPER READ-ONLY</span><span>Ultimo reporte: '+(d.local_bridge_received_utc?dt(d.local_bridge_received_utc):'-')+' | '+ag+'</span><span>PC a Render: '+(on?'CONECTADO':'OFFLINE')+'</span><span>Transmision de ordenes reales: BLOQUEADA</span><small>'+esc(d.local_bridge_message||'')+'</small>';if($('brokerAccount'))$('brokerAccount').innerHTML='<div class="mini"><b>'+brokerMoney(a.net_liquidation??a.NetLiquidation??a.netLiquidation,cur)+'</b><p>Net Liquidation PAPER</p></div><div class="mini"><b>'+brokerMoney(a.total_cash??a.TotalCashValue??a.totalCash,cur)+'</b><p>Total Cash PAPER</p></div><div class="mini"><b>'+brokerMoney(a.available_funds??a.AvailableFunds??a.availableFunds,cur)+'</b><p>Available Funds PAPER</p></div><div class="mini"><b>'+Number(d.local_bridge_positions_count||0)+'</b><p>Posiciones IBKR Paper</p></div>'}catch(e){$('brokerStatus').innerHTML='<b>IBKR PAPER: OFFLINE</b><span>Transmision real: BLOQUEADA</span>'}};
loadBrokerGateway();setInterval(loadBrokerGateway,15000);

// V0.17.9 - CONCILIACION NEXUS PAPER vs IBKR PAPER
async function loadBrokerReconciliation(){
 if(!$('brokerReconciliation'))return;
 try{
  const d=await fetch('/api/broker/reconciliation?_='+Date.now(),{cache:'no-store'}).then(r=>r.json());
  if(!d.bridge_connected){$('brokerReconciliation').innerHTML='<div class="emptyline">Bridge IBKR PAPER sin reporte reciente. Se actualizara automaticamente.</div>';return;}
  const rows=d.rows||[];
  let head='<div class="traderow"><span><b>Estado</b><small>Ultima sincronizacion '+(d.last_sync_utc?dt(d.last_sync_utc):'-')+'</small></span><span><b>'+(d.matched?'COINCIDE':'REVISAR')+'</b><small>'+Number(d.differences_count||0)+' diferencias</small></span></div>';
  let body=rows.length?rows.map(x=>'<div class="traderow"><span><b>'+esc(x.symbol)+'</b><small>NEXUS '+Number(x.nexus_qty||0).toLocaleString('es-MX',{maximumFractionDigits:6})+' | IBKR '+Number(x.ibkr_qty||0).toLocaleString('es-MX',{maximumFractionDigits:6})+'</small></span><span><b>'+(x.match?'OK':'DIFERENCIA')+'</b><small>Delta '+Number(x.difference_qty||0).toLocaleString('es-MX',{maximumFractionDigits:6})+'</small></span></div>').join(''):'<div class="emptyline">Sin posiciones abiertas en ninguno de los dos PAPER.</div>';
  $('brokerReconciliation').innerHTML=head+body;
 }catch(e){$('brokerReconciliation').innerHTML='<div class="emptyline">No se pudo consultar la conciliacion.</div>';}
}
loadBrokerReconciliation();
setInterval(loadBrokerReconciliation,15000);




// V0.21 — mobile app shell + PWA install
(function(){
  const nav=[...document.querySelectorAll('.bottomNav a')];
  function mark(){let best=nav[0];let dist=1e9;nav.forEach(a=>{const el=document.querySelector(a.getAttribute('href'));if(el){const d=Math.abs(el.getBoundingClientRect().top-90);if(d<dist){dist=d;best=a}}});nav.forEach(a=>a.classList.toggle('active',a===best));}
  nav.forEach(a=>a.addEventListener('click',()=>{nav.forEach(x=>x.classList.remove('active'));a.classList.add('active')}));
  window.addEventListener('scroll',()=>requestAnimationFrame(mark),{passive:true});mark();
  if('serviceWorker' in navigator) navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
  let deferred=null;const bar=document.getElementById('installBar'),btn=document.getElementById('installApp'),dismiss=document.getElementById('dismissInstall');
  window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferred=e;if(bar&&!sessionStorage.getItem('nexusInstallDismissed'))bar.hidden=false});
  if(btn)btn.onclick=async()=>{if(!deferred)return;deferred.prompt();await deferred.userChoice;deferred=null;bar.hidden=true};
  if(dismiss)dismiss.onclick=()=>{bar.hidden=true;sessionStorage.setItem('nexusInstallDismissed','1')};
  window.addEventListener('appinstalled',()=>{if(bar)bar.hidden=true});
})();
