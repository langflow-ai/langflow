# 🚀 Guia Rápido de Teste - Webhook Real-Time SSE

## ⚡ Setup Rápido (5 minutos)

### 1. Start Backend
```bash
cd /Users/cris.zanforlin/Documents/langflow
make run
# ou
python -m langflow run
```

### 2. Start Frontend
```bash
cd src/frontend
npm run dev
```

### 3. Abra Browser
```
http://localhost:3000
```

---

## 🧪 Teste Básico

### Passo 1: Crie um Flow

1. No Langflow, clique em "New Flow"
2. Adicione componente **Webhook** ao canvas
3. (Opcional) Conecte outros componentes
4. Salve o flow

### Passo 2: Pegue o Flow ID

Na URL do browser:
```
http://localhost:3000/flow/YOUR_FLOW_ID_HERE
                            ^^^^^^^^^^^^^^^^^^^
```

Copie o `YOUR_FLOW_ID_HERE`

### Passo 3: Abra Console do Browser

Pressione **F12** e vá para aba "Console"

Você deve ver:
```
[useWebhookEvents] Connecting to SSE: ...
[useWebhookEvents] Connected to flow: {flow_id: "..."}
```

### Passo 4: Envie Webhook

Em **outro terminal**:

```bash
# Substitua YOUR_FLOW_ID pelo ID copiado!
curl -X POST "http://localhost:7860/api/v1/webhook/YOUR_FLOW_ID" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test from terminal!", "test": true}'
```

### Passo 5: Observe a Mágica ✨

**No Browser Console**:
```
[useWebhookEvents] end
Build completed
```

**No Backend Logs**:
```
UI listeners detected for flow ...
SSE connection established for flow ...
```

**Na UI**:
- Componentes devem atualizar
- `isBuilding` fica true durante execução
- Estados mudam em tempo real

---

## 🎯 Teste Completo (Eventos Granulares)

### Com Autenticação

Se `WEBHOOK_AUTH_ENABLE=true`:

```bash
# 1. Gere API key na UI (Settings → API Keys)

# 2. Use na requisição
curl -X POST "http://localhost:7860/api/v1/webhook/YOUR_FLOW_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-lf-YOUR_API_KEY_HERE" \
  -d '{"message": "Authenticated request!"}'
```

### Teste Performance (Sem UI)

```bash
# 1. Feche TODAS as abas do Langflow no browser

# 2. Envie webhook
curl -X POST "http://localhost:7860/api/v1/webhook/YOUR_FLOW_ID" \
  -H "Content-Type: application/json" \
  -d '{"message": "No UI open"}'

# 3. Verifique logs - NÃO deve ter "UI listeners detected"
# Webhook deve executar normalmente sem overhead!
```

### Teste Múltiplas UIs

```bash
# 1. Abra flow em 2 abas diferentes do browser

# 2. Envie webhook

# 3. Observe: AMBAS as abas recebem eventos!
```

---

## 🐛 Debug

### Verificar SSE Connection

No browser console:
```javascript
// Deve mostrar conexão ativa
console.log(window.performance.getEntries().filter(e => e.name.includes('webhook-events')))
```

### Verificar Backend

```bash
# Health check
curl http://localhost:7860/api/v1/health

# Test SSE endpoint diretamente
curl -N http://localhost:7860/api/v1/webhook-events/YOUR_FLOW_ID

# Deve retornar:
# event: connected
# data: {"flow_id":"...","flow_name":"..."}
#
# event: heartbeat
# data: {"timestamp":...}
```

### Logs Detalhados

Backend:
```bash
# Busque por:
grep "useWebhookEvents" langflow.log
grep "SSE connection" langflow.log
grep "UI listeners" langflow.log
```

Frontend:
```javascript
// No console do browser:
localStorage.setItem('debug', 'langflow:*')
// Recarregue página
```

---

## 📊 Exemplos de Payloads

### Simples
```bash
curl -X POST "http://localhost:7860/api/v1/webhook/YOUR_FLOW_ID" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

### Complexo
```bash
curl -X POST "http://localhost:7860/api/v1/webhook/YOUR_FLOW_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "user_message",
    "user": {
      "id": 123,
      "name": "John Doe"
    },
    "data": {
      "message": "Hello from external system",
      "timestamp": "2024-01-15T10:30:00Z",
      "metadata": {
        "source": "mobile_app",
        "version": "1.0.0"
      }
    }
  }'
```

### Com Arrays
```bash
curl -X POST "http://localhost:7860/api/v1/webhook/YOUR_FLOW_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"id": 1, "value": "item1"},
      {"id": 2, "value": "item2"},
      {"id": 3, "value": "item3"}
    ],
    "process_all": true
  }'
```

---

## ✅ Checklist de Sucesso

- [ ] Backend rodando (`make run`)
- [ ] Frontend rodando (`npm run dev`)
- [ ] Flow criado com componente Webhook
- [ ] Console do browser mostra "Connected to flow"
- [ ] Webhook enviado via curl
- [ ] Backend logs mostram "UI listeners detected"
- [ ] Browser console mostra "Build completed"
- [ ] UI atualiza em tempo real
- [ ] Teste sem UI (sem overhead)

---

## 🎉 Funcionou?

Se todos os checkmarks acima estão ✅, parabéns!

**Você agora tem webhook com feedback visual em tempo real!**

---

## ⏭️ Próximos Passos

1. **Teste com flow real** (ChatInput → OpenAI → ChatOutput)
2. **Adicione mais componentes** e veja todos atualizando
3. **Integre com sistema externo** (Zapier, n8n, etc.)
4. **Implemente eventos granulares** (build_start, end_vertex)

---

## 💬 Suporte

Problemas? Veja:
- `WEBHOOK_SSE_IMPLEMENTATION.md` - Documentação completa
- `webhook-realtime-proposal.md` - Proposta e arquitetura
- Logs do backend e frontend
- Console do browser (F12)

---

**Happy Webhooking! 🎣**
