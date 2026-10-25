
'use strict';
const paths={
grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
orbit:'<circle cx="12" cy="12" r="3"/><ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(-35 12 12)"/><circle cx="18.5" cy="6.6" r="1.5" fill="currentColor"/>',
rocket:'<path d="M13 5c3-3 6-3 7-3 0 1 0 4-3 7l-7 7-5-5 8-6Z"/><path d="m10 6-6 1-2 5 5-1m8 3-1 6-5 2 1-6M5 15l-3 7 7-3"/><circle cx="15" cy="7" r="1.5"/>',
shield:'<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4Z"/><path d="m8 12 3 3 5-6"/>',
pulse:'<path d="M2 12h4l3-8 5 16 3-8h5"/>',
layers:'<path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5"/>',
globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 6h14M5 18h14"/>',
check:'<path d="m5 12 4 4 10-10"/>',
checkcircle:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 6-6"/>',
file:'<path d="M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8M8 16h6"/>',
branch:'<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="6" r="2"/><path d="M6 7v10m0-3c8 0 12-2 12-6"/>',
chevron:'<path d="m9 5 7 7-7 7"/>',
arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
arrowup:'<path d="M5 19 19 5M5 5h14v14"/>',
down:'<path d="m6 9 6 6 6-6"/>',
search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
pause:'<path d="M8 5v14M16 5v14"/>',
play:'<path d="m8 4 12 8-12 8V4Z"/>',
close:'<path d="m5 5 14 14M5 19 19 5"/>',
plug:'<path d="M8 2v5m8-5v5M6 7h12v4a6 6 0 0 1-12 0V7Zm6 10v5"/>',
sliders:'<path d="M4 4v16M12 4v16M20 4v16M1 9h6m2 7h6m2-9h6"/>',
clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
alert:'<path d="m12 3 10 18H2L12 3Zm0 6v5m0 3v.1"/>',
lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 4v3"/>',
download:'<path d="M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6"/>',
menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
code:'<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-14-2 18"/>',
chart:'<path d="M4 3v18h18M8 15l4-6 4 3 5-7"/>',
spark:'<path d="m12 2 2.7 7.3L22 12l-7.3 2.7L12 22l-2.7-7.3L2 12l7.3-2.7L12 2Z"/>',
refresh:'<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
server:'<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.1M7 17.5h.1M12 6.5h6M12 17.5h6"/>',
filter:'<path d="M3 5h18l-7 8v6l-4 2v-8L3 5Z"/>',
stop:'<rect x="6" y="6" width="12" height="12" rx="2"/>'
};
const icon=(name)=>'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'+(paths[name]||paths.spark)+'</svg>';
const esc=(s)=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const NAV=[['overview','Mission control','grid'],['agents','Agent fleet','orbit'],['releases','Releases','rocket'],['incidents','Incidents','pulse'],['sites','Site intelligence','globe'],['approvals','Approvals','shield'],['reports','Reports','file']];

function spark(n){const points=['0,25 8,23 15,25 23,12 30,17 37,14 44,18 51,7 60,10 70,2','0,24 8,24 16,18 24,18 32,20 40,10 48,14 56,7 63,8 70,3','0,23 8,20 16,18 24,19 32,10 40,12 48,5 56,7 64,5 70,6','0,20 10,20 18,11 26,11 34,18 42,18 50,9 60,9 70,9'][n%4];return '<svg class="spark" viewBox="0 0 70 30" aria-hidden="true"><polyline points="'+points+'" fill="none" stroke="var(--accent)" stroke-width="1.5"/><path d="M0 29h70" stroke="#2a3435" stroke-dasharray="2 3"/></svg>';}

function pipeline(stage){const names=['Build','Quality','Verify','Approve','Deploy'];return '<div class="pipeline">'+names.map((n,k)=>'<div class="pipeline-step '+(k<stage?'done':k===stage?'current':'')+'"><span class="step-orb">'+(k<stage?icon('check'):String(k+1).padStart(2,'0'))+'</span><span>'+n+'</span></div>').join('')+'</div>';}

