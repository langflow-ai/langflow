# Proposta: Webhook com Feedback Visual em Tempo Real

## 🎯 Objetivo

Criar uma experiência onde:
1. **Usuário manda webhook via terminal** (curl, Postman, etc.)
2. **Se tem UI aberta** → Vê build em tempo real (BUILDING, BUILT, ERROR, animações, duração)
3. **Se não tem UI aberta** → Webhook funciona normalmente (como hoje)
4. **Mesma experiência** que apertar o botão Play na UI

---

## 📊 Análise de Opções Técnicas

### Comparação Rápida

| Opção | Complexidade | Performance | Escalabilidade | Recomendação |
|-------|-------------|-------------|----------------|--------------|
| **SSE (Server-Sent Events)** | ⭐⭐ Baixa | ⭐⭐⭐⭐⭐ Excelente | ⭐⭐⭐⭐ Boa | ✅ **MELHOR** |
| **WebSocket** | ⭐⭐⭐ Média | ⭐⭐⭐⭐ Muito Boa | ⭐⭐⭐⭐ Boa | ⚠️ Alternativa |
| **Polling** | ⭐ Muito Baixa | ⭐⭐ Ruim | ⭐⭐⭐ Média | ❌ Não ideal |
| **Redis Pub/Sub + SSE** | ⭐⭐⭐⭐ Alta | ⭐⭐⭐⭐⭐ Excelente | ⭐⭐⭐⭐⭐ Excelente | ⭐ Futuro |

---

## ✅ Opção 1: Server-Sent Events (SSE) - RECOMENDADA

### Por Que SSE é a Melhor Opção?

**1. Já Existe no Langflow!**
```typescript
// O sistema de build JÁ USA SSE!
// buildUtils.ts:273-288
return performStreamingRequest({
  method: "POST",
  url: buildUrl,
  onData: async (event) => {
    const type = event["event"];
    const data = event["data"];
    return await onEvent(type, data, ...);
  },
});
```

**2. Perfeito para o Caso de Uso**
- ✅ **Unidirecional** (backend → frontend) - é exatamente o que precisamos!
- ✅ **Reconnect automático** - se conexão cair, reconecta sozinho
- ✅ **HTTP/1.1** - funciona em qualquer servidor
- ✅ **Menor overhead** que WebSocket
- ✅ **Mesma infraestrutura** do build atual

**3. Implementação Simples**
- Reutiliza **TODO o código existente** de eventos
- Mesma estrutura de eventos: `vertices_sorted`, `build_start`, `end_vertex`, etc.
- Mesmo handler `onEvent()` que já funciona

### Arquitetura Proposta (SSE)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLUXO COMPLETO                               │
└─────────────────────────────────────────────────────────────────────┘

TERMINAL                          BACKEND                     FRONTEND
   │                                 │                            │
   │                                 │ ◄──── GET /webhook-events/{flow_id}
   │                                 │       ?stream=true
   │                                 │                            │
   │                                 ├─── SSE connection opened ──►
   │                                 │    (mantém conexão aberta) │
   │                                 │                            │
   │ POST /webhook/{flow_id}         │                            │
   ├────────────────────────────────►│                            │
   │ {payload}                       │                            │
   │                                 │                            │
   │                           ┌─────▼─────┐                      │
   │                           │  Webhook  │                      │
   │                           │  Handler  │                      │
   │                           └─────┬─────┘                      │
   │                                 │                            │
   │                           ┌─────▼─────┐                      │
   │                           │Event Bus  │                      │
   │                           │(in-memory)│                      │
   │                           └─────┬─────┘                      │
   │                                 │                            │
   │ 202 ACCEPTED                    │                            │
   │◄────────────────────────────────┤                            │
   │ (response imediato)             │                            │
   │                                 │                            │
   │                           ┌─────▼─────┐                      │
   │                           │Build Flow │                      │
   │                           │(background)│                      │
   │                           └─────┬─────┘                      │
   │                                 │                            │
   │                           emit: vertices_sorted              │
   │                                 ├────────────────────────────►
   │                                 │    event: vertices_sorted   │
   │                                 │    data: {ids, to_run}     │
   │                                 │                            │
   │                                 │         Frontend marca      │
   │                                 │         componentes como    │
   │                                 │         TO_BUILD            │
   │                                 │                            │
   │                           emit: build_start                  │
   │                                 ├────────────────────────────►
   │                                 │    event: build_start       │
   │                                 │    data: {id}              │
   │                                 │                            │
   │                                 │         Ícone vira ⌛      │
   │                                 │         Borda roxa animada  │
   │                                 │         Edge verde animada  │
   │                                 │                            │
   │                           emit: end_vertex                   │
   │                                 ├────────────────────────────►
   │                                 │    event: end_vertex        │
   │                                 │    data: {build_data}      │
   │                                 │                            │
   │                                 │         Mostra duração ✅   │
   │                                 │         Borda verde         │
   │                                 │                            │
   │                           emit: end                          │
   │                                 ├────────────────────────────►
   │                                 │    event: end               │
   │                                 │                            │
   │                                 │         isBuilding = false  │
   │                                 │         Para animações      │
