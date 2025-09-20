# Dr Sof - Login + Chatbot (n8n), Funciona com Whatsapp tambem.

Pequena aplicação Node/Express com duas telas:

## Como rodar

No Windows PowerShell:

```
cd c:\\Users\\coman\\Desktop\\xdxd
npm install
npm start
```

Abra no navegador:

Faça login com qualquer email/senha (sem autenticação real neste demo). O webhook do n8n é lido do arquivo `.env`; não é necessário colar a URL no login.

## Integração com n8n
Ao enviar uma mensagem no chat, o frontend chama `POST /api/sendMessage` e o servidor encaminha um JSON ao seu Webhook do n8n.

O payload enviado segue o formato do exemplo (simplificado) – o texto da mensagem vai em `body.data.message.conversation` e `messageType` é `conversation`:

```
 {
   "headers": {
     "host": "<host do webhook>",
     "user-agent": "dr-sof-web/1.0",
     "content-type": "application/json"
   },
   "params": {},
   "query": {},
   "body": {
     "event": "messages.upsert",
     "instance": "dr-sof-web",
     "data": {
       "key": {
         "remoteJid": "site",     // exigência do fluxo
         "fromMe": false,
         "id": "<random>",
         "senderLid": "<medicoId>@lid"
       },
       "pushName": "<medicoNome>",
       "status": "DELIVERY_ACK",
       "message": {
         "conversation": "<TEXTO DIGITADO PELO MÉDICO>",
         "messageContextInfo": {}
       },
       "contextInfo": null,
       "messageType": "conversation",
       "messageTimestamp": 1690000000,
       "instanceId": "web-instance",
       "source": "web"
     },
     "destination": "<URL DO WEBHOOK>",
     "date_time": "<ISO>",
     "sender": "<medicoId>@s.whatsapp.net",
     "server_url": "https://dr-sof.local",
     "apikey": "dr-sof-demo-key"
   },
   "webhookUrl": "<URL DO WEBHOOK>",
   "executionMode": "production"
 }
```

Observações:
- O texto digitado no chat vai em `body.data.message.conversation` e `messageType` é `conversation`.
- `remoteJid` foi fixado como `site` (exigência do seu fluxo no n8n).
- O n8n pode responder como objeto `{ output: "..." }`, `{ answer: "..." }`, array `[ { output } ]` ou texto. O backend normaliza e devolve ao frontend uma string em `message`.
- O frontend exibe o texto entre parênteses e preserva quebras de linha.

## Onde editar

- `.env`
  - `N8N_WEBHOOK_URL` → URL do webhook do n8n (fixo)
  - `PORT` → porta do servidor local

- `server.js`
  - Servidor Express, serve estáticos e implementa:
    - `GET /api/config` (expõe a URL do webhook ao frontend)
    - `POST /api/sendMessage` (monta o payload e envia ao n8n)
  - Função `buildWebhookPayload(...)` → onde está o `remoteJid: 'site'`, `message.conversation` etc.
  - Normalização da resposta do n8n → converte para `{ message: <texto> }` antes de retornar ao frontend.

- `public/index.html`
  - Layout das telas (Login e Chat) e estilos principais. O chat já preserva quebras de linha.

- `public/main.js`
  - Navegação Login → Chat, envio de mensagens e exibição das respostas.
  - Busca a configuração do webhook em `/api/config`.
  - Extrai o texto do retorno (`json.message` → `data.output/answer` → array) e formata entre parênteses.

- `public/styles.css`
  - Espaço para estilos adicionais (opcional; a base está no HTML).

- `package.json`
  - Scripts (`npm start`) e dependências.
a