let AGENTS=[],SITES=[];
const state={page:location.hash.slice(2)||'overview',motion:!matchMedia('(prefers-reduced-motion: reduce)').matches,accent:'lime',env:'stage',runs:[],approvals:[],reports:[],events:[],activeAgent:null,siteFilter:'all',siteSearch:'',releaseFilter:'all',approvalId:null,approvalTab:'summary',connected:false,csrf:null,provider:'fixture',busy:false};
let frame=0,hoveredAgent=null,lastFocus=null,pollTimer=null,snapshotHash='',commandKey=null;
const main=document.getElementById('main'),modal=document.getElementById('modal');
const pill=(text,color='')=>'<span class="pill '+color+'">'+esc(text)+'</span>';
const btn=(label,action,style='',attrs='')=>'<button class="btn '+style+'" data-action="'+action+'" '+attrs+'>'+label+'</button>';
const requestKey=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
const role=id=>AGENTS.find(a=>a.id===id);
const scopedRuns=()=>state.runs.filter(r=>r.request.environment===state.env);
const scopedApprovals=()=>state.approvals.filter(a=>a.payload.environment===state.env);
const pending=()=>scopedApprovals().filter(a=>a.status==='pending').length;
const active=()=>scopedRuns().find(r=>['running','queued'].includes(r.status));
const short=id=>id.slice(0,12);
const date=v=>new Date(v).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
const color=s=>['failed','declined'].includes(s)?'red':['queued','running','pending','awaiting_review','inconclusive'].includes(s)?'amber':'green';
const labels={release:'Release verification',incident:'Incident investigation',reporting:'Platform brief'};
const footer=()=>'<footer class="page-footer"><span>'+icon('lock')+' AAAEM PLATFORM · STANDALONE SYSTEM</span><span>LOCAL WORKSPACE · FIXTURE INTEGRATIONS</span></footer>';
function head(title,desc,action){return '<div class="heading"><div><div class="eyebrow"><span class="dot"></span>Intelligence in operation</div><h1>'+title+'</h1><p class="subtitle">'+desc+'</p></div><div class="actions">'+(action||btn(icon('play')+'Start an agent run','launch','primary'))+'</div></div>';}
function empty(title,desc,action='launch'){return '<div class="panel run-empty">'+icon('orbit')+'<h3>'+title+'</h3><p>'+desc+'</p>'+btn('Start an agent run '+icon('arrow'),action,'primary')+'</div>';}
function toast(title,detail=''){const el=document.createElement('div');el.className='toast';el.innerHTML=icon('checkcircle')+'<div>'+esc(title)+(detail?'<small>'+esc(detail)+'</small>':'')+'</div>';document.getElementById('toasts').append(el);setTimeout(()=>el.remove(),5000);}
function hydrateIcons(){document.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);el.removeAttribute('data-icon')});}
function setMotion(value){state.motion=value;document.body.classList.toggle('motion-off',!value);const b=document.getElementById('motion-button');b.innerHTML=icon(value?'pause':'play');b.setAttribute('aria-label',value?'Pause decorative motion':'Enable decorative motion');if(state.page==='overview')startNetwork();}
function render(){
 cancelAnimationFrame(frame);
 if(!['overview','agents','releases','incidents','sites','approvals','reports','integrations'].includes(state.page))state.page='overview';
 document.getElementById('navigation').innerHTML=NAV.map(n=>'<button class="nav-item '+(state.page===n[0]?'active':'')+'" data-nav="'+n[0]+'" aria-label="'+n[1]+'" title="'+n[1]+'" '+(state.page===n[0]?'aria-current="page"':'')+'>'+icon(n[2])+'<span>'+n[1]+'</span>'+(n[0]==='approvals'?'<b class="count">'+pending()+'</b>':'')+'</button>').join('');
 document.querySelector('[data-nav="integrations"]').classList.toggle('active',state.page==='integrations');
 document.getElementById('breadcrumb-title').textContent=(NAV.find(n=>n[0]===state.page)||['','Integrations'])[1];
 state.activeAgent=active()?.kind||null;
 const views={overview,agents:fleet,releases:()=>runPage('release'),incidents:()=>runPage('incident'),sites,approvals,reports,integrations};
 main.innerHTML='<div>'+views[state.page]()+'</div>';
 if(state.page==='overview')startNetwork();
 hydrateIcons();
}
function navigate(page){state.page=page;location.hash='/'+page;document.getElementById('sidebar').classList.remove('open');closeModal();render();window.scrollTo({top:0,behavior:state.motion?'smooth':'instant'});}
function openModal(content,drawer=false){if(!modal.open)lastFocus=document.activeElement;modal.className=drawer?'drawer-dialog':'';modal.innerHTML=content;if(!modal.open)modal.showModal();}
function closeModal(){if(modal.open)modal.close();if(lastFocus?.isConnected)lastFocus.focus();}
function modalHeader(kicker,title,desc=''){return '<div class="modal-head"><div><div class="eyebrow">'+esc(kicker)+'</div><h2>'+esc(title)+'</h2><p>'+esc(desc)+'</p></div><button class="icon-button" data-action="close" aria-label="Close dialog">'+icon('close')+'</button></div>';}
function metrics(){const r=scopedRuns();return '<div class="metrics">'+[
 ['Sites registered',SITES.length,'Fixture registry',0],['Phase 1 agents','3<small> / 6</small>','Plus the Ops dispatcher',1],
 ['Drafts prepared',r.filter(x=>x.result).length,'Persisted in your workspace',2],['Awaiting review',String(pending()).padStart(2,'0'),'Draft acceptance only',3]
 ].map(x=>'<div class="metric"><div class="metric-title">'+x[0]+'</div><div class="metric-number">'+x[1]+'</div>'+spark(x[3])+'<div class="metric-foot">'+x[2]+'</div></div>').join('')+'</div>';}
