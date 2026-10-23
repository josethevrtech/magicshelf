'use strict';
const token = location.hash.slice(1) || sessionStorage.getItem('magicshelf-token');
if (location.hash) { sessionStorage.setItem('magicshelf-token', token); history.replaceState(null, '', location.pathname); }
const $ = id => document.getElementById(id);
let snapshot = null, view = 'discover', selected = null, tab = 'about', category = 'All', query = '', gallery = 0, working = false, actionError = '';
function el(tag, text, cls) { const n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; }
function button(text, cls, fn) { const b = el('button', text, cls); b.type = 'button'; b.onclick = fn; b.disabled = working || Boolean(snapshot?.busy); return b; }
function link(text, url, cls = 'project-link') { const a = el('a', text, cls); try { if (new URL(url).protocol !== 'https:') return el('span', text); } catch { return el('span', text); } a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; }
function transferLabel(t) { return ({downloading:'Downloading',checking:'Checking download',installing:'Installing',ready:'Ready when Off',complete:'Installed · Ready',setting_up:'Setting up',setup_failed:'Setup needs retry',failed:'Download needs retry'})[t.stage] || ''; }
function progress(t) { const box=el('div',null,'download-progress');box.append(el('strong',transferLabel(t)));const bar=el('progress');bar.max=t.total_bytes;bar.value=t.received_bytes;bar.setAttribute('aria-label','Download progress for '+t.name);box.append(bar);if((t.stage==='downloading'||t.stage==='setting_up')&&t.total_bytes>0)box.append(el('small',(t.received_bytes/1048576).toFixed(1)+' / '+(t.total_bytes/1048576).toFixed(1)+' MB · '+Math.floor(t.received_bytes/t.total_bytes*100)+'%'));return box; }
function power(item) { if(item.setup&&!item.setup.ready)return button(['queued','running'].includes(item.setup.stage)?'View setup':'Set up','primary',()=>{selected=item.id;tab='settings';render();});const b=button('','power-toggle',()=>act('module.toggle',{id:item.id,enabled:!item.enabled}));b.append(el('span',item.enabled?'On':'Off'),el('span',null,'power-track'));b.setAttribute('role','switch');b.setAttribute('aria-checked',String(item.enabled));b.setAttribute('aria-label','Turn '+item.name+' on or off');b.lastChild.setAttribute('aria-hidden','true');return b; }
async function api(method, params = {}) { const r = await fetch('/api', { method: 'POST', headers: {'Content-Type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({api_version:1,method,params}) }); if (!r.ok) throw Error('Open MagicShelf from its desktop shortcut to reconnect.'); const data = await r.json(); if (data.error) throw Error(data.error); return data.result; }
async function act(method, params = {}) { if (working) return; working = true; actionError = ''; render(); $('notice').textContent = method === 'module.subscribe' ? 'Downloading your creation…' : 'Updating your shelf…'; try { snapshot = await api(method, params); } catch (e) { actionError = e.message; } finally { working = false; render(); } }
function choose(next) { view = next; selected = null; category = 'All'; query = ''; render(); window.scrollTo(0,0); if(next==='discover')api('catalog.discover').catch(()=>{}); }
function openCreation(id) { selected = id; const item=snapshot.modules.find(m=>m.id===id); tab = item?.installed&&item.setup&&!item.setup.ready?'settings':'about'; gallery = 0; render(); window.scrollTo(0,0); if(next==='discover')api('catalog.discover').catch(()=>{}); }
function review(item, method = 'module.subscribe') {
  const target = item.update || item;
  $('review-title').textContent = (item.installed && item.update ? 'Update ' : 'Subscribe to ') + item.name;
  $('review-description').textContent = item.installed && item.update ? 'Install this update now. If the creation is On, it will restart. Your saved data is kept. Cancel to let the update install while Off.' : 'MagicShelf will download and install it for you. Then use On / Off on its collection card.';
  $('review-permissions').replaceChildren(el('h3','What this creation can do'));for(const permission of target.permission_details||[]){const row=el('div',null,'permission');row.append(el('strong',permission.title),el('p',permission.description));$('review-permissions').append(row);}
  $('review-note').textContent = 'Creations run with access to your SteamOS account. If an update asks for more access, MagicShelf will ask you again. Future updates download automatically and install while the creation is Off.';
  $('confirm').textContent = item.installed && item.update ? 'Install update' : item.installed ? 'Subscribe for updates' : 'Subscribe & install';
  $('review').returnValue = ''; $('review').showModal();
  $('review').onclose = () => { if ($('review').returnValue === 'confirm') act(method, {id:item.id,subscribed:true,permissions:target.permissions}); };
}
function artwork(item, cls, index = 0) { const box = el('div', null, 'art ' + cls + (item.category === 'Companions' ? ' companions' : '')); const photo = item.screenshots?.[index]; if (photo) { const img = el('img'); img.src = photo.url; img.alt = photo.caption || item.name; img.loading = 'lazy'; img.onerror = () => { img.remove(); box.append(el('span','✦','fallback-art')); }; box.append(img); } else box.append(el('span','✦','fallback-art')); return box; }
function collection() {
  const area = el('section'); const intro = el('div', null, 'intro'); intro.append(el('h1', view === 'discover' ? 'Explore the Collection' : 'My Shelf')); area.append(intro);
  const toolbar = el('div',null,'toolbar'), filters = el('div',null,'filters');
  const categories = ['All', ...new Set(snapshot.modules.map(m => m.category || 'Creations'))];
  categories.forEach(c => { const b = button(c,'filter',() => {category=c; render();}); b.setAttribute('aria-pressed',String(category===c)); filters.append(b); });
  const search = el('input',null,'search'); search.type='search'; search.placeholder='Search creations'; search.setAttribute('aria-label','Search creations'); search.value=query; search.oninput=()=>{query=search.value; renderCards();}; toolbar.append(filters,search); area.append(toolbar);
  const heading = el('div',null,'section-heading'); const count=el('span'); count.id='result-count'; heading.append(count); area.append(heading);
  const cards=el('div',null,'cards'); cards.id='creation-cards'; area.append(cards);
  return area;
}
function renderCards() {
  const cards=$('creation-cards'); if(!cards)return;
  const items=snapshot.modules.filter(m=>(view==='discover'||m.installed||m.subscribed)&&(category==='All'||m.category===category)&&[m.name,m.description,m.category].join(' ').toLowerCase().includes(query.toLowerCase()));
  $('result-count').textContent=items.length+' creation'+(items.length===1?'':'s'); cards.replaceChildren();
  for(const item of items){
    const card=el('article',null,'creation-card'),open=button('','card-open',()=>openCreation(item.id)),info=el('div',null,'card-info');open.setAttribute('aria-label','View '+item.name);
    info.append(el('div',item.category,'card-category'),el('h3',item.name),el('p',item.description));open.append(artwork(item,'card-art'),info);card.append(open);
    const foot=el('div',null,'card-foot'),t=snapshot.transfer;
    if(t?.active&&t.id===item.id)foot.append(progress(t));
    else if(item.installed)foot.append(el('span',({ready:'Update ready',review:'Review update',failed:'Update needs retry',held:'Previous version kept',available:'Update available'})[item.update_status]||(item.setup&&!item.setup.ready?(['queued','running'].includes(item.setup.stage)?'Setting up':'Setup needed'):'Installed')),power(item));
    else foot.append(button('View creation ↗','secondary',()=>openCreation(item.id)));
    card.append(foot);cards.append(card);
  }
  if(!items.length){const empty=el('div',null,'empty');empty.append(el('h2',query?'No matching creations':'Your shelf starts here'),el('p',query?'Try a different search or category.':'Explore Discover and subscribe to a creation you like.'));cards.append(empty);}
}
function settings(item) {
  const panel=el('div');
  if(!item.installed){panel.append(el('p','Subscribe and download this creation to configure it.','about'));return panel;}
  const power=el('div',null,'setting-row'), copy=el('div');copy.append(el('h3','On your shelf'),el('p',item.enabled?'Running and ready to use.':'Off. Your saved data is kept.'));const toggle=button('','switch',()=>act('module.toggle',{id:item.id,enabled:!item.enabled}));toggle.setAttribute('role','switch');toggle.setAttribute('aria-checked',String(item.enabled));toggle.setAttribute('aria-label','Turn '+item.name+' on or off');power.append(copy,toggle);panel.append(power);
  if(item.can_configure||item.adapter){const row=el('div',null,'setting-row'), text=el('div');text.append(el('h3','Device controls'),el('p','Brightness, size, placement and hand attachment.'));row.append(text,button('Open settings ↗','secondary',()=>act('module.open',{id:item.id})));panel.append(row,el('p','Opening device settings turns this creation on. Its controls appear on the creation in VR.','explanation'));}
  const updates=el('div',null,'setting-row'), text=el('div');text.append(el('h3','Updates'),el('p',item.update_mode==='local'?'Local build · published packages are not available yet.':item.subscribed?'Updates download automatically and install while Off.':'Subscribe to keep this creation up to date.'));updates.append(text);if(item.subscribed)updates.append(button('Unsubscribe','secondary',()=>act('module.subscribe',{id:item.id,subscribed:false})));else if(item.subscription_available)updates.append(button('Subscribe for updates','secondary',()=>review(item)));panel.append(updates);
  if(item.update)panel.append(button(item.update_status==='ready'?'Update now':'Review update','secondary',()=>review(item,item.subscribed?'module.subscribe':'module.install')));
  if(item.previous_version)panel.append(button('Restore previous version','secondary',()=>{if(confirm('Restore the previous version and its saved data? Your current data will be archived.'))act('module.rollback',{id:item.id});}));
  if(!item.adapter)panel.append(button('Remove download','danger',()=>{if(confirm('Remove '+item.name+' and stop its subscription? Your saved data will be kept.'))act('module.remove',{id:item.id});}));return panel;
}
function setupFocused(item){return item?.installed&&item.setup&&!item.setup.ready&&tab==='settings';}
function setupPage(item){
  const section=el('section',null,'creation-setup');section.append(button('← Back','back',()=>{selected=null;render();}));
  const grid=el('div',null,'detail'),right=el('div',null,'detail-info setup-info');grid.append(artwork(item,'gallery-main'),right);right.append(el('h1',item.name));
  const steps=item.setup.steps,index=steps.findIndex(s=>!s.ready),next=steps[index];
  if(next){
    if(steps.length>1)right.append(el('p','Step '+(index+1)+' of '+steps.length,'setup-step'));
    const active=['queued','running'].includes(item.setup.stage),failed=item.setup.stage==='failed',downloading=next.total_bytes>0;
    const content=el('div',null,'setup-content');content.append(el('h2',failed?'Setup paused':active?'Setting up':'Finish setup'));
    if(failed)content.append(el('p',item.setup.error,'setup-copy'));
    else if(downloading){const bar=el('progress');bar.max=next.total_bytes;bar.value=next.received_bytes;bar.setAttribute('aria-label','Setup download progress');content.append(bar,el('p',next.received_bytes>=next.total_bytes?'Finishing up…':Math.floor(Math.min(1,next.received_bytes/next.total_bytes)*100)+'%','setup-copy'));}
    else content.append(el('p',active?'Getting everything ready.':'MagicShelf will handle the downloads.','setup-copy'));
    if(!active)content.append(button(failed?'Retry':'Set up','primary',()=>act('module.setup',{id:item.id})));
    if(failed)content.append(button('Open Steam','secondary',()=>act('module.setup.open',{id:item.id,appid:next.appid})));
    right.append(content);
  }
  section.append(grid);return section;
}
function credits(item){const panel=el('div');panel.append(el('p','Made possible by these creators. Artist support is optional and opens their own page.','about'));for(const credit of item.credits||[]){const row=el('article',null,'credit');row.append(el('h3',credit.name),el('p',credit.role));if(credit.license)row.append(el('p',credit.license,'credit-license'));const links=el('div',null,'credit-links');if(credit.url)links.append(link('Artist / creator ↗',credit.url,''));if(credit.support_url)links.append(link('Support creator ↗',credit.support_url,''));row.append(links);panel.append(row);}if(!item.credits?.length)panel.append(el('p','By '+(item.author||'the creation’s author')+'. '+(item.license||''),'about'));return panel;}
function detail(item){if(setupFocused(item))return setupPage(item);const section=el('section');section.append(button('← Back to '+(view==='library'?'My Shelf':'Discover'),'back',()=>{selected=null;render();}));const grid=el('div',null,'detail'),left=el('div'),right=el('div',null,'detail-info');gallery=Math.min(gallery,Math.max(0,(item.screenshots?.length||1)-1));left.append(artwork(item,'gallery-main',gallery));const thumbs=el('div',null,'gallery-controls');(item.screenshots||[]).forEach((s,i)=>{const b=button('','thumbnail',()=>{gallery=i;render();});b.setAttribute('aria-label','Screenshot '+(i+1));b.setAttribute('aria-pressed',String(gallery===i));const img=el('img');img.src=s.url;img.alt='';b.append(img);thumbs.append(b);});left.append(thumbs,el('p',item.screenshots?.[gallery]?.caption||'Screenshot coming soon.','caption'));
  right.append(el('span',item.category,'eyebrow'),el('h1',item.name),el('p','by '+(item.author||'josethevrtech'),'byline'),el('p',item.tagline||item.description,'tagline'));
  const state=el('div',null,'detail-status');state.append(el('span',item.adapter?'Installed locally':item.subscribed?'Installed · automatic updates':item.installed?'Installed':'Ready to download'));right.append(state);
  const actions=el('div',null,'detail-actions'),t=snapshot.transfer;
  if(t?.active&&t.id===item.id)actions.append(progress(t));
  else if(item.installed)actions.append(power(item),button('Configure creation','secondary',()=>{tab='settings';render();}));
  else if(item.subscription_available)actions.append(button('Subscribe & download','primary',()=>review(item)));
  right.append(actions);
  right.append(el('p',item.adapter?'This creation is already installed on your device. Its downloadable release is still being prepared.':item.update_note?item.update_note:'Subscribe to download this creation and receive future updates.','explanation'));
  const tabs=el('div',null,'detail-tabs');tabs.setAttribute('role','tablist');['about','settings','credits'].forEach(t=>{const b=button(t[0].toUpperCase()+t.slice(1),'',()=>{tab=t;render();});b.setAttribute('role','tab');b.setAttribute('aria-selected',String(tab===t));tabs.append(b);});right.append(tabs);const content=el('div',null,'tab-content');content.setAttribute('role','tabpanel');if(tab==='settings')content.append(settings(item));else if(tab==='credits')content.append(credits(item));else{content.append(el('p',item.about||item.description,'about'));const links=el('div',null,'links');(item.links||[]).forEach(l=>links.append(link(l.label+' ↗',l.url)));content.append(links);}right.append(content);grid.append(left,right);section.append(grid);return section;}
function preferences(){
  const section=el('section',null,'store-settings'),intro=el('div',null,'intro');intro.append(el('h1','Settings'));section.append(intro);
  const prefs=snapshot.preferences;if(!prefs)return section;
  for(const [group,title] of [['shelf','Shelf'],['placement','Placement'],['app','App']]){
    const panel=el('section',null,'settings-panel');panel.append(el('h2',title));
    for(const control of prefs.controls.filter(c=>c.group===group)){
      const row=el('div',null,'setting-row'),copy=el('div'),actions=el('div',null,'setting-actions'),value=prefs.values[control.key];
      copy.append(el('h3',control.label),el('p',control.description));row.append(copy);
      const save=v=>act('settings.update',{changes:{[control.key]:v}});
      if(control.choices){for(const choice of control.choices){const b=button(choice.label,value===choice.value?'primary':'secondary',()=>save(choice.value));b.setAttribute('aria-pressed',String(value===choice.value));actions.append(b);}}
      else{
        const display=control.unit==='m'?value.toFixed(1)+' m':control.unit==='degrees'?Math.round(value)+' deg':Math.round(value*100)+(control.unit==='%'?'%':' cm');
        for(const delta of [-1,1]){
          if(delta===1)actions.append(el('output',display));
          const next=Math.max(control.min,Math.min(control.max,Math.round((value+delta*control.step)*1e6)/1e6));
          const b=button(delta<0?'−':'+','secondary',()=>save(next));b.setAttribute('aria-label',(delta<0?'Decrease ':'Increase ')+control.label);b.disabled=working||next===value;actions.append(b);
        }
      }
      row.append(actions);panel.append(row);
    }
    panel.append(button('Restore defaults','secondary',()=>act('settings.reset',{group})));section.append(panel);
  }
  const update=snapshot.framework_update;if(update){const panel=el('section',null,'settings-panel');panel.append(el('h2','MagicShelf '+snapshot.version),el('p',update.message));if(update.stage==='ready')panel.append(button('Update and reopen','primary',()=>act('framework.install')));else if(update.stage==='downloading')panel.append(progress({...update,name:'MagicShelf'}));else if(update.stage==='failed')panel.append(button('Try again','secondary',()=>act('catalog.refresh')));section.append(panel);}
  const credits=el('section',null,'settings-panel');credits.append(el('h2','Credits'),el('p','MagicShelf '+snapshot.version+' · SteamOS and Steam Frame'));
  for(const credit of prefs.credits){const row=el('div',null,'credit');row.append(el('h3',credit.name),el('p',credit.role),link('Open project ↗',credit.url));credits.append(row);}
  credits.append(el('p',"Creation artists and contributors are credited on each creation's page."));section.append(credits);
  return section;
}
function render(){if(!snapshot)return;const item=snapshot.modules.find(m=>m.id===selected);if(selected&&!item)selected=null;$('discover').setAttribute('aria-pressed',String(view==='discover'));$('library').setAttribute('aria-pressed',String(view==='library'));$('preferences').setAttribute('aria-pressed',String(view==='settings'));$('shelf-count').textContent=snapshot.modules.filter(m=>m.installed).length;$('version').textContent='MagicShelf '+snapshot.version;document.body.classList.toggle('setup-active',Boolean(setupFocused(item)));$('breadcrumb').textContent=item&&!setupFocused(item)?'Collection / '+item.name:'';$('content').replaceChildren(item?detail(item):view==='settings'?preferences():collection());renderCards();$('notice').textContent=actionError||snapshot.message;$('notice').className=actionError?'error':'';$('update-status').textContent=snapshot.update_message||'';$('downloads').replaceChildren();if(snapshot.transfer&&snapshot.transfer.stage!=='complete'){$('downloads').append(el('small','DOWNLOADS'),el('p',snapshot.transfer.name),progress(snapshot.transfer));}$('refresh').disabled=working;}
$('brand').onclick=e=>{e.preventDefault();choose('discover');};$('discover').onclick=()=>choose('discover');$('library').onclick=()=>choose('library');$('preferences').onclick=()=>choose('settings');$('refresh').onclick=()=>act('catalog.refresh');
api('snapshot').then(data=>{snapshot=data;view=data.preferences?.values?.start_view||'discover';render();api('catalog.discover').catch(()=>{});}).catch(e=>{$('notice').textContent=e.message;$('notice').className='error';});
let lastPoll=0;
setInterval(async()=>{if($('review').open||document.activeElement?.tagName==='INPUT'||(!working&&!snapshot?.transfer?.active&&Date.now()-lastPoll<5000))return;lastPoll=Date.now();try{const next=await api('snapshot');if(JSON.stringify(next)!==JSON.stringify(snapshot)){snapshot=next;render();}}catch{}},500);
