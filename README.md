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

Faça login com qualquer email/senha (sem autenticação real neste demo). Em seguida informe a URL do Webhook do n8n quando solicitado.

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

## Onde editar

## Próximos passos (sugestões)