function activity(){const ids=new Set(scopedRuns().map(r=>r.id));return state.events.filter(e=>!e.run_id||ids.has(e.run_id)).slice(0,5).map(e=>'<div class="event"><div class="event-icon">'+icon(role(e.agent)?.icon||'checkcircle')+'</div><div class="event-content"><strong>'+esc(e.title)+'</strong><p>'+esc(e.detail)+'</p><time>'+date(e.created_at)+'</time></div></div>').join('')||'<div class="empty">Activity will appear as runs progress.</div>';}
function agentNodes(){const positions=[[19,22],[81,22],[16,50],[84,50],[19,78],[81,78]];return AGENTS.slice(1).map((a,n)=>'<button class="agent-node '+(!a.enabled?'planned ':'')+(state.activeAgent===a.id?'working':'')+'" style="--x:'+positions[n][0]+'%;--y:'+positions[n][1]+'%" data-action="agent" data-id="'+a.id+'" aria-label="Inspect '+esc(a.name)+'"><span class="node-top">'+icon(a.icon)+esc(a.name)+'</span><span class="node-bottom"><span><span class="dot"></span> '+(state.activeAgent===a.id?'PROCESSING':a.enabled?'READY':'PHASE '+a.phase)+'</span><span class="node-code">'+a.code.slice(-2)+'</span></span></button>').join('');}
function runStrip(){const r=active();if(!r)return '';return '<div class="simulation-strip">'+icon('orbit')+'<strong>'+labels[r.kind]+'</strong><div class="bar"><i style="width:'+(r.status==='queued'?10:60)+'%"></i></div><span class="phase">'+esc(r.stage)+'</span><button class="text-btn" data-action="run-detail" data-id="'+r.id+'">Inspect '+icon('arrow')+'</button></div>';}
function siteStatus(){const map=new Map(SITES.map(s=>[s.id,{...s,status:'not_checked',checks:null}]));for(const r of scopedRuns().filter(r=>r.kind==='release'&&r.result).reverse()){const d=r.result.details;for(const id of d.site_ids){const s=map.get(id);if(!s)continue;const check=d.site_results.find(x=>x.id===id);s.status=!check?'unknown':check.passed===check.total?'healthy':'fail';s.checks=check?.passed??null;s.run_id=r.id;}}return [...map.values()];}
function overview(){const latest=scopedRuns().find(r=>r.kind==='release'),health=siteStatus();return head('Mission control','Seven agent roles. A persistent workspace. Every decision in view.',btn(icon('globe')+state.env.charAt(0).toUpperCase()+state.env.slice(1)+' environment','environment')+btn(icon('play')+'Start an agent run','launch','primary'))+runStrip()+metrics()+
 '<div class="workspace-grid"><section class="panel"><div class="panel-head"><div><h2>Agent constellation</h2><p>Specialists working together, with you in control.</p></div>'+pill('3 SPECIALISTS READY','green')+'</div><div class="constellation"><canvas id="network-canvas" aria-hidden="true"></canvas><span class="orbit-label">DISTRIBUTED INTELLIGENCE / SHARED CONTEXT</span>'+agentNodes()+'<button class="core-button" data-action="agent" data-id="core" aria-label="Inspect Ops orchestrator"><span class="core-label"><strong>Ops orchestrator</strong><span>'+(active()?'COORDINATING WORKFLOW':'CONNECTING THE PLATFORM')+'</span></span></button></div><div class="graph-footer"><div class="legend"><span><i class="dot"></i>PHASE 1</span><span>FADED · PLANNED</span></div><span>SELECT AN AGENT TO EXPLORE ↗</span></div></section>'+
 '<section class="panel activity"><div class="panel-head"><h2>Activity stream</h2><span class="live-tag"><i class="dot pulsing"></i>LOCAL BACKEND</span></div><div class="activity-list">'+activity()+'</div><div class="activity-footer"><span>Evidence follows every action</span><button class="text-btn" data-nav="reports">View reports '+icon('arrow')+'</button></div></section></div>'+
 '<div class="bottom-grid"><section class="panel"><div class="panel-head"><h2>Release journey</h2><span class="panel-kicker">'+(latest?short(latest.id):'READY TO BEGIN')+'</span></div><div class="panel-body">'+(latest?'<div class="release-info"><div class="release-icon">'+icon('rocket')+'</div><div><h3>'+labels.release+'</h3><p>'+esc(latest.request.environment)+' · '+esc(latest.result?.revision||'Collecting revision')+'</p></div>'+pill(latest.result?.assessment||latest.status,color(latest.result?.assessment||latest.status))+'</div>'+pipeline(latest.result?3:1)+'<div class="release-bottom"><p><b>'+esc(latest.stage)+'</b><br>Review is a draft acknowledgment.</p>'+btn('Inspect run '+icon('arrow'),'run-detail','small-btn','data-id="'+latest.id+'"')+'</div>':'<p class="subtitle" style="margin-bottom:20px">Start the first release run to collect scoped evidence and prepare a reviewable dossier.</p>'+btn('Verify a release '+icon('arrow'),'launch','small-btn','data-id="release"'))+'</div></section>'+
 '<section class="panel"><div class="panel-head"><h2>Site intelligence</h2><button class="text-btn" data-nav="sites">Explore sites '+icon('arrowup')+'</button></div><div class="panel-body"><div class="site-mini-grid">'+health.map(s=>'<button class="site-tile '+(s.status==='healthy'?'':s.status==='fail'?'fail':'unknown')+'" data-action="site" data-id="'+s.id+'" aria-label="'+esc(s.name+' '+s.market+', '+s.status)+'" title="'+esc(s.name+' / '+s.market+' — '+s.status)+'"></button>').join('')+'</div><div class="site-legend"><span><i class="dot"></i>'+health.filter(s=>s.status==='healthy').length+' passed</span><span>'+health.filter(s=>s.status==='fail').length+' need review</span><span>'+health.filter(s=>!['healthy','fail'].includes(s.status)).length+' not verified</span></div></div></section></div>'+footer();}
