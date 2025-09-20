# Dr Sof - Login + Chatbot (n8n)

Pequena aplicação Node/Express com duas telas:
- Login inspirado no layout fornecido
- Chat que envia a mensagem do médico para seu Webhook do n8n e exibe a resposta

## Como rodar

No Windows PowerShell:

```
cd c:\\Users\\coman\\Desktop\\xdxd
npm install
npm start
```

Abra no navegador:
- http://localhost:3000

Faça login com qualquer email/senha (sem autenticação real neste demo). Em seguida informe a URL do Webhook do n8n quando solicitado.

## Integração com n8n
Ao enviar uma mensagem no chat, o frontend chama `POST /api/sendMessage` e o servidor encaminha um JSON ao seu Webhook do n8n.

O payload enviado segue o formato do exemplo (simplificado) – o texto da mensagem vai em `body.data.message.conversation` e `messageType` é `conversation`:

```
[
  {
    "headers": {
      "host": "<host do seu webhook>",
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
          "remoteJid": "<medicoId>@s.whatsapp.net",
          "fromMe": true,
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
        "messageTimestamp": 1758400542,
        "instanceId": "web-instance",
        "source": "web"
      },
      "destination": "<URL DO SEU WEBHOOK>",
      "date_time": "2025-09-20T17:35:42.550Z",
      "sender": "<medicoId>@s.whatsapp.net",
      "server_url": "https://dr-sof.local",
      "apikey": "dr-sof-demo-key"
    },
    "webhookUrl": "<URL DO SEU WEBHOOK>",
    "executionMode": "production"
  }
]
```

Observações:
- Campos da Evolution API podem ser ignorados no n8n; o que importa é você processar o texto em `body.data.message.conversation`.
- Configure seu workflow para retornar um JSON simples (por exemplo `{ "answer": "texto de resposta" }`). O frontend exibirá `answer`. Se vier um outro JSON, ele será mostrado como texto (stringificado).

## Onde editar
- `public/index.html` – telas de Login e Chat.
- `public/main.js` – lógica de navegação e envio de mensagem.
- `server.js` – servidor Express e integração com o n8n.

## Próximos passos (sugestões)
- Implementar autenticação real (JWT/Session).
- Salvar o Webhook do n8n em `.env` ou em configurações do usuário.
- Persistir histórico no backend.
- Tratar anexos/áudio se necessário (atualizar `message` conforme seu caso).