```

### Componentes da Solução

#### 1. Event Manager (Backend)

```python
# src/backend/base/langflow/services/event_manager.py

from typing import Any, AsyncIterator, Dict, Set
import asyncio
from collections import defaultdict
from fastapi import Request

class WebhookEventManager:
    """
    Gerencia conexões SSE e broadcasting de eventos de webhook.
    """

    def __init__(self):
        # flow_id → set of queues (uma por conexão SSE)
        self._listeners: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, flow_id: str) -> asyncio.Queue:
        """
        Subscreve para receber eventos de um flow específico.
        Retorna uma queue que receberá os eventos.
        """
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._listeners[flow_id].add(queue)
        return queue

    async def unsubscribe(self, flow_id: str, queue: asyncio.Queue):
        """
        Remove subscri��ão.
        """
        async with self._lock:
            if flow_id in self._listeners:
                self._listeners[flow_id].discard(queue)
                if not self._listeners[flow_id]:
                    del self._listeners[flow_id]

    async def emit(self, flow_id: str, event_type: str, data: Any):
        """
        Emite evento para todos os listeners deste flow.
        """
        async with self._lock:
            listeners = self._listeners.get(flow_id, set())

        if not listeners:
            # Ninguém ouvindo, não faz nada
            return

        # Serializa evento
        event = {
            "event": event_type,
            "data": data,
        }

        # Envia para todas as queues
        for queue in listeners:
            try:
                await asyncio.wait_for(
                    queue.put(event),
                    timeout=1.0  # Timeout para evitar bloqueio
                )
            except asyncio.TimeoutError:
                # Queue cheia, ignora (conexão lenta)
                pass
            except Exception:
                # Queue fechada, ignora
                pass

    def has_listeners(self, flow_id: str) -> bool:
        """
        Verifica se há algum listener ativo para este flow.
        """
        return flow_id in self._listeners and len(self._listeners[flow_id]) > 0


# Instância global
webhook_event_manager = WebhookEventManager()
```

#### 2. Endpoint SSE (Backend)

```python
# src/backend/base/langflow/api/v1/endpoints.py

from fastapi import Request
from fastapi.responses import StreamingResponse
from langflow.services.event_manager import webhook_event_manager
import json
import asyncio

@router.get("/webhook-events/{flow_id_or_name}")
async def webhook_events_stream(
    flow_id_or_name: str,
    flow: Annotated[Flow, Depends(get_flow_by_id_or_endpoint_name)],
    request: Request,
):
    """
    Endpoint SSE para receber eventos de webhook em tempo real.

    Uso:
    GET /api/v1/webhook-events/{flow_id_or_name}?stream=true

    Retorna:
    Stream de eventos SSE com progresso do build.
    """

    async def event_generator():
        # Subscreve para receber eventos
        queue = await webhook_event_manager.subscribe(flow.id)

        try:
            # Envia evento inicial de conexão
            yield f"event: connected\ndata: {json.dumps({'flow_id': flow.id})}\n\n"

            while True:
                # Verifica se cliente desconectou
                if await request.is_disconnected():
                    break

                try:
                    # Aguarda próximo evento (com timeout)
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=30.0  # Heartbeat a cada 30s
                    )

                    # Serializa e envia evento
                    event_data = json.dumps(event["data"])
                    yield f"event: {event['event']}\ndata: {event_data}\n\n"

                except asyncio.TimeoutError:
                    # Heartbeat - mantém conexão viva
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': time.time()})}\n\n"

        finally:
            # Remove subscri��ão quando conexão fechar
            await webhook_event_manager.unsubscribe(flow.id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx: desabilita buffering
        },
    )