function fleet(){return head('Meet your agent team','Three specialists are executable today. The remaining roles have explicit delivery phases.')+'<div class="fleet-grid">'+AGENTS.map(a=>'<button class="panel fleet-card" data-action="agent" data-id="'+a.id+'"><div class="agent-art">'+icon(a.icon)+'</div><div><span class="upper muted">'+a.code+'</span><h2 class="fleet-name">'+esc(a.name)+'</h2><p class="fleet-description">'+esc(a.description)+'</p><div class="fleet-foot">'+pill(a.enabled?a.mode:'Phase '+a.phase+' · planned',a.enabled?'green':'')+'<span class="text-btn">Explore agent '+icon('arrowup')+'</span></div></div></button>').join('')+'</div>'+footer();}
function agentDetail(id){const a=role(id);if(!a)return;openModal(modalHeader(a.code,a.name,a.description)+'<div class="drawer-hero"><div class="agent-art">'+icon(a.icon)+'</div></div><div class="modal-body">'+pill(a.enabled?'Implemented · local':'Planned · Phase '+a.phase,a.enabled?'green':'amber')+'<div class="detail-section"><h3>Responsibility</h3><p>'+esc(a.detail)+'</p></div><div class="detail-section"><h3>Integration targets</h3><div class="tool-list">'+a.tools.map(t=>'<span class="tag">'+esc(t)+'</span>').join('')+'</div></div><div class="callout">Enterprise adapters currently use fixture data. '+(a.enabled?'Runs, evidence, and reports are persisted by the backend.':'This role is not executable in Phase 1.')+'</div>'+(a.enabled?btn(icon('play')+'Start a workflow','launch','primary','data-id="'+(a.id==='core'?'release':a.id)+'"'):'')+'</div>',true);}
function runPage(kind){const all=scopedRuns().filter(r=>r.kind===kind),filtered=all.filter(r=>state.releaseFilter==='all'||(state.releaseFilter==='attention'?['failed','awaiting_review'].includes(r.status):!!r.result));return head(kind==='release'?'Every release, accounted for.':'From signal to understanding.',kind==='release'?'Persisted verification runs, exact revisions, and reviewable evidence.':'Observed facts, hypotheses, and open questions stay separate.',btn(icon('play')+(kind==='release'?'Verify a release':'Investigate an incident'),'launch','primary','data-id="'+kind+'"'))+'<div class="toolbar"><div class="segmented">'+[['all','All runs'],['attention','Needs attention'],['prepared','Drafts prepared']].map(x=>'<button data-run-filter="'+x[0]+'" class="'+(state.releaseFilter===x[0]?'active':'')+'">'+x[1]+'</button>').join('')+'</div><span class="small muted">'+all.length+' runs · '+state.env+'</span></div>'+(filtered.length?'<div class="panel list-panel"><div class="data-row header"><span>Run / scope</span><span>Environment</span><span>Status</span><span>Created</span><span></span></div>'+filtered.map(r=>'<button class="data-row" data-action="run-detail" data-id="'+r.id+'"><div class="row-primary"><div class="release-icon">'+icon(kind==='release'?'rocket':'pulse')+'</div><div><strong>'+labels[kind]+'</strong><p>'+short(r.id)+' · '+esc(r.request.scenario)+' fixture</p></div></div><span class="row-value">'+esc(r.request.environment)+'</span><span>'+pill(r.result?.assessment||r.status,color(r.result?.assessment||r.status))+'</span><span class="row-value mono small">'+date(r.created_at)+'</span>'+icon('arrowup')+'</button>').join('')+'</div>':empty('No runs in this view','Start a workflow to collect evidence from the local adapters.'))+footer();}
function sites(){return head('A living view of your sites.','108 fixture sites. Health comes from persisted release evidence for '+state.env+'.')+'<div class="toolbar"><div class="segmented">'+[['all','All sites'],['attention','Needs attention'],['unchecked','Not verified']].map(x=>'<button data-site-filter="'+x[0]+'" class="'+(state.siteFilter===x[0]?'active':'')+'">'+x[1]+'</button>').join('')+'</div><input class="field" id="site-search" type="search" value="'+esc(state.siteSearch)+'" placeholder="Search brand, market, or region…" aria-label="Search sites"></div><div class="site-grid" id="site-grid">'+siteCards()+'</div>'+footer();}
function siteCards(){const list=siteStatus().filter(s=>(s.name+' '+s.market+' '+s.region).toLowerCase().includes(state.siteSearch.toLowerCase())&&(state.siteFilter==='all'||(state.siteFilter==='attention'?s.status==='fail':!['healthy','fail'].includes(s.status))));return list.map(s=>'<button class="panel site-card" data-action="site" data-id="'+s.id+'"><div class="site-symbol">'+icon('globe')+'</div><h3>'+esc(s.name+' / '+s.market)+'</h3><p>'+esc(s.region)+'</p><div class="site-line '+s.status+'"></div><p style="margin-top:8px">'+(s.checks===null?'Not verified':s.checks+' / 28 fixture checks')+'</p></button>').join('')||'<div class="empty">No sites match this filter.</div>';}
function siteDetail(id){const s=siteStatus().find(s=>s.id===Number(id));if(!s)return;openModal(modalHeader('SITE REGISTRY / '+s.id,s.name+' / '+s.market,s.region)+'<div class="drawer-hero"><div class="agent-art">'+icon('globe')+'</div></div><div class="modal-body">'+pill(s.status,color(s.status))+'<div class="detail-meta"><div><label>Theme</label><span>'+s.theme+'</span></div><div><label>Environment</label><span>'+state.env+'</span></div><div><label>Fixture checks</label><span>'+(s.checks===null?'Not checked':s.checks+' / 28')+'</span></div></div><div class="callout">'+(s.run_id?'Coverage: four representative fixture pages. No actual browser scan was performed.':'There is no verification evidence for this site in the selected environment.')+'</div>'+(s.run_id?btn('View source run','run-detail','','data-id="'+s.run_id+'"'):'')+'</div>',true);}
function approvals(){const list=scopedApprovals();const a=list.find(x=>x.id===state.approvalId)||list[0];if(!a)return head('Your judgment. Amplified.','Each review is bound to an exact draft and revision.')+empty('Nothing waiting for review','A release workflow will prepare a dossier here. Phase 1 review records acceptance only.')+footer();state.approvalId=a.id;const run=state.runs.find(r=>r.id===a.run_id);return head('Your judgment. Amplified.','Review the evidence. Understand the impact. Record your decision.',pill(pending()+' PENDING REVIEWS','amber'))+'<div class="approval-layout"><div class="approval-list">'+list.map(x=>'<button class="approval-item '+(x.id===a.id?'selected':'')+'" data-approval="'+x.id+'">'+pill(x.status,color(x.status))+'<h3>'+esc(x.title)+'</h3><p>'+esc(x.payload.revision)+'</p><div class="meta"><span>'+x.payload.site_ids.length+' sites</span><span>'+date(x.created_at)+'</span></div></button>').join('')+'</div><section class="panel approval-detail">'+pill('DRAFT REVIEW','amber')+'<h2>'+esc(a.title)+'</h2><p class="subtitle">Accepting the dossier does not deploy a release or approve a Cloud Manager gate.</p><div class="detail-meta"><div><label>Scope</label><span>'+a.payload.site_ids.length+' sites</span></div><div><label>Revision</label><span>'+esc(a.payload.revision)+'</span></div><div><label>Assessment</label><span>'+esc(run?.result?.assessment||'unknown')+'</span></div></div><div class="tabs" role="tablist" aria-label="Approval evidence">'+[['summary','Summary'],['evidence','Evidence'],['proposal','Review scope']].map(t=>'<button role="tab" aria-selected="'+(state.approvalTab===t[0])+'" class="'+(state.approvalTab===t[0]?'active':'')+'" data-approval-tab="'+t[0]+'">'+t[1]+'</button>').join('')+'</div>'+(state.approvalTab==='summary'?'<p class="subtitle summary-text">'+esc(run?.result?.narrative.summary||'Draft unavailable')+'</p>':state.approvalTab==='evidence'?a.payload.evidence_ids.map(id=>'<div class="check-row">'+icon('file')+'<span>'+esc(id)+'</span></div>').join('')+btn('Inspect source evidence','run-detail','small-btn','data-id="'+a.run_id+'"'):'<pre class="diff">'+esc(JSON.stringify(a.payload,null,2))+'</pre>')+'<div class="callout">'+icon('lock')+' Review expires '+date(a.expires_at)+'. The server verifies the draft hash and current result.</div>'+(a.status==='pending'?'<div class="approval-buttons">'+btn(icon('check')+'Accept draft','approve','primary','data-id="'+a.id+'"')+btn('Decline','decline','danger','data-id="'+a.id+'"')+'</div>':'<div class="callout">'+esc(a.status)+' by '+esc(a.actor||'system')+(a.reason?'. Reason: '+esc(a.reason):'')+'</div>')+'</section></div>'+footer();}
function reports(){const ids=new Set(scopedRuns().map(r=>r.id)),list=state.reports.filter(r=>ids.has(r.run_id));return head('The platform, made clear.','Evidence-linked drafts generated from your persisted runs.',btn(icon('play')+'Generate platform brief','launch','primary','data-id="reporting"'))+(list.length?'<div class="report-grid">'+list.map(r=>'<article class="panel report-card"><div class="report-cover">'+icon('file')+'</div><span class="upper muted">'+date(r.created_at)+'</span><h3>'+esc(r.title)+'</h3><p>'+short(r.run_id)+' · draft</p>'+btn('Read report '+icon('arrow'),'report','small-btn','data-id="'+r.id+'"')+'</article>').join('')+'</div>':empty('Your first report starts with a run','Release and incident runs generate their own reports. The Reporting agent can also summarize persisted work.'))+footer();}
const integrationsList=[['Cloud Manager','CM','Pipeline executions and revision history.','Fixture adapter implemented'],['New Relic','NR','Bounded telemetry windows.','Fixture adapter implemented'],['Splunk','S','Redacted log-pattern summaries.','Fixture adapter implemented'],['Verification','PW','Shared result contract for scoped site checks.','Fixture results; no browser runner yet'],['GitHub','GH','Code diffs and future review PRs.','Planned'],['Snyk + Sonar','SQ','Security findings and quality evidence.','Phase 2'],['AEM','A','Site inventory and inheritance metadata.','Fixture registry only'],['Microsoft Teams','T','Requests and review notifications.','Planned'],['MkDocs','MD','Documentation proposals.','Draft exports available']];
function integrations(){return head('Connected by design.','Integration boundaries are explicit. Live enterprise connections come next.',pill('FIXTURE ADAPTERS','amber'))+'<div class="integration-grid">'+integrationsList.map((a,i)=>'<article class="panel integration-card"><span class="integration-logo">'+a[1]+'</span><h3>'+a[0]+'</h3><p>'+a[2]+'</p><footer>'+pill(a[3])+'<button class="text-btn" data-action="integration" data-id="'+i+'">Scope '+icon('arrowup')+'</button></footer></article>').join('')+'</div><div class="integration-note">'+icon('lock')+' Model provider: '+esc(state.provider)+'. Enterprise credentials never enter this browser.</div>'+footer();}
function launch(kind='release'){if(!['release','incident','reporting'].includes(kind))kind='release';commandKey=requestKey();openModal(modalHeader('NEW AGENT RUN','Put the platform to work.','Persistent backend execution · synthetic enterprise inputs')+'<div class="modal-body"><div class="field-row"><label for="run-kind">Workflow</label><select id="run-kind">'+Object.entries(labels).map(([id,label])=>'<option value="'+id+'" '+(id===kind?'selected':'')+'>'+label+'</option>').join('')+'</select></div><div class="field-row"><label for="run-scenario">Fixture scenario</label><select id="run-scenario"><option value="healthy">Healthy release / baseline telemetry</option><option value="degraded">Failed checks / elevated errors</option><option value="incomplete">Missing verification evidence</option></select></div><div class="field-row"><label for="run-scope">Release impact scope</label><select id="run-scope"><option value="theme-04">Theme 04 consumers</option><option value="shared">Shared platform · all sites</option><option value="unknown">Unknown dependencies · expand to all sites</option></select></div><div class="callout">Environment: '+state.env+'. '+(state.provider==='bedrock'?'Summaries use the configured Bedrock model; enterprise inputs remain fixtures.':'Fixture mode makes no model or enterprise API calls.')+'</div>'+btn(icon('play')+'Start run','submit-run','primary')+'<div id="run-error" class="error-inline" role="alert"></div></div>');}
async function runDetail(id){const data=await api('/api/runs/'+id),r=data.run;openModal(modalHeader(short(r.id),labels[r.kind],r.request.environment+' · '+r.status)+'<div class="modal-body">'+pill(r.result?.assessment||r.status,color(r.result?.assessment||r.status))+'<div class="detail-section"><h3>Current stage</h3><p>'+esc(r.stage)+'</p>'+(r.error?'<p class="error-inline">'+esc(r.error)+'</p>':'')+'</div>'+(r.result?'<div class="detail-section"><h3>Draft summary</h3><p class="summary-text">'+esc(r.result.narrative.summary)+'</p></div>':'')+'<div class="detail-section"><h3>Run timeline</h3>'+data.events.map(e=>'<div class="check-row">'+icon('checkcircle')+'<span>'+esc(e.title)+'<br><small class="muted">'+esc(e.detail)+'</small></span><span class="mono">'+new Date(e.created_at).toLocaleTimeString()+'</span></div>').join('')+'</div><div class="detail-section"><h3>Evidence ledger</h3>'+data.evidence.map(e=>'<details class="evidence-item"><summary>'+esc(e.tool)+' · '+esc(e.source)+'</summary><p class="small muted">'+esc(e.id)+'</p><pre>'+esc(JSON.stringify(e.data,null,2))+'</pre><p class="small muted summary-text">SHA-256 '+e.digest+'</p></details>').join('')+'</div><div class="approval-buttons">'+btn('Refresh run','run-detail','small-btn','data-id="'+id+'"')+(['queued','running'].includes(r.status)?btn('Cancel run','cancel','danger','data-id="'+id+'"'):'')+(r.status==='failed'?btn('Retry run','retry','','data-id="'+id+'"'):'')+(r.status==='awaiting_review'?btn('Review dossier','review-run','primary','data-id="'+id+'"'):'')+'</div><p class="modal-note">Attempt '+r.attempts+' · data persisted by the local backend. No external write capabilities are enabled.</p></div>',true);}
async function showReport(id){const response=await fetch('/api/reports/'+id);if(!response.ok)throw Error('Report could not be loaded');const content=await response.text();openModal(modalHeader('PERSISTED REPORT','Evidence-linked draft','Download or inspect the exact generated content.')+'<div class="modal-body"><pre class="diff">'+esc(content)+'</pre><a class="btn download-link" href="/api/reports/'+id+'?download=true">'+icon('download')+'Download Markdown</a></div>');}
function decline(id){openModal(modalHeader('REVIEW DECISION','Decline this draft?','Your reason will be retained with the review record.')+'<div class="modal-body"><label for="decline-reason" class="small muted">Reason (optional)</label><textarea class="field" id="decline-reason" maxlength="1000" rows="4" style="width:100%;margin-top:10px"></textarea><div class="approval-buttons">'+btn('Record decline','confirm-decline','danger','data-id="'+id+'"')+btn('Keep reviewing','close')+'</div></div>');}
function settings(){openModal(modalHeader('WORKSPACE PREFERENCES','Make it your space.','Appearance is local to this browser; work is stored on the backend.')+'<div class="modal-body"><div class="setting-row"><div><h3>Accent color</h3><p>Choose the platform signal color.</p></div><div class="swatches">'+[['lime','#c0f681'],['cyan','#8cdde8'],['violet','#bea9ff']].map(x=>'<button class="swatch '+(state.accent===x[0]?'active':'')+'" data-accent="'+x[0]+'" style="--swatch:'+x[1]+'" aria-label="'+x[0]+' accent"></button>').join('')+'</div></div><div class="setting-row"><div><h3>Decorative motion</h3><p>Orbital graphics and transitions.</p></div>'+btn(state.motion?'On':'Off','settings-motion','small-btn')+'</div><div class="callout">Run and approval history is retained across browser refreshes. There is no destructive reset button.</div></div>');}
function environment(){openModal(modalHeader('WORKSPACE SCOPE','Choose an environment.','Filters the workspace and scopes new fixture runs.')+'<div class="modal-body">'+['dev','stage','production'].map(e=>'<button class="scenario-card" data-environment="'+e+'"><span class="agent-art">'+icon('server')+'</span><span><h3>'+e+'</h3><p>Fixture data only · no enterprise connection</p></span>'+icon('arrow')+'</button>').join('')+'</div>');}
function searchResults(q){return NAV.map(n=>({name:n[1],icon:n[2],nav:n[0]})).concat(AGENTS.map(a=>({name:a.name,icon:a.icon,id:a.id}))).filter(x=>x.name.toLowerCase().includes(q.toLowerCase())).map(x=>'<button class="command-result" '+(x.nav?'data-nav="'+x.nav+'"':'data-action="agent" data-id="'+x.id+'"')+'>'+icon(x.icon)+'<span>'+esc(x.name)+'</span></button>').join('')||'<div class="empty">No matches found.</div>';}
function openSearch(){openModal('<input id="command-input" class="command-input" type="search" placeholder="Find an agent or workspace…" aria-label="Search commands"><div class="command-results" id="command-results">'+searchResults('')+'</div><div class="command-hint">TAB TO NAVIGATE · ENTER TO OPEN · ESC TO CLOSE</div>');document.getElementById('command-input').focus();}
async function api(path,body,headers={}){const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-AAAEM-CSRF':state.csrf,...headers},body:body===undefined?undefined:JSON.stringify(body)});if(!response.ok){const error=await response.json().catch(()=>({detail:'Request failed'}));throw Error(typeof error.detail==='string'?error.detail:'Check the request fields');}return response.json();}
async function sync(bootstrap=false){const data=await api(bootstrap?'/api/bootstrap':'/api/workspace');state.csrf=data.csrf||state.csrf;if(bootstrap){state.csrf=data.csrf;state.provider=data.provider;AGENTS=data.agents;SITES=data.sites;}state.connected=true;document.getElementById('connection-badge').textContent='LOCAL · FIXTURE DATA';document.getElementById('connection-badge').classList.remove('connection-error');const signature=JSON.stringify([data.runs,data.approvals,data.events,data.reports]);Object.assign(state,{runs:data.runs,approvals:data.approvals,events:data.events,reports:data.reports});if(signature!==snapshotHash||bootstrap){snapshotHash=signature;if(document.activeElement?.id!=='site-search')render();}}
async function poll(){try{await sync(!state.csrf);}catch(error){state.connected=false;state.csrf=null;document.getElementById('connection-badge').textContent='BACKEND DISCONNECTED';document.getElementById('connection-badge').classList.add('connection-error');if(!AGENTS.length)main.innerHTML='<div class="load-state"><h2>Backend unavailable</h2><p>Start the local server, then retry.</p>'+btn('Reconnect','reconnect','primary')+'</div>';}finally{pollTimer=setTimeout(poll,active()?1200:3500);}}
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{
 if(b.dataset.nav){navigate(b.dataset.nav);return;}
 if(b.dataset.siteFilter){state.siteFilter=b.dataset.siteFilter;render();return;}
 if(b.dataset.runFilter){state.releaseFilter=b.dataset.runFilter;render();return;}
 if(b.dataset.approval){state.approvalId=b.dataset.approval;state.approvalTab='summary';render();return;}
 if(b.dataset.approvalTab){state.approvalTab=b.dataset.approvalTab;render();return;}
 if(b.dataset.environment){state.env=b.dataset.environment;closeModal();render();return;}
 if(b.dataset.accent){const values={lime:['#c0f681','192,246,129'],cyan:['#8cdde8','140,221,232'],violet:['#bea9ff','190,169,255']};state.accent=b.dataset.accent;document.documentElement.style.setProperty('--accent',values[state.accent][0]);document.documentElement.style.setProperty('--accent-rgb',values[state.accent][1]);settings();if(state.page==='overview')startNetwork();return;}
 const id=b.dataset.id,action=b.dataset.action;
 if(['submit-run','approve','confirm-decline','retry','cancel'].includes(action)){if(!state.connected)throw Error('Reconnect before changing workspace records');b.disabled=true;}
 switch(action){
  case 'menu':document.getElementById('sidebar').classList.toggle('open');break;
  case 'search':openSearch();break;
  case 'close':closeModal();break;
  case 'agent':agentDetail(id);break;
  case 'site':siteDetail(id);break;
  case 'launch':launch(id);break;
  case 'submit-run':{const body={kind:document.getElementById('run-kind').value,environment:state.env,scenario:document.getElementById('run-scenario').value,scope:document.getElementById('run-scope').value};await api('/api/runs',body,{'Idempotency-Key':commandKey});closeModal();await sync();navigate('overview');toast('Run queued','The backend will collect evidence and prepare a draft.');break;}
  case 'run-detail':await runDetail(id);break;
  case 'review-run':state.approvalId=state.approvals.find(a=>a.run_id===id)?.id;navigate('approvals');break;
  case 'report':await showReport(id);break;
  case 'cancel':case 'retry':await api('/api/runs/'+id+'/'+action,{});await sync();await runDetail(id);break;
  case 'approve':case 'confirm-decline':{const proposal=state.approvals.find(a=>a.id===id);const reason=action==='confirm-decline'?document.getElementById('decline-reason').value:'';await api('/api/approvals/'+id+'/decision',{digest:proposal.digest,decision:action==='approve'?'approved':'declined',reason});closeModal();await sync();toast('Review recorded','No deployment or publication was triggered.');break;}
  case 'decline':decline(id);break;
  case 'settings':settings();break;
  case 'motion':setMotion(!state.motion);break;
  case 'settings-motion':setMotion(!state.motion);settings();break;
  case 'environment':environment();break;
  case 'reconnect':await sync(true);break;
  case 'integration':{const a=integrationsList[Number(id)];openModal(modalHeader('INTEGRATION SCOPE',a[0],a[2])+'<div class="modal-body">'+pill(a[3],'amber')+'<div class="callout">The backend enforces agent and environment scope. This build does not configure credentials or connect to this enterprise service.</div></div>');break;}
  case 'about':openModal(modalHeader('AAAEM PLATFORM','Your operational workspace.','Standalone application · Phase 1')+'<div class="modal-body"><p class="subtitle">Three bounded agent workflows, a durable local queue, evidence, draft review, and reports. AWS deployment and enterprise SSO remain the next stage.</p><div class="callout">Data integrations: fixtures. Model provider: '+esc(state.provider)+'. Authentication: local operator only. Run this build locally.</div></div>');break;
 }
 }catch(error){const inline=document.getElementById('run-error');if(inline)inline.textContent=error.message;toast('Action could not finish',error.message);}finally{if(b.isConnected)b.disabled=false;}
});
document.addEventListener('input',e=>{if(e.target.id==='site-search'){state.siteSearch=e.target.value;document.getElementById('site-grid').innerHTML=siteCards();}if(e.target.id==='command-input')document.getElementById('command-results').innerHTML=searchResults(e.target.value);});
document.addEventListener('change',e=>{if(e.target.id?.startsWith('run-'))commandKey=requestKey();});
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openSearch();}if(e.key==='Escape')document.getElementById('sidebar').classList.remove('open');});
document.addEventListener('pointerover',e=>{const n=e.target.closest('.agent-node');if(n)hoveredAgent=n.dataset.id;});
document.addEventListener('pointerout',e=>{if(e.target.closest('.agent-node'))hoveredAgent=null;});
document.addEventListener('click',e=>{if(!e.target.closest('.sidebar')&&!e.target.closest('.mobile-menu'))document.getElementById('sidebar').classList.remove('open');});
modal.addEventListener('close',()=>{if(lastFocus?.isConnected)lastFocus.focus();});
window.addEventListener('resize',()=>{if(state.page==='overview')startNetwork();});
window.addEventListener('hashchange',()=>{const page=location.hash.slice(2);if(page!==state.page)navigate(page);});
matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',e=>setMotion(!e.matches));
document.getElementById('pulse-bars').innerHTML=Array.from({length:28},(_,k)=>'<i style="height:'+(10+(k*17)%20)+'px;animation-delay:'+(k%7*.17)+'s"></i>').join('');
setMotion(state.motion);hydrateIcons();poll();

