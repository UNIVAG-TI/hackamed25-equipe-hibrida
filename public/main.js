const loginView = document.getElementById('login-view');
const chatView = document.getElementById('chat-view');
const form = document.getElementById('login-form');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const messages = document.getElementById('messages');

let session = { medicoNome: '', medicoId: '', webhookUrl: '' };

// Load config from backend
fetch('/api/config').then(r=>r.json()).then(cfg=>{
  if (cfg?.webhookUrl) session.webhookUrl = cfg.webhookUrl;
}).catch(()=>{});

function show(view) {
  for (const el of document.querySelectorAll('.view')) el.classList.remove('active');
  view.classList.add('active');
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  // Simples validação: email/senha ok, pedir webhook URL
  const email = document.getElementById('email').value.trim();
  const nameGuess = email.split('@')[0] || 'Médico';
  session = {
    medicoNome: nameGuess,
    medicoId: nameGuess.replace(/[^a-z0-9]/gi, '') || 'doctor',
    webhookUrl: session.webhookUrl
  };

  if (!session.webhookUrl) {
    alert('Webhook do n8n não está configurado no servidor (.env).');
    return;
  }

  show(chatView);
  addMsg('Olá! Sou o assistente virtual do Dr Sof. Estou aqui para te ajudar com uma avaliação inicial dos seus sintomas. Como você está se sentindo hoje?', 'bot');
});

sendBtn.addEventListener('click', sendMessage);
input?.addEventListener('keydown', (e)=>{ if (e.key === 'Enter') { e.preventDefault(); sendMessage(); } });

async function sendMessage(){
  const text = input.value.trim();
  if(!text) return;
  input.value = '';
  addMsg(text, 'user');
  try {
    const res = await fetch('/api/sendMessage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, webhookUrl: session.webhookUrl, medicoNome: session.medicoNome, medicoId: session.medicoId })
    });
    const json = await res.json();
  const reply = json.message || extractReadable(json);
  const formatted = formatReply(reply);
    addMsg(formatted || 'Sem resposta do n8n.', 'bot');
  } catch (err) {
    console.error(err);
    addMsg('Erro ao contatar o n8n: ' + err.message, 'bot');
  }
}

function addMsg(text, who){
  const li = document.createElement('li');
  li.className = 'msg ' + (who === 'user' ? 'user' : 'bot');
  li.textContent = text;
  messages.appendChild(li);
  messages.scrollTop = messages.scrollHeight;
}

function extractReadable(payload){
  // Tentar achar uma mensagem textual em várias estruturas possíveis vindas do n8n
  if (!payload) return '';
  // Caso comum: n8n retorna { output: '...' } ou { answer: '...' }
  if (payload.data && payload.data.output) return payload.data.output;
  if (payload.output) return payload.output;
  if (payload.data && payload.data.answer) return payload.data.answer;
  if (payload.answer) return payload.answer;
  if (Array.isArray(payload) && payload[0]) {
    const first = payload[0];
    if (first.output) return first.output;
    if (first.answer) return first.answer;
  }
  if (typeof payload === 'string') return payload;
  // Fallback: stringificar suavemente
  try { return JSON.stringify(payload.data || payload); } catch { return '' }
}

function formatReply(text){
  if (!text) return '';
  const trimmed = String(text).trim();
  const alreadyWrapped = trimmed.startsWith('(') && trimmed.endsWith(')');
  return alreadyWrapped ? trimmed : `(${trimmed})`;
}
