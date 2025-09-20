import express from 'express';
import cors from 'cors';
import fetch from 'node-fetch';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;
const DEFAULT_WEBHOOK_URL = process.env.N8N_WEBHOOK_URL || '';

app.use(cors());
app.use(express.json({ limit: '2mb' }));
app.use(express.urlencoded({ extended: true }));

// Static frontend
app.use(express.static(path.join(__dirname, 'public')));

// Health check
app.get('/health', (_req, res) => res.json({ ok: true }));

// Frontend config endpoint (exposes if webhook is set)
app.get('/api/config', (_req, res) => {
  res.json({ webhookUrl: DEFAULT_WEBHOOK_URL, configured: Boolean(DEFAULT_WEBHOOK_URL) });
});

// API: forward chat message to n8n webhook
app.post('/api/sendMessage', async (req, res) => {
  try {
    const { message, webhookUrl: bodyUrl, medicoNome, medicoId } = req.body || {};
    const webhookUrl = bodyUrl || DEFAULT_WEBHOOK_URL;

    if (!message) return res.status(400).json({ error: 'message is required' });
    if (!webhookUrl) return res.status(400).json({ error: 'webhookUrl is not configured' });

    const now = new Date();
    const mock = buildWebhookPayload({
      text: message,
      medicoNome: medicoNome || 'Médico',
      medicoId: medicoId || 'doctor-uid-001',
      webhookUrl
    });

    // Send to n8n
    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(mock)
    });

    // Try to parse JSON, fallback to text
    let data;
    const text = await response.text();
    try { data = JSON.parse(text); } catch { data = { text }; }
    // Normalize common shapes to {output: string}
    let normalized;
    if (Array.isArray(data)) {
      const first = data[0] || {};
      if (typeof first === 'object' && (first.output || first.answer)) {
        normalized = { output: first.output || first.answer };
      } else {
        normalized = { raw: data };
      }
    } else if (data && typeof data === 'object') {
      normalized = data.output ? { output: data.output } : (data.answer ? { output: data.answer } : data);
    } else {
      normalized = { text: String(data) };
    }

    // Derive a single message string for the frontend
    let messageText = '';
    if (typeof normalized === 'object') {
      messageText = normalized.output || normalized.answer || normalized.text || '';
    }
    if (!messageText) {
      try { messageText = JSON.stringify(normalized); } catch { messageText = String(normalized); }
    }

    return res.json({ ok: true, responseStatus: response.status, message: messageText, data: normalized });
  } catch (err) {
    console.error('sendMessage error', err);
    return res.status(500).json({ ok: false, error: String(err?.message || err) });
  }
});

// Fallback: serve index.html
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => console.log(`Dr Sof server running on http://localhost:${PORT}`));

// Helper to build the webhook JSON with the provided format
function buildWebhookPayload({ text, medicoNome, medicoId, webhookUrl }) {
  // We will embed the text message as if it were a WhatsApp text message. Fields from Evolution API can be ignored by n8n; include essential ones only.
  const id = Math.random().toString(16).slice(2).toUpperCase();
  const dateIso = new Date().toISOString();
  return {
    headers: {
      host: new URL(webhookUrl).host,
      'user-agent': 'dr-sof-web/1.0',
      'content-type': 'application/json'
    },
    params: {},
    query: {},
    body: {
      event: 'messages.upsert',
      instance: 'dr-sof-web',
      data: {
        key: {
          remoteJid: 'site',
          fromMe: false,
          id,
          senderLid: `${medicoId}@lid`
        },
        pushName: medicoNome,
        status: 'DELIVERY_ACK',
        message: {
          conversation: text,
          messageContextInfo: {}
        },
        contextInfo: null,
        messageType: 'conversation',
        messageTimestamp: Math.floor(Date.now() / 1000),
        instanceId: 'web-instance',
        source: 'web'
      },
      destination: webhookUrl,
      date_time: dateIso,
      sender: `${medicoId}@s.whatsapp.net`,
      server_url: 'https://dr-sof.local',
      apikey: 'dr-sof-demo-key'
    },
    webhookUrl,
    executionMode: 'production'
  };
}
