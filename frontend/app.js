const api = '/api';
let token = localStorage.getItem('token');
let refreshTimer;
const headers = () => ({'Content-Type':'application/json','Authorization':`Bearer ${token}`});

function errorMessage(detail, fallback='Something went wrong') {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => `${item.loc?.at(-1) || 'field'}: ${item.msg || 'Invalid value'}`).join(' | ');
  if (typeof detail === 'object') return detail.msg || JSON.stringify(detail);
  return fallback;
}

function toast(message) {
  const el = document.getElementById('toast');
  el.textContent = message; el.hidden = false;
  clearTimeout(el._timer); el._timer = setTimeout(() => el.hidden = true, 3500);
}

async function login(register) {
  const body = {email:document.getElementById('email').value,password:document.getElementById('password').value};
  const r = await fetch(`${api}/auth/${register?'register':'login'}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d = await r.json();
  if (!r.ok) return document.getElementById('auth-msg').textContent = errorMessage(d.detail, 'Unable to sign in');
  token = d.access_token; localStorage.setItem('token',token); showApp();
}

function logout() {
  localStorage.removeItem('token'); token = null; clearInterval(refreshTimer);
  document.getElementById('app').hidden = true; document.getElementById('auth').hidden = false; document.getElementById('logout').hidden = true;
}

async function provision(templateId) {
  toast(`Requesting your ${templateId} workspace…`);
  const r = await fetch(`${api}/environments`, {method:'POST',headers:{...headers(),'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({template_id:templateId})});
  const d = await r.json();
  if (!r.ok) return toast(errorMessage(d.detail, 'Unable to provision workspace'));
  toast('Workspace requested. The platform is preparing it now.');
  loadEnvironments();
}

async function action(id, name) {
  if (name === 'delete' && !confirm('Delete this workspace and all of its data? This cannot be undone.')) return;
  const method = name==='delete'?'DELETE':'POST';
  const r = await fetch(`${api}/environments/${id}${name==='delete'?'':`/${name}`}`, {method,headers:headers()});
  const d = await r.json();
  if (!r.ok) return toast(errorMessage(d.detail, 'Action failed'));
  toast(name==='delete'?'Deleting workspace…':`${name==='stop'?'Stopping':'Starting'} workspace…`);
  setTimeout(loadEnvironments,500);
}

async function showLogs(id) {
  const r = await fetch(`${api}/environments/${id}/logs`, {headers:headers()});
  const d = await r.json();
  const el = document.getElementById(`details-${id}`); el.hidden=false;
  el.textContent = r.ok ? JSON.stringify(d.logs,null,2) : errorMessage(d.detail, 'Unable to load logs');
}

async function showCredentials(id) {
  const r = await fetch(`${api}/environments/${id}/credentials`, {headers:headers()});
  const d = await r.json();
  const el = document.getElementById(`details-${id}`); el.hidden=false;
  el.textContent = r.ok ? JSON.stringify(d.values,null,2) : errorMessage(d.detail, 'Unable to load credentials');
}

function progressFor(status) {
  const labels = {requested:'Request accepted',provisioning:'Preparing services and workspace',running:'Workspace ready',failed:'Provisioning failed',stopping:'Stopping workspace',stopped:'Workspace stopped',deleting:'Deleting workspace'};
  return labels[status] || status;
}

function componentName(name) {
  return {workspace:'Browser IDE',jupyter:'JupyterLab',postgres:'PostgreSQL',redis:'Redis',minio:'Object Storage',spark:'Spark'}[name] || name;
}

async function loadEnvironments() {
  const r = await fetch(`${api}/environments`, {headers:headers()});
  if (r.status===401) return logout();
  const envs = await r.json();
  const container = document.getElementById('environments'); container.innerHTML='';
  if (!envs.length) { container.innerHTML='<div class="empty">No workspaces yet. Provision one above and the platform will build it for you.</div>'; return; }

  for (const e of envs) {
    const statusResponse = await fetch(`${api}/environments/${e.id}/status`, {headers:headers()});
    const detail = await statusResponse.json();
    const div = document.createElement('article'); div.className='card environment';
    const comps = (detail.components||[]).map(c=>`<span class="component ${c.healthy?'healthy':'waiting'}"><b>${c.healthy?'✓':'○'}</b> ${componentName(c.name)}</span>`).join('');
    const running = e.status === 'running';
    const stopped = e.status === 'stopped';
    const isData = e.template_id === 'data';
    const short = e.id.split('-')[0];
    const storageUrl = `http://storage-data-${short}.localhost:8081`;
    div.innerHTML=`
      <div class="environment-head"><div><span class="eyebrow">${e.template_id==='backend'?'BACKEND':'DATA'} WORKSPACE</span><h3>${e.name}</h3></div><span class="status status-${e.status}">${e.status}</span></div>
      <div class="progress"><span></span><p>${progressFor(e.status)}</p></div>
      <div class="components">${comps}</div>
      ${e.error_message?`<div class="error-box">${e.error_message}</div>`:''}
      <div class="workspace-actions">
        ${running && e.url?`<a class="button" href="${e.url}" target="_blank">Open Workspace</a>`:''}
        ${running && detail.app_url?`<a class="button secondary" href="${detail.app_url}" target="_blank">Open Application</a>`:''}
        ${running && isData?`<a class="button secondary" href="${storageUrl}" target="_blank">Open Object Storage</a>`:''}
        ${running?`<button class="ghost" onclick="showCredentials('${e.id}')">Access details</button>`:''}
        <button class="ghost" onclick="showLogs('${e.id}')">Logs</button>
        ${(running||stopped)?`<button class="ghost" onclick="action('${e.id}','${stopped?'start':'stop'}')">${stopped?'Start':'Stop'}</button>`:''}
        <button class="danger" onclick="action('${e.id}','delete')">Delete</button>
      </div>
      <p class="meta">Created ${new Date(e.created_at).toLocaleString()} · Expires ${e.expires_at?new Date(e.expires_at).toLocaleString():'not set'}</p>
      <pre id="details-${e.id}" hidden></pre>`;
    container.appendChild(div);
  }
}

function showApp(){
  document.getElementById('auth').hidden=true; document.getElementById('app').hidden=false; document.getElementById('logout').hidden=false;
  loadEnvironments(); clearInterval(refreshTimer); refreshTimer=setInterval(loadEnvironments,4000);
}
if(token) showApp();