function startNetwork(){
 cancelAnimationFrame(frame);
 const canvas=document.getElementById('network-canvas');
 if(!canvas)return;
 const ctx=canvas.getContext('2d');
 if(!ctx)return;
 const rect=canvas.getBoundingClientRect();
 const w=rect.width,h=rect.height,dpr=Math.min(devicePixelRatio||1,2);
 canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
 let last=0;
 const pos=[[.19,.22],[.81,.22],[.16,.5],[.84,.5],[.19,.78],[.81,.78]];
 const begin=performance.now();
 function cubic(p0,p1,p2,p3,t){const u=1-t;return u*u*u*p0+3*u*u*t*p1+3*u*t*t*p2+t*t*t*p3;}
 function draw(now){
  if(!document.getElementById('network-canvas')||canvas!==document.getElementById('network-canvas'))return;
  if(state.motion)frame=requestAnimationFrame(draw);
  if(state.motion&&now-last<32)return;last=now;
  const t=state.motion?(now-begin)/1000:2;
  const colors={lime:[192,246,129],cyan:[140,221,232],violet:[190,169,255]};
  const c=colors[state.accent]||colors.lime;
  const rgb=c.join(',');
  const cx=w*.5,cy=h*.49,r=Math.min(77,w*.112);
  ctx.clearRect(0,0,w,h);
  const glow=ctx.createRadialGradient(cx,cy,5,cx,cy,w*.42);
  glow.addColorStop(0,'rgba('+rgb+',.055)');glow.addColorStop(.6,'rgba('+rgb+',.014)');glow.addColorStop(1,'rgba('+rgb+',0)');
  ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
  ctx.strokeStyle='#293b302d';ctx.lineWidth=.5;
  for(let x=14;x<w;x+=24){ctx.beginPath();ctx.moveTo(x,25);ctx.lineTo(x,h-18);ctx.stroke();}
  for(let y=25;y<h-17;y+=24){ctx.beginPath();ctx.moveTo(14,y);ctx.lineTo(w-14,y);ctx.stroke();}
  for(let k=0;k<50;k++){const sx=(k*137.5+19)%w,sy=(k*97.1+20)%h;ctx.fillStyle='rgba('+rgb+','+(.09+.06*Math.sin(k+t*.5))+')';ctx.fillRect(sx,sy,1,1);}
  ctx.save();ctx.translate(cx,cy);ctx.scale(1,.43);ctx.rotate(.05);ctx.strokeStyle='rgba('+rgb+',.08)';ctx.lineWidth=1;
  for(let k=0;k<3;k++){ctx.beginPath();ctx.ellipse(0,0,r*(1.55+k*.42),r*(1.55+k*.42),0,0,Math.PI*2);ctx.stroke();}
  ctx.restore();
  pos.forEach((p,j)=>{
   const tx=w*p[0],ty=h*p[1],sign=tx>cx?1:-1;
   const x0=cx+sign*r*.78,y0=cy+(ty-cy)*.2,x3=tx-sign*(w<601?47:w<850?55:64),y3=ty;
   const x1=x0+sign*35,y1=y0,x2=x3-sign*36,y2=y3;
   const active=state.activeAgent===AGENTS[j+1].id||hoveredAgent===AGENTS[j+1].id;
   ctx.beginPath();ctx.moveTo(x0,y0);ctx.bezierCurveTo(x1,y1,x2,y2,x3,y3);
   ctx.strokeStyle='rgba('+rgb+','+(active?.53:.14)+')';ctx.lineWidth=active?1.3:.8;ctx.stroke();
   ctx.beginPath();ctx.moveTo(x0,y0+4);ctx.bezierCurveTo(x1,y1+4,x2,y2+4,x3,y3+4);ctx.strokeStyle='rgba('+rgb+',.04)';ctx.lineWidth=.5;ctx.stroke();
   for(let n=0;n<2;n++){const pct=(t*(active?.22:.09)+j*.19+n*.5)%1;
    const px=cubic(x0,x1,x2,x3,pct),py=cubic(y0,y1,y2,y3,pct);
    const halo=ctx.createRadialGradient(px,py,0,px,py,active?8:5);halo.addColorStop(0,'rgba('+rgb+','+(active?.65:.35)+')');halo.addColorStop(1,'rgba('+rgb+',0)');ctx.fillStyle=halo;ctx.fillRect(px-8,py-8,16,16);
    ctx.beginPath();ctx.arc(px,py,active?1.6:1,0,Math.PI*2);ctx.fillStyle='rgba('+rgb+',.9)';ctx.fill();
   }
  });
  const sphere=ctx.createRadialGradient(cx-r*.4,cy-r*.45,0,cx,cy,r*1.2);sphere.addColorStop(0,'#344737');sphere.addColorStop(.4,'#1a2c24');sphere.addColorStop(.85,'#0c1715');sphere.addColorStop(1,'#0d1514');
  ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fillStyle=sphere;ctx.fill();
  function project(lat,lon){
   const x=r*Math.cos(lat)*Math.cos(lon),y=r*Math.sin(lat),z=r*Math.cos(lat)*Math.sin(lon),rot=t*.18;
   const xr=x*Math.cos(rot)+z*Math.sin(rot),zr=-x*Math.sin(rot)+z*Math.cos(rot);
   const yr=y*Math.cos(-.38)-zr*Math.sin(-.38),zz=y*Math.sin(-.38)+zr*Math.cos(-.38);
   const perspective=300/(300-zz*.25);
   return [cx+xr*perspective,cy+yr*perspective,zz];
  }
  for(let latN=-8;latN<=8;latN++){
   const lat=latN/9*Math.PI/2;let prev=null;
   for(let k=0;k<=75;k++){const pt=project(lat,k/75*Math.PI*2);
    if(prev){ctx.beginPath();ctx.moveTo(prev[0],prev[1]);ctx.lineTo(pt[0],pt[1]);ctx.strokeStyle='rgba('+rgb+','+(.06+Math.max(0,pt[2]/r)*.45)+')';ctx.lineWidth=.65;ctx.stroke();}
    if(k%4===0&&pt[2]>0){ctx.beginPath();ctx.arc(pt[0],pt[1],.65+(pt[2]/r)*.35,0,Math.PI*2);ctx.fillStyle='rgba('+rgb+','+(.25+pt[2]/r*.48)+')';ctx.fill();}
    prev=pt;
   }
  }
  for(let lon=0;lon<24;lon++){let prev=null;for(let la=-20;la<=20;la++){const pt=project(la/20*Math.PI/2,lon/24*Math.PI*2);if(prev&&pt[2]>-r*.2){ctx.beginPath();ctx.moveTo(prev[0],prev[1]);ctx.lineTo(pt[0],pt[1]);ctx.strokeStyle='rgba('+rgb+','+(.06+Math.max(0,pt[2]/r)*.15)+')';ctx.lineWidth=.5;ctx.stroke();}prev=pt;}}
  for(let k=0;k<3;k++){ctx.save();ctx.translate(cx,cy);ctx.rotate(.35+k*1.03+t*.025*(k%2===0?1:-1));ctx.beginPath();ctx.ellipse(0,0,r*1.2,r*.34,0,0,Math.PI*2);ctx.strokeStyle='rgba('+rgb+','+(k===0?.4:.18)+')';ctx.lineWidth=.8;ctx.stroke();const a=t*.22+k*2;ctx.beginPath();ctx.arc(r*1.2*Math.cos(a),r*.34*Math.sin(a),1.6,0,Math.PI*2);ctx.fillStyle='rgb('+rgb+')';ctx.fill();ctx.restore();}
  const sheen=ctx.createRadialGradient(cx-r*.35,cy-r*.5,0,cx-r*.35,cy-r*.5,r*.8);sheen.addColorStop(0,'rgba('+rgb+',.12)');sheen.addColorStop(1,'rgba('+rgb+',0)');ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fillStyle=sheen;ctx.fill();
  ctx.font='7px Consolas,monospace';ctx.fillStyle='rgba('+rgb+',.5)';ctx.textAlign='center';ctx.fillText('AAAEM // CORE',cx,cy-r-28);
 }
 frame=requestAnimationFrame(draw);
}
