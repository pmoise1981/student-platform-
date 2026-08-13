const api = '/api';
let token = localStorage.getItem('token');
const headers = () => ({'Content-Type':'application/json','Authorization':`Bearer ${token}`});

async function login(register) {
  const body = {email:document.getElementById('email').value,password:document.getElementById('password').value};
  const r = await fetch(`${api}/auth/${register?'register':'login'}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d = await r.json();
  if (!r.ok) return document.getElementById('auth-msg').textContent = d.detail || 'Unable to sign in';
  token = d.access_token; localStorage.setItem('token',token); showApp();
}

async function provision(template_id) {
  const r = await fetch(`${api}/environments`, {method:'POST',headers:{...headers(),'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({template_id})});
  if (!r.ok) alert((await r.json()).detail); else loadEnvironments();
}

async function action(id, name) {
  const method = name==='delete'?'DELETE':'POST';
  const r = await fetch(`${api}/environments/${id}${name==='delete'?'':`/${name}`}`, {method,headers:headers()});
  if (!r.ok) alert((await r.json()).detail); else setTimeout(loadEnvironments,400);
}

async function showLogs(id) {
  const r = await fetch(`${api}/environments/${id}/logs`, {headers:headers()});
  const d = await r.json();
  const el = document.getElementById(`logs-${id}`); el.hidden=false; el.textContent = r.ok ? JSON.stringify(d.logs,null,2) : d.detail;
}

async function showCredentials(id) {
  const r = await fetch(`${api}/environments/${id}/credentials`, {headers:headers()});
  const d = await r.json();
  const el = document.getElementById(`logs-${id}`); el.hidden=false; el.textContent = r.ok ? JSON.stringify(d.values,null,2) : d.detail;
}

async function loadEnvironments() {
  const r = await fetch(`${api}/environments`, {headers:headers()});
  if (r.status===401) return;
  const envs = await r.json();
  const container = document.getElementById('environments'); container.innerHTML='';
  for (const e of envs) {
    const detail = await (await fetch(`${api}/environments/${e.id}`, {headers:headers()})).json();
    const div = document.createElement('article'); div.className='card environment';
    const comps = (detail.components||[]).map(c=>`<span class="${c.healthy?'healthy':'unhealthy'}">${c.name}: ${c.healthy?'Healthy':'Waiting'}</span>`).join('');
    div.innerHTML=`<h3>${e.name}</h3><div class="status">Status: ${e.status}</div><div class="components">${comps}</div>
      ${e.url?`<p>URL: <a href="${e.url}" target="_blank">${e.url}</a></p>`:''}
      <p class="meta">Created: ${new Date(e.created_at).toLocaleString()}<br>Expires: ${e.expires_at?new Date(e.expires_at).toLocaleString():'Not set'}</p>
      ${e.error_message?`<p class="unhealthy">${e.error_message}</p>`:''}
      <div class="actions"><button onclick="showLogs('${e.id}')">View Logs</button><button onclick="showCredentials('${e.id}')">Credentials</button><button class="secondary" onclick="action('${e.id}','${e.status==='stopped'?'start':'stop'}')">${e.status==='stopped'?'Start':'Stop'}</button><button class="secondary" onclick="action('${e.id}','delete')">Delete</button></div>
      <pre id="logs-${e.id}" hidden></pre>`;
    container.appendChild(div);
  }
}

function showApp(){ document.getElementById('auth').hidden=true; document.getElementById('app').hidden=false; loadEnvironments(); setInterval(loadEnvironments,5000); }
if(token) showApp();