```

#### 3. Modificar Webhook Handler

```python
# src/backend/base/langflow/api/v1/endpoints.py

@router.post("/webhook/{flow_id_or_name}", response_model=dict, status_code=HTTPStatus.ACCEPTED)
async def webhook_run_flow(
    flow_id_or_name: str,
    flow: Annotated[Flow, Depends(get_flow_by_id_or_endpoint_name)],
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Webhook endpoint com suporte a eventos em tempo real.
    """
    # ... código existente de autenticação e payload ...

    # Verifica se há listeners conectados
    has_ui_connected = webhook_event_manager.has_listeners(flow.id)

    run_id = str(uuid4())
    background_tasks.add_task(
        simple_run_flow_task_with_events,  # 👈 Nova função
        flow=flow,
        input_request=input_request,
        api_key_user=webhook_user,
        telemetry_service=telemetry_service,
        start_time=start_time,
        run_id=run_id,
        emit_events=has_ui_connected,  # 👈 Só emite se há listeners
        flow_id=flow.id,
    )

    return {"message": "Task started in the background", "status": "in progress"}
```

#### 4. Build com Eventos (Backend)

```python
# src/backend/base/langflow/graph/graph/base.py

async def simple_run_flow_task_with_events(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    api_key_user: User | None = None,
    event_manager: EventManager | None = None,
    telemetry_service=None,
    start_time: float | None = None,
    run_id: str | None = None,
    emit_events: bool = False,
    flow_id: str,
):
    """
    Executa flow com emissão de eventos para o Event Manager.
    """
    try:
        # Se deve emitir eventos, cria callbacks
        callbacks = None
        if emit_events:
            callbacks = {
                "on_vertices_sorted": lambda data: asyncio.create_task(
                    webhook_event_manager.emit(flow_id, "vertices_sorted", data)
                ),
                "on_build_start": lambda data: asyncio.create_task(
                    webhook_event_manager.emit(flow_id, "build_start", data)
                ),
                "on_build_end": lambda data: asyncio.create_task(
                    webhook_event_manager.emit(flow_id, "build_end", data)
                ),
                "on_end_vertex": lambda data: asyncio.create_task(
                    webhook_event_manager.emit(flow_id, "end_vertex", data)
                ),
                "on_error": lambda data: asyncio.create_task(
                    webhook_event_manager.emit(flow_id, "error", data)
                ),
                "on_end": lambda data: asyncio.create_task(
                    webhook_event_manager.emit(flow_id, "end", data)
                ),
            }

        result = await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=False,
            api_key_user=api_key_user,
            event_manager=event_manager,
            run_id=run_id,
            callbacks=callbacks,  # 👈 Passa callbacks
        )

        # Telemetria...
        return result

    except Exception as exc:
        # Emite evento de erro se há listeners
        if emit_events:
            await webhook_event_manager.emit(
                flow_id,
                "error",
                {"message": str(exc), "run_id": run_id}
            )

        # Log e telemetria...
        return None
```

#### 5. Frontend Hook (React)

```typescript
// src/frontend/src/hooks/useWebhookEvents.ts

import { useEffect, useRef } from 'react';
import useFlowStore from '@/stores/flowStore';
import useFlowsManagerStore from '@/stores/flowsManagerStore';
import { BuildStatus } from '@/constants/enums';
import { baseURL } from '@/customization/constants';

/**
 * Hook para conectar ao stream de eventos de webhook.
 * Conecta automaticamente quando flow está aberto.
 */
export function useWebhookEvents() {
  const currentFlow = useFlowsManagerStore(state => state.currentFlow);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!currentFlow?.id) return;

    // Conecta ao SSE endpoint
    const flowId = currentFlow.endpoint_name || currentFlow.id;
    const url = `${baseURL}/api/v1/webhook-events/${flowId}`;

    console.log('[WebhookEvents] Connecting to:', url);

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    // Handler de eventos (REUTILIZA o mesmo handler do build!)
    eventSource.addEventListener('vertices_sorted', (e) => {
      const data = JSON.parse(e.data);
      console.log('[WebhookEvents] vertices_sorted:', data);

      const verticesIds = data.ids;
      const verticesToRun = data.to_run;

      // Marca como TO_BUILD
      useFlowStore.getState().updateBuildStatus(
        verticesIds,
        BuildStatus.TO_BUILD
      );

      // Salva estrutura
      const verticesLayers = verticesIds.map(id => [{ id, reference: id }]);
      useFlowStore.getState().updateVerticesBuild({
        verticesLayers,
        verticesIds,
        verticesToRun,
      });
    });

    eventSource.addEventListener('build_start', (e) => {
      const data = JSON.parse(e.data);
      console.log('[WebhookEvents] build_start:', data);

      // Marca como BUILDING
      useFlowStore.getState().updateBuildStatus(
        [data.id],
        BuildStatus.BUILDING
      );

      // Define como isBuilding para bloquear outros builds
      useFlowStore.getState().setIsBuilding(true);
    });

    eventSource.addEventListener('end_vertex', (e) => {
      const data = JSON.parse(e.data);
      console.log('[WebhookEvents] end_vertex:', data);

      const buildData = data.build_data;

      if (buildData.valid) {
        // ✅ Sucesso!
        useFlowStore.getState().updateBuildStatus(
          [buildData.id],
          BuildStatus.BUILT
        );

        // Adiciona ao flowPool (cache de resultados)
        useFlowStore.getState().addDataToFlowPool(buildData, buildData.id);
      } else {
        // ❌ Erro!
        useFlowStore.getState().updateBuildStatus(
          [buildData.id],
          BuildStatus.ERROR
        );
      }

      // Anima próximas edges
      if (buildData.next_vertices_ids) {
        useFlowStore.getState().updateEdgesRunningByNodes(
          buildData.next_vertices_ids,
          true
        );
      }
    });

    eventSource.addEventListener('build_end', (e) => {
      const data = JSON.parse(e.data);
      console.log('[WebhookEvents] build_end:', data);

      useFlowStore.getState().updateBuildStatus(
        [data.id],
        BuildStatus.BUILT
      );
    });

    eventSource.addEventListener('end', (e) => {
      console.log('[WebhookEvents] end');

      // Finaliza build
      useFlowStore.getState().setIsBuilding(false);
      useFlowStore.getState().clearEdgesRunningByNodes();
    });

    eventSource.addEventListener('error', (e) => {
      const data = JSON.parse(e.data);
      console.log('[WebhookEvents] error:', data);

      // Mostra erro
      useAlertStore.getState().setErrorData({
        title: 'Webhook Build Error',
        list: [data.message],
      });

      useFlowStore.getState().setIsBuilding(false);
    });

    eventSource.addEventListener('connected', (e) => {
      console.log('[WebhookEvents] Connected!', e.data);
    });

    eventSource.addEventListener('heartbeat', (e) => {
      // Heartbeat - mantém conexão viva
      console.log('[WebhookEvents] Heartbeat');
    });

    eventSource.onerror = (error) => {
      console.error('[WebhookEvents] Connection error:', error);
      // EventSource reconecta automaticamente
    };

    // Cleanup ao desmontar
    return () => {
      console.log('[WebhookEvents] Disconnecting...');
      eventSource.close();
      eventSourceRef.current = null;
    };

  }, [currentFlow?.id]);
}
```

#### 6. Integrar Hook no Flow Page

```typescript
// src/frontend/src/pages/FlowPage/index.tsx

import { useWebhookEvents } from '@/hooks/useWebhookEvents';

export default function FlowPage() {
  // ... código existente ...

  // 👇 Adiciona hook - conecta automaticamente!
  useWebhookEvents();

  return (
    // ... resto do componente
  );
}
```

### Fluxo Completo de Teste

#### Passo 1: Abrir Flow na UI

```bash
# Usuário abre: http://localhost:3000/flow/my-chat-bot
```

**O que acontece:**
1. `FlowPage` monta
2. `useWebhookEvents()` é chamado
3. Conecta ao SSE: `GET /api/v1/webhook-events/my-chat-bot`
4. Backend adiciona queue aos listeners
5. Conexão SSE fica aberta

#### Passo 2: Enviar Webhook via Terminal

```bash
curl -X POST "http://localhost:7860/api/v1/webhook/my-chat-bot" \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-lf-..." \
  -d '{"message": "Hello from webhook!"}'
```

**O que acontece:**
1. Backend recebe POST
2. Verifica `has_listeners(my-chat-bot)` → **True!**
3. Cria task em background com `emit_events=True`
4. Retorna `202 ACCEPTED` imediatamente

#### Passo 3: Build em Background com Eventos

```python
# Backend executa em background:
1. simple_run_flow_task_with_events()
2. Callbacks são configurados
3. Build começa:

   # Evento 1: vertices_sorted
   webhook_event_manager.emit(
       "my-chat-bot",
       "vertices_sorted",
       {"ids": ["ChatInput-a", "OpenAI-b", "ChatOutput-c"], ...}
   )

   # Evento 2: build_start (ChatInput)
   webhook_event_manager.emit(
       "my-chat-bot",
       "build_start",
       {"id": "ChatInput-a"}
   )

   # ... execução ...

   # Evento 3: end_vertex (ChatInput)
   webhook_event_manager.emit(
       "my-chat-bot",
       "end_vertex",
       {"build_data": {valid: true, ...}}
   )

   # ... continua para próximo componente ...
```

#### Passo 4: Frontend Recebe Eventos

```typescript
// Frontend recebe via SSE:

1. Event: vertices_sorted
   → Marca componentes como TO_BUILD

2. Event: build_start (ChatInput)
   → Marca ChatInput como BUILDING
   → Ícone vira ⌛
   → Borda roxa animada
   → isBuilding = true

3. Event: end_vertex (ChatInput)
   → Marca ChatInput como BUILT ✅
   → Mostra duração: "2.1s"
   → Borda verde
   → Anima edge para próximo

4. Event: build_start (OpenAI)
   → Marca OpenAI como BUILDING
   → Ícone ⌛

5. Event: end_vertex (OpenAI)
   → Marca OpenAI como BUILT ✅
   → Duração: "3.5s"

6. Event: build_start (ChatOutput)
   → Marca ChatOutput como BUILDING

7. Event: end_vertex (ChatOutput)
   → Marca ChatOutput como BUILT ✅
   → Duração: "0.3s"

8. Event: end
   → isBuilding = false
   → Para todas as animações
```

**Resultado Final:**
- ✅ Todos os componentes verdes
- ✅ Durações mostradas
- ✅ Mesma experiência que apertar Play!

#### Passo 5: Fechar UI

```bash
# Usuário fecha aba do browser
```

**O que acontece:**
1. EventSource é fechado (cleanup do useEffect)
2. Backend detecta desconexão
3. Remove queue dos listeners
4. `has_listeners()` retorna False
5. **Próximos webhooks NÃO emitirão eventos** (performance!)

---

## 🆚 Comparação com WebSocket

### Por Que NÃO WebSocket?

**WebSocket seria:**
```typescript
// Mais complexo de implementar
const ws = new WebSocket('ws://localhost:7860/webhook-events/flow-id');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // ... handler
};

// Precisa implementar reconnect manual
ws.onclose = () => {
  setTimeout(() => reconnect(), 1000);
};
```

**SSE é mais simples:**
```typescript
// Reconnect automático!
const eventSource = new EventSource('/webhook-events/flow-id');

eventSource.addEventListener('build_start', (e) => {
  const data = JSON.parse(e.data);
  // ... handler
});
```

**Comparação:**

| Característica | SSE | WebSocket |
|----------------|-----|-----------|
| **Direção** | Unidirecional (server → client) | Bidirecional |
| **Reconnect** | ✅ Automático | ❌ Manual |
| **HTTP/HTTPS** | ✅ Sim | ⚠️ Requer upgrade |
| **Protocolo** | HTTP/1.1 | WS/WSS |
| **Browser API** | ✅ EventSource (nativo) | ✅ WebSocket (nativo) |
| **Overhead** | Menor | Maior |
| **Ideal para** | Notificações, updates | Chat bidirecional |

**Para este caso:** SSE é melhor porque só precisamos de **server → client**.

---

## 🚀 Plano de Implementação (Passo a Passo)

### Fase 1: Backend - Event Manager (2-3 dias)

**Tarefas:**
1. ✅ Criar `WebhookEventManager` class
   - Gerencia listeners por flow_id
   - Subscribe/unsubscribe
   - Emit events
   - Thread-safe (asyncio.Lock)

2. ✅ Criar endpoint `/webhook-events/{flow_id}`
   - SSE streaming
   - Heartbeat a cada 30s
   - Detecção de desconexão

3. ✅ Modificar `webhook_run_flow`
   - Verificar `has_listeners()`
   - Passar flag `emit_events` para background task

4. ✅ Modificar execução do flow
   - Adicionar callbacks para eventos
   - Emitir: vertices_sorted, build_start, end_vertex, build_end, end, error

**Arquivos a modificar:**
```
src/backend/base/langflow/
├── services/
│   └── event_manager.py          # NOVO
├── api/v1/
│   └── endpoints.py               # MODIFICAR
└── graph/graph/
    └── base.py                    # MODIFICAR (simple_run_flow)
```

### Fase 2: Frontend - Hook e Integração (1-2 dias)

**Tarefas:**
1. ✅ Criar hook `useWebhookEvents`
   - Conecta ao SSE
   - Handlers para cada tipo de evento
   - Reutiliza lógica de `buildUtils.ts`
   - Cleanup ao desmontar

2. ✅ Integrar no FlowPage
   - Adicionar hook no componente
   - Testar com flow aberto/fechado

**Arquivos a criar/modificar:**
```
src/frontend/src/
├── hooks/
│   └── useWebhookEvents.ts        # NOVO
└── pages/FlowPage/
    └── index.tsx                  # MODIFICAR (adicionar hook)
```

### Fase 3: Testes (1-2 dias)

**Cenários de teste:**

1. ✅ **Webhook com UI aberta**
   - Abrir flow na UI
   - Enviar webhook via curl
   - Verificar: animações, estados, durações

2. ✅ **Webhook sem UI aberta**
   - Fechar UI
   - Enviar webhook via curl
   - Verificar: executa normalmente, sem overhead

3. ✅ **Múltiplas UIs abertas**
   - Abrir flow em 2 abas
   - Enviar webhook
   - Verificar: ambas recebem eventos

4. ✅ **Desconexão e reconnect**
   - Abrir flow
   - Desconectar rede
   - Reconectar
   - Verificar: EventSource reconecta automaticamente

5. ✅ **Build com erro**
   - Webhook com componente inválido
   - Verificar: estado ERROR, modal de erro

6. ✅ **Performance**
   - Webhook sem listeners: deve ser rápido
   - Webhook com listeners: overhead mínimo

### Fase 4: Documentação e Polimento (1 dia)

**Tarefas:**
1. ✅ Documentar novo endpoint
2. ✅ Atualizar docs de webhook
3. ✅ Adicionar logs para debugging
4. ✅ Configuração opcional (enable/disable)

---

## 📊 Vantagens da Solução

### 1. Reutilização de Código
- ✅ **Mesmos eventos** do build atual
- ✅ **Mesmo handler** `onEvent()`
- ✅ **Mesmas animações** e feedback visual
- ✅ **Mesma lógica** de estado (BuildStatus)

### 2. Performance
- ✅ **Zero overhead** quando UI fechada
- ✅ **In-memory** (sem banco de dados)
- ✅ **Conexão única** por flow (não por componente)
- ✅ **Backpressure** handling (queue com limite)

### 3. Escalabilidade
- ✅ **Stateless** (pode escalar horizontalmente)
- ✅ **Graceful degradation** (se falhar, webhook funciona)
- ✅ **Fácil migração** para Redis Pub/Sub no futuro

### 4. Developer Experience
- ✅ **Simples de implementar** (SSE nativo)
- ✅ **Fácil de debugar** (logs, eventos)
- ✅ **Auto-reconnect** (EventSource)
- ✅ **Type-safe** (TypeScript)

---

## 🔮 Evolução Futura: Redis Pub/Sub

Para ambientes de **produção com múltiplos workers**, evoluir para Redis:

```
┌────────────────────────────────────────────────────┐
│              ARQUITETURA COM REDIS                 │
└────────────────────────────────────────────────────┘

Frontend            Load Balancer         Worker 1         Worker 2
   │                     │                    │                │
   │ SSE connection      │                    │                │
   ├────────────────────►│                    │                │
   │                     ├────────────────────►│                │
   │                     │    (sticky session)│                │
   │                     │                    │                │
   │                     │                    │                │
Terminal                │                    │                │
   │                     │                    │                │
   │ POST /webhook       │                    │                │
   ├────────────────────►│                    │                │
   │                     ├───────────────────────────────────►│
   │                     │                    │                │
   │                     │                    │     ┌──────────▼────────┐
   │                     │                    │     │  Redis Pub/Sub    │
   │                     │                    │     │                   │
   │                     │                    │     │ Channel:          │
   │                     │                    │     │  webhook:flow-id  │
   │                     │                    │     └──────────┬────────┘
   │                     │                    │                │
   │                     │                    │◄───────────────┘
   │                     │                    │  (subscribe)   │
   │                     │                    │                │
   │                     │                    │  emit event    │
   │                     │◄───────────────────┤                │
   │◄────────────────────┤   SSE event       │                │
   │     (via Worker 1)  │                    │                │
```

**Benefícios:**
- ✅ Funciona com **load balancer**
- ✅ Workers podem estar em **máquinas diferentes**
- ✅ **Persistência** opcional (Redis Streams)
- ✅ **Replay** de eventos

**Implementação:**
```python
# Substituir webhook_event_manager por Redis Pub/Sub
import redis.asyncio as redis

class RedisEventManager:
    def __init__(self):
        self.redis = redis.from_url("redis://localhost")

    async def emit(self, flow_id: str, event_type: str, data: Any):
        channel = f"webhook:{flow_id}"
        event = {"event": event_type, "data": data}
        await self.redis.publish(channel, json.dumps(event))

    async def subscribe(self, flow_id: str) -> AsyncIterator:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"webhook:{flow_id}")

        async for message in pubsub.listen():
            if message["type"] == "message":
                yield json.loads(message["data"])
```

---

## 🎯 Resumo e Recomendação Final

### ✅ MELHOR SOLUÇÃO: SSE (Server-Sent Events)

**Por quê:**
1. ✅ **Reutiliza 90% do código existente** do build
2. ✅ **Simples de implementar** (2-3 dias backend, 1-2 dias frontend)
3. ✅ **Performance excelente** (zero overhead sem listeners)
4. ✅ **Reconnect automático** (EventSource nativo)
5. ✅ **Mesma experiência** visual do build atual
6. ✅ **Escalável** (fácil migrar para Redis)

### 📋 Checklist de Implementação

**Backend:**
- [ ] Criar `WebhookEventManager` class
- [ ] Criar endpoint `/webhook-events/{flow_id}`
- [ ] Modificar `webhook_run_flow` para detectar listeners
- [ ] Adicionar callbacks de eventos no flow execution
- [ ] Testes unitários

**Frontend:**
- [ ] Criar hook `useWebhookEvents`
- [ ] Integrar no `FlowPage`
- [ ] Testar reconexão automática
- [ ] Testes E2E

**Testes:**
- [ ] Webhook com UI aberta (feedback visual)
- [ ] Webhook sem UI aberta (performance)
- [ ] Múltiplas UIs abertas
- [ ] Build com erro
- [ ] Desconexão/reconnect

**Docs:**
- [ ] Documentar novo endpoint
- [ ] Atualizar docs de webhook
- [ ] Exemplos de uso

### 🚀 Resultado Final

```bash
# Terminal
$ curl -X POST "http://localhost:7860/api/v1/webhook/my-chat" \
    -H "Content-Type: application/json" \
    -d '{"message": "test"}'

# UI (em tempo real):
#
# ┌─────────────────────┐
# │ ChatInput           │
# │ ⌛ Building...      │  ← Borda roxa animada
# └─────────────────────┘
#          ↓
# ┌─────────────────────┐
# │ OpenAI              │
# │ ⏸️ Ready            │
# └─────────────────────┘
#
# (2 segundos depois)
#
# ┌─────────────────────┐
# │ ChatInput           │
# │ ✅ 2.1s             │  ← Borda verde
# └─────────────────────┘
#          ↓  (edge verde animada)
# ┌─────────────────────┐
# │ OpenAI              │
# │ ⌛ Building...      │  ← Agora está buildando
# └─────────────────────┘
```

**Experiência idêntica a apertar Play!** 🎉
