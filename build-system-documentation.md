# Documentação Completa do Sistema de Build do Langflow
## Para Pessoas Leigas - Explicação Detalhada com Todos os Detalhes

---

## 📚 Índice

1. [Introdução - O Que é "Build" no Langflow?](#introdução)
2. [Estados de Build - As 5 Fases de Vida de um Componente](#estados-de-build)
3. [Arquitetura Visual do Sistema](#arquitetura-visual)
4. [Fluxo Completo de Execução](#fluxo-completo-de-execução)
5. [Camada de Interface (React)](#camada-de-interface-react)
6. [Gerenciamento de Estado (Zustand Store)](#gerenciamento-de-estado-zustand-store)
7. [Métodos de Entrega de Eventos](#métodos-de-entrega-de-eventos)
8. [Sistema de Visualização](#sistema-de-visualização)
9. [Animações e Feedback Visual](#animações-e-feedback-visual)
10. [Telemetria e Analytics](#telemetria-e-analytics)
11. [Casos de Uso Práticos](#casos-de-uso-práticos)
12. [Erros Comuns e Como São Tratados](#erros-comuns)
13. [Performance e Otimizações](#performance-e-otimizações)

---

## Introdução

### O Que é "Build" no Langflow?

Imagine que você está construindo uma casa LEGO. Cada peça representa um **componente** no Langflow (por exemplo: um componente de chat, um componente de busca, etc.).

**"Buildar"** (construir/executar) um componente no Langflow significa:
1. **Validar** que todas as conexões estão corretas
2. **Executar** a lógica do componente (processar dados)
3. **Verificar** se funcionou sem erros
4. **Mostrar** os resultados

É como apertar o botão "▶️ Play" em um vídeo, mas para seus componentes de IA/dados.

### Por Que Isso é Importante?

Quando você clica no botão "Play" (▶️) em um componente:
- O frontend **precisa saber** se está funcionando ✅
- O frontend **precisa mostrar** progresso 🔄
- O frontend **precisa exibir** erros ❌
- O frontend **precisa atualizar** a interface em tempo real

Este documento explica **EXATAMENTE** como tudo isso funciona, passo a passo.

---

## Estados de Build

### As 5 Fases de Vida de um Componente

Cada componente no Langflow pode estar em **um de 5 estados** diferentes. Pense neles como semáforos:

```typescript
export enum BuildStatus {
  TO_BUILD = "TO_BUILD",      // 🔵 Azul - Pronto para começar
  BUILDING = "BUILDING",       // 🟡 Amarelo - Em execução
  BUILT = "BUILT",             // 🟢 Verde - Sucesso!
  ERROR = "ERROR",             // 🔴 Vermelho - Erro!
  INACTIVE = "INACTIVE",       // ⚫ Cinza - Desativado
}
```

### Detalhamento de Cada Estado

#### 1. **TO_BUILD** (Pronto para Construir)
```
Estado: ⏸️ Aguardando
Cor: Azul/Padrão
Ícone: Nenhum ícone especial
Mensagem: "Build Component"
```

**Quando acontece:**
- Componente foi adicionado ao flow
- Build anterior foi resetado
- Usuário cancelou o build

**O que o usuário vê:**
- Borda padrão do componente
- Botão Play (▶️) ativo
- Sem indicadores de status

**Código responsável:**
```typescript
// buildUtils.ts:128
useFlowStore.getState().updateBuildStatus(verticesToRun, BuildStatus.TO_BUILD);
```

#### 2. **BUILDING** (Construindo)
```
Estado: 🔄 Executando
Cor: Amarelo/Animado
Ícone: Loader2 (girando)
Mensagem: "Building..."
```

**Quando acontece:**
- Usuário clicou no botão Play
- Backend começou a processar o componente
- Componente está na fila de execução

**O que o usuário vê:**
- Ícone de loading girando (⌛)
- Edges (conexões) animadas
- Borda amarela animada
- Mensagem "Building..." no tooltip

**Animação:**
```css
/* Ícone gira continuamente */
.animate-spin {
  animation: spin 1s linear infinite;
}

/* Edges ficam animadas */
.running {
  stroke-dasharray: 5;
  animation: dashdraw 0.5s linear infinite;
}
```

**Código responsável:**
```typescript
// buildUtils.ts:903
get().updateBuildStatus(idList, BuildStatus.BUILDING);

// NodeStatus/index.tsx:309
const iconName = BuildStatus.BUILDING === buildStatus ? "Loader2" : "Play";
```

**Tempo Mínimo Visual:**
```typescript
// buildUtils.ts:164
const MIN_VISUAL_BUILD_TIME_MS = 300;

// Garante que o usuário veja o loading por pelo menos 300ms
// (mesmo se o build for instantâneo)
if (delta < MIN_VISUAL_BUILD_TIME_MS) {
  await new Promise(resolve => setTimeout(resolve, MIN_VISUAL_BUILD_TIME_MS - delta));
}
```

#### 3. **BUILT** (Construído com Sucesso)
```
Estado: ✅ Completo
Cor: Verde
Ícone: Nenhum (mostra duração)
Mensagem: Detalhes do resultado + tempo de execução
```

**Quando acontece:**
- Build terminou sem erros
- Todas as validações passaram
- Resultados foram salvos

**O que o usuário vê:**
- **Duração da execução** em verde (ex: "1.2s")
- Borda verde do componente
- Tooltip com:
  - Status de validação ✅
  - Timestamp da última execução
  - Duração formatada
  - Resultados (se houver)

**Formato da duração:**
```typescript
// NodeStatus/utils/format-run-time.ts
"0.5s"   → "500ms"
"1.2s"   → "1.2s"
"65s"    → "1m 5s"
"3661s"  → "1h 1m"
```

**Código responsável:**
```typescript
// buildUtils.ts:535
onBuildUpdate(buildData, BuildStatus.BUILT, "");

// flowStore.ts:1008
if (status == BuildStatus.BUILT) {
  const timestamp_string = new Date(Date.now()).toLocaleString();
  newFlowBuildStatus[id].timestamp = timestamp_string;
}
```

**Armazenamento:**
```typescript
// flowStore.ts:1002
flowBuildStatus: {
  "Component-abc123": {
    status: "BUILT",
    timestamp: "1/15/2024, 10:30:00 AM"
  }
}
```

#### 4. **ERROR** (Erro)
```
Estado: ❌ Falhou
Cor: Vermelho
Ícone: CircleAlert (⚠️)
Mensagem: Mensagem de erro detalhada
```

**Quando acontece:**
- Validação falhou (campos obrigatórios vazios)
- Exceção durante execução
- Timeout
- Erro de rede

**O que o usuário vê:**
- **Ícone de alerta vermelho** (⚠️)
- Borda vermelha do componente
- Tooltip com:
  - Título do erro
  - Lista de mensagens de erro
  - Stack trace (se disponível)
- **Modal de erro** aparece automaticamente

**Tipos de erro:**

**a) Campos obrigatórios faltando:**
```typescript
// NodeStatus/build-status-display.tsx:62-64
if (buildStatus === BuildStatus.ERROR && !validationStatus) {
  return <StatusMessage>{STATUS_MISSING_FIELDS_ERROR}</StatusMessage>;
}
// Mostra: "Missing Required Fields"
```

**b) Erro durante execução:**
```typescript
// buildUtils.ts:512-531
const errorMessages = Object.keys(buildData.data.outputs).flatMap(key => {
  const outputs = buildData.data.outputs[key];
  return outputs
    .filter(log => isErrorLogType(log.message))
    .map(log => log.message.errorMessage);
});
```

**Código responsável:**
```typescript
// buildUtils.ts:531
onBuildUpdate(buildData, BuildStatus.ERROR, "");

// buildUtils.ts:875
useFlowStore.getState().updateBuildStatus(idList, BuildStatus.ERROR);
```

#### 5. **INACTIVE** (Inativo)
```
Estado: ⚫ Desabilitado
Cor: Cinza
Ícone: CircleOff
Mensagem: "Inactive"
```

**Quando acontece:**
- Componente foi desativado manualmente
- Componente não faz parte do caminho de execução
- Componente foi "frozen" (congelado)

**O que o usuário vê:**
- Ícone de círculo cortado (⊘)
- Borda cinza
- Componente semi-transparente
- Tooltip mostra "Inactive"

**Código responsável:**
```typescript
// buildUtils.ts:686-691
onBuildUpdate(
  getInactiveVertexData(element.id),
  BuildStatus.INACTIVE,
  runId
);
```

---

## Arquitetura Visual do Sistema

### Visão Geral dos Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                         USUÁRIO                                 │
│                    (Clica no botão Play)                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CAMADA REACT                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  NodeStatus Component                                │      │
│  │  - Botão Play                                        │      │
│  │  - Ícones de status                                  │      │
│  │  - Animações                                         │      │
│  └────────────┬─────────────────────────────────────────┘      │
└───────────────┼──────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ZUSTAND STORE                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  flowStore.ts                                        │      │
│  │  - buildFlow() → Inicia processo                    │      │
│  │  - flowBuildStatus → Estado de cada componente      │      │
│  │  - updateBuildStatus() → Atualiza estados           │      │
│  │  - isBuilding → Flag global                         │      │
│  └────────────┬─────────────────────────────────────────┘      │
└───────────────┼──────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BUILD UTILS                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  buildFlowVertices()                                 │      │
│  │  - Validação de nodes/edges                          │      │
│  │  - Criação de camadas (layers)                       │      │
│  │  - Coordenação de execução                           │      │
│  └────────────┬─────────────────────────────────────────┘      │
└───────────────┼──────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│              MÉTODOS DE ENTREGA DE EVENTOS                      │
│  ┌──────────────┬──────────────┬──────────────────────┐        │
│  │   DIRECT     │  STREAMING   │      POLLING         │        │
│  │  (Fastest)   │   (Medium)   │      (Slowest)       │        │
│  └──────┬───────┴──────┬───────┴──────────┬───────────┘        │
└─────────┼──────────────┼──────────────────┼────────────────────┘
          │              │                  │
          ▼              ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND API                                 │
│  /api/v1/build/{flow_id}                                       │
│  - Valida flow                                                  │
│  - Executa componentes em ordem                                 │
│  - Envia eventos de progresso                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Fluxo de Dados Completo

```
Usuário clica Play
       ↓
handleClickRun() (NodeStatus)
       ↓
buildFlow({ stopNodeId }) (flowStore)
       ↓
buildFlowVerticesWithFallback() (buildUtils)
       ↓
Valida nodes e edges
       ↓
POST /api/v1/build/{flow_id}
       ↓
┌──────────────────┐
│  Event Delivery  │
└────────┬─────────┘
         │
    ┌────┴────┬─────────┬──────────┐
    ↓         ↓         ↓          ↓
 DIRECT  STREAMING  POLLING     (fallback)
    │         │         │
    └────┬────┴────┬────┘
         ↓         ↓
   Event Handler (onEvent)
         ↓
  ┌──────────────┐
  │ Event Types: │
  ├──────────────┤
  │ vertices_sorted → Define ordem       │
  │ build_start     → Começa componente  │
  │ build_end       → Termina componente │
  │ end_vertex      → Processa resultado │
  │ add_message     → Adiciona mensagem  │
  │ token           → Streaming token    │
  │ error           → Trata erro         │
  │ end             → Finaliza tudo      │
  └──────────────┘
         ↓
  updateBuildStatus()
         ↓
  React Re-render
         ↓
  Usuário vê atualização na UI
```

---

## Fluxo Completo de Execução

### Passo a Passo Detalhado

Vamos acompanhar o que acontece quando você clica no botão Play (▶️):

#### **Passo 1: Click do Usuário**

**Arquivo:** `NodeStatus/index.tsx:290-303`

```typescript
const handleClickRun = () => {
  setFlowPool({});  // Limpa resultados anteriores

  // Se já está buildando e usuário hovering, PARA o build
  if (BuildStatus.BUILDING === buildStatus && isHovered) {
    stopBuilding();
    return;
  }

  // Não permite clicar se já está buildando
  if (buildStatus === BuildStatus.BUILDING || isBuilding) return;

  // INICIA O BUILD!
  buildFlow({
    stopNodeId: nodeId,                    // Qual componente parar
    eventDelivery: eventDeliveryConfig,    // Método de entrega
  });

  // Analytics
  track("Flow Build - Clicked", { stopNodeId: nodeId });
};
```

**O que acontece:**
1. Limpa `flowPool` (cache de resultados)
2. Verifica se já está buildando
3. Chama `buildFlow()` do store
4. Registra evento de analytics

---

#### **Passo 2: Preparação no Store**

**Arquivo:** `flowStore.ts:654-686`

```typescript
buildFlow: async ({
  startNodeId,
  stopNodeId,
  input_value,
  files,
  silent,
  session,
  stream = true,
  eventDelivery = EventDeliveryType.STREAMING,
}) => {
  // Salva parâmetros para possível retry
  set({
    pastBuildFlowParams: { startNodeId, stopNodeId, ... },
    buildInfo: null,
  });

  const playgroundPage = get().playgroundPage;
  get().setIsBuilding(true);  // FLAG GLOBAL: "Está buildando!"
  set({ flowBuildStatus: {} });  // Limpa status anterior

  const currentFlow = useFlowsManagerStore.getState().currentFlow;
  const setErrorData = useAlertStore.getState().setErrorData;
  const edges = get().edges;
  let errors: string[] = [];

  // ... continua
}
```

**O que acontece:**
1. Define `isBuilding = true` (bloqueia novos builds)
2. Limpa `flowBuildStatus` anterior
3. Prepara para coletar erros
4. Salva referência ao flow atual

---

#### **Passo 3: Validação de Nodes e Edges**

**Arquivo:** `flowStore.ts:696-740`

```typescript
// Determina quais nodes validar
let nodesToValidate = get().nodes;
let edgesToValidate = edges;

if (startNodeId) {
  // Se tem startNodeId, valida só os componentes "downstream" (após ele)
  const downstream = getConnectedSubgraph(
    startNodeId,
    get().nodes,
    edges,
    "downstream",
  );
  nodesToValidate = downstream.nodes;
  edgesToValidate = downstream.edges;
} else if (stopNodeId) {
  // Se tem stopNodeId, valida só os componentes "upstream" (antes dele)
  get().setStopNodeId(stopNodeId);
  const upstream = getConnectedSubgraph(
    stopNodeId,
    get().nodes,
    edges,
    "upstream",
  );
  nodesToValidate = upstream.nodes;
  edgesToValidate = upstream.edges;
}

// VALIDA EDGES
for (const edge of edgesToValidate) {
  const errorsEdge = validateEdge(edge, nodesToValidate, edgesToValidate);
  if (errorsEdge.length > 0) {
    errors.push(errorsEdge.join("\n"));
  }
}

// VALIDA NODES
const errorsObjs = validateNodes(nodesToValidate, edges);
errors = errors.concat(errorsObjs.flatMap(obj => obj.errors));

// SE TEM ERROS, PARA TUDO!
if (errors.length > 0) {
  setErrorData({
    title: MISSED_ERROR_ALERT,
    list: errors,
  });
  const ids = errorsObjs.flatMap(obj => obj.id);
  get().updateBuildStatus(ids, BuildStatus.ERROR);
  get().setIsBuilding(false);
  throw new Error("Invalid components");
}
```

**Tipos de validação:**

1. **Edge Validation:**
   - Tipo de dado compatível?
   - Source e target existem?
   - Conexão válida?

2. **Node Validation:**
   - Campos obrigatórios preenchidos?
   - Valores válidos?
   - Template correto?

**Se houver erro:**
- ❌ Marca componentes como `ERROR`
- ❌ Mostra modal de erro
- ❌ Para o processo
- ❌ Define `isBuilding = false`

---

#### **Passo 4: Chamada ao Backend**

**Arquivo:** `buildUtils.ts:194-415`

```typescript
export async function buildFlowVertices({
  flowId,
  startNodeId,
  stopNodeId,
  eventDelivery,
  // ... outros parâmetros
}) {
  const inputs = {};

  // Monta URL do build
  let buildUrl = customBuildUrl(flowId, playgroundPage);
  // Exemplo: /api/v1/build/{flowId}

  const queryParams = new URLSearchParams();

  if (startNodeId) {
    queryParams.append("start_component_id", startNodeId);
  }
  if (stopNodeId) {
    queryParams.append("stop_component_id", stopNodeId);
  }

  queryParams.append("event_delivery", eventDelivery ?? EventDeliveryType.POLLING);

  if (queryParams.toString()) {
    buildUrl = `${buildUrl}?${queryParams.toString()}`;
  }

  // Prepara payload
  const postData = {};
  if (files) postData["files"] = files;
  if (nodes) postData["data"] = { nodes, edges };

  // Adiciona timestamp do cliente para tracking de latência
  inputs["client_request_time"] = Date.now();
  if (Object.keys(inputs).length > 0) {
    postData["inputs"] = inputs;
  }

  // ESCOLHE MÉTODO DE ENTREGA DE EVENTOS
  if (eventDelivery === EventDeliveryType.DIRECT) {
    // Modo DIRECT: streaming direto do endpoint de build
    return performStreamingRequest({
      method: "POST",
      url: buildUrl,
      body: postData,
      onData: async (event) => {
        const type = event["event"];
        const data = event["data"];
        return await onEvent(type, data, ...);
      },
      // ... handlers de erro
    });
  }

  // Modos STREAMING ou POLLING: processo em 2 etapas

  // 1. Inicia o build e recebe job_id
  const buildResponse = await fetch(buildUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(postData),
  });

  const { job_id } = await buildResponse.json();

  // 2. Conecta ao endpoint de eventos
  const eventsUrl = customEventsUrl(job_id);
  // Exemplo: /api/v1/build/events/{job_id}

  if (eventDelivery === EventDeliveryType.STREAMING) {
    // Usa SSE (Server-Sent Events)
    return performStreamingRequest({
      method: "GET",
      url: eventsUrl,
      onData: async (event) => { ... },
    });
  } else {
    // Usa polling (requisições GET repetidas)
    return await pollBuildEvents(
      eventsUrl,
      buildResults,
      verticesStartTimeMs,
      callbacks,
      buildController,
    );
  }
}
```

**Resumo:**
1. Monta URL com query params
2. Prepara payload com dados do flow
3. Escolhe método de entrega
4. Inicia processo de build no backend
5. Conecta ao stream de eventos

---

#### **Passo 5: Processamento de Eventos**

**Arquivo:** `buildUtils.ts:433-601`

Esta é a parte **MAIS IMPORTANTE** do sistema! Cada evento do backend é processado aqui:

```typescript
async function onEvent(
  type: string,
  data: any,
  buildResults: boolean[],
  verticesStartTimeMs: Map<string, number>,
  callbacks: { ... }
): Promise<boolean> {

  switch (type) {

    // ============================================================
    // EVENTO 1: vertices_sorted
    // ============================================================
    case "vertices_sorted": {
      // Backend calculou a ORDEM de execução dos componentes
      const verticesToRun = data.to_run;
      const verticesIds = data.ids;

      // Marca todos como TO_BUILD
      useFlowStore.getState().updateBuildStatus(verticesIds, BuildStatus.TO_BUILD);

      // Registra timestamp de início
      verticesIds.forEach(id => verticesStartTimeMs.set(id, Date.now()));

      // Salva estrutura de camadas
      const verticesLayers = verticesIds.map(id => [{ id, reference: id }]);
      useFlowStore.getState().updateVerticesBuild({
        verticesLayers,
        verticesIds,
        verticesToRun,
      });

      // Callback de sucesso
      if (onValidateNodes) {
        onValidateNodes(data.to_run);
        if (onGetOrderSuccess) onGetOrderSuccess();
        useFlowStore.getState().setIsBuilding(true);
      }

      return true;
    }

    // ============================================================
    // EVENTO 2: build_start
    // ============================================================
    case "build_start": {
      // Backend começou a buildar este componente
      useFlowStore.getState().updateBuildStatus(
        [data.id],
        BuildStatus.BUILDING
      );
      break;
    }

    // ============================================================
    // EVENTO 3: end_vertex (MAIS IMPORTANTE!)
    // ============================================================
    case "end_vertex": {
      const buildData = data.build_data;

      // Calcula tempo mínimo de visualização
      const startTimeMs = verticesStartTimeMs.get(buildData.id);
      if (startTimeMs) {
        const delta = Date.now() - startTimeMs;
        // Garante no mínimo 300ms de loading visual
        if (delta < MIN_VISUAL_BUILD_TIME_MS) {
          await new Promise(resolve =>
            setTimeout(resolve, MIN_VISUAL_BUILD_TIME_MS - delta)
          );
        }
      }

      if (onBuildUpdate) {
        if (!buildData.valid) {
          // ❌ BUILD FALHOU!

          // Extrai mensagens de erro
          const errorMessages = Object.keys(buildData.data.outputs).flatMap(key => {
            const outputs = buildData.data.outputs[key];
            return outputs
              .filter(log => isErrorLogType(log.message))
              .map(log => log.message.errorMessage);
          });

          // Mostra erro
          onBuildError && onBuildError(
            "Error Building Component",
            errorMessages,
            [{ id: buildData.id }]
          );

          // Marca como ERROR
          onBuildUpdate(buildData, BuildStatus.ERROR, "");
          buildResults.push(false);
          return false;

        } else {
          // ✅ BUILD SUCESSO!

          onBuildUpdate(buildData, BuildStatus.BUILT, "");
          buildResults.push(true);
        }
      }

      // Limpa animações de edges
      await useFlowStore.getState().clearEdgesRunningByNodes();

      // Atualiza próximos vértices
      if (buildData.next_vertices_ids) {
        // Marca próximos componentes como TO_BUILD
        useFlowStore.getState().updateBuildStatus(
          buildData.next_vertices_ids,
          BuildStatus.TO_BUILD
        );

        // Anima edges até próximos componentes
        useFlowStore.getState().updateEdgesRunningByNodes(
          buildData.next_vertices_ids,
          true
        );
      }

      return true;
    }

    // ============================================================
    // EVENTO 4: build_end
    // ============================================================
    case "build_end": {
      // Backend terminou de buildar este componente
      useFlowStore.getState().updateBuildStatus(
        [data.id],
        BuildStatus.BUILT
      );
      break;
    }

    // ============================================================
    // EVENTO 5: add_message
    // ============================================================
    case "add_message": {
      // Adiciona mensagem ao chat/log
      useMessagesStore.getState().addMessage(data);
      return true;
    }

    // ============================================================
    // EVENTO 6: token (streaming de chat)
    // ============================================================
    case "token": {
      // Atualiza texto de mensagem token por token
      setTimeout(() => {
        flushSync(() => {
          useMessagesStore.getState().updateMessageText(data.id, data.chunk);
        });
      }, 10);
      return true;
    }

    // ============================================================
    // EVENTO 7: remove_message
    // ============================================================
    case "remove_message": {
      useMessagesStore.getState().removeMessage(data);
      return true;
    }

    // ============================================================
    // EVENTO 8: end (FINALIZAÇÃO!)
    // ============================================================
    case "end": {
      // Todos os componentes terminaram!
      const allNodesValid = buildResults.every(result => result);

      onBuildComplete && onBuildComplete(allNodesValid);
      useFlowStore.getState().setIsBuilding(false);

      return true;
    }

    // ============================================================
    // EVENTO 9: error
    // ============================================================
    case "error": {
      if (data?.category === "error") {
        useMessagesStore.getState().addMessage(data);

        if (!data?.properties?.source?.id) {
          onBuildError && onBuildError("Error Building Flow", [data.text]);
        }
      }
      buildResults.push(false);
      return true;
    }

    default:
      return true;
  }
}
```

**Sequência de Eventos Típica:**

```
1. vertices_sorted  → Define ordem de execução
   ↓
2. build_start (Component A)  → Começa Component A
   ↓
3. end_vertex (Component A)   → Termina Component A com sucesso
   ↓
4. build_start (Component B)  → Começa Component B
   ↓
5. end_vertex (Component B)   → Termina Component B com sucesso
   ↓
6. end  → Tudo finalizado!
```

---

#### **Passo 6: Atualização do Estado**

**Arquivo:** `flowStore.ts:1001-1021`

```typescript
updateBuildStatus: (nodeIdList: string[], status: BuildStatus) => {
  const newFlowBuildStatus = { ...get().flowBuildStatus };

  nodeIdList.forEach((id) => {
    newFlowBuildStatus[id] = { status };

    // Se foi BUILT, salva timestamp
    if (status == BuildStatus.BUILT) {
      const timestamp_string = new Date(Date.now()).toLocaleString();
      newFlowBuildStatus[id].timestamp = timestamp_string;
    }
  });

  set({ flowBuildStatus: newFlowBuildStatus });
},
```

**Estrutura do estado:**

```typescript
flowBuildStatus: {
  "ChatInput-abc123": {
    status: "BUILT",
    timestamp: "1/15/2024, 10:30:00 AM"
  },
  "OpenAI-xyz789": {
    status: "BUILDING",
    timestamp: undefined
  },
  "TextOutput-def456": {
    status: "TO_BUILD",
    timestamp: undefined
  }
}
```

---

#### **Passo 7: Re-render do React**

**Arquivo:** `NodeStatus/index.tsx:31-59`

```typescript
export default function NodeStatus({
  nodeId,
  buildStatus,  // 🔥 Vem do hook useBuildStatus
  ...
}) {
  // buildStatus mudou → React re-renderiza!

  // Atualiza borda do componente
  useEffect(() => {
    setBorderColor(
      getNodeBorderClassName(selected, buildStatus, validationStatus)
    );
  }, [buildStatus, ...]);

  // Atualiza ícone
  const iconStatus = useIconStatus(buildStatus);

  // Atualiza botão Play/Stop
  const iconName =
    BuildStatus.BUILDING === buildStatus
      ? isHovered ? "Square" : "Loader2"
      : "Play";

  // ... render
}
```

**Hook que monitora mudanças:**

**Arquivo:** `use-get-build-status.ts:5-35`

```typescript
export const useBuildStatus = (data: NodeDataType, nodeId: string) => {
  return useFlowStore((state) => {
    // Busca status do componente
    const buildStatus = state.flowBuildStatus[nodeId]?.status;

    // Se é um flow aninhado, verifica todos os sub-componentes
    if (data.node?.flow?.data?.nodes) {
      const nodes = data.node.flow.data.nodes;
      const buildStatuses = nodes
        .map(node => state.flowBuildStatus[node.id]?.status)
        .filter(Boolean);

      // Lógica de prioridade:
      // 1. Se TODOS são BUILT → BUILT
      if (buildStatuses.every(status => status === BuildStatus.BUILT)) {
        return BuildStatus.BUILT;
      }
      // 2. Se ALGUM é BUILDING → BUILDING
      if (buildStatuses.some(status => status === BuildStatus.BUILDING)) {
        return BuildStatus.BUILDING;
      }
      // 3. Se ALGUM é ERROR → ERROR
      if (buildStatuses.some(status => status === BuildStatus.ERROR)) {
        return BuildStatus.ERROR;
      }

      return BuildStatus.TO_BUILD;
    }

    return buildStatus;
  });
};
```

---

## Camada de Interface (React)

### Componentes Principais

#### 1. **NodeStatus Component**

**Localização:** `CustomNodes/GenericNode/components/NodeStatus/index.tsx`

**Responsabilidade:** Exibir status visual e botão de execução

**Props:**
```typescript
interface NodeStatusProps {
  nodeId: string;               // ID único do componente
  display_name: string;         // Nome para exibição
  selected?: boolean;           // Se está selecionado
  setBorderColor: (color) => void;  // Callback para mudar borda
  frozen?: boolean;             // Se está congelado
  showNode: boolean;            // Se deve mostrar
  data: NodeDataType;           // Dados do componente
  buildStatus: BuildStatus;     // Estado atual de build
  // ... outros
}
```

**Estados internos:**
```typescript
const [validationString, setValidationString] = useState<string>("");
const [validationStatus, setValidationStatus] = useState<VertexBuildTypeAPI | null>(null);
const [isPolling, setIsPolling] = useState(false);
const [isHovered, setIsHovered] = useState(false);
```

**Renders diferentes por estado:**

```typescript
// Estado: BUILDING
<IconComponent
  name="Loader2"
  className="animate-spin text-muted-foreground"
/>

// Estado: BUILT (com sucesso)
<div className="text-accent-emerald-foreground">
  {normalizeTimeString(validationStatus?.data?.duration)}
  {/* Ex: "1.2s" */}
</div>

// Estado: ERROR
<IconComponent
  name="CircleAlert"
  className="text-destructive"
/>

// Estado: INACTIVE
<IconComponent
  name="CircleOff"
  className="text-muted-foreground"
/>
```

**Interações:**

```typescript
// Click no botão Play
const handleClickRun = () => {
  if (BuildStatus.BUILDING === buildStatus && isHovered) {
    stopBuilding();  // Para o build se já está rodando
    return;
  }

  buildFlow({ stopNodeId: nodeId });
  track("Flow Build - Clicked", { stopNodeId });
};

// Hover no botão durante BUILDING
onMouseEnter={() => setIsHovered(true)}
// Muda ícone de Loader2 para Square (botão de parar)

// Atalho de teclado
useHotkeys(play, handlePlayWShortcut, { preventDefault: true });
```

#### 2. **BuildStatusDisplay Component**

**Localização:** `NodeStatus/components/build-status-display.tsx`

**Responsabilidade:** Renderizar conteúdo do tooltip

```typescript
const BuildStatusDisplay = ({
  buildStatus,
  validationStatus,
  validationString,
  lastRunTime,
}) => {
  // BUILDING → Mostra "Building..."
  if (buildStatus === BuildStatus.BUILDING) {
    return <StatusMessage>{STATUS_BUILDING}</StatusMessage>;
  }

  // INACTIVE → Mostra "Inactive"
  if (buildStatus === BuildStatus.INACTIVE) {
    return <StatusMessage>{STATUS_INACTIVE}</StatusMessage>;
  }

  // ERROR sem validationStatus → Campos obrigatórios faltando
  if (buildStatus === BuildStatus.ERROR && !validationStatus) {
    return <StatusMessage>{STATUS_MISSING_FIELDS_ERROR}</StatusMessage>;
  }

  // Ainda não buildou → Mostra "Build Component"
  if (!validationStatus) {
    return <StatusMessage>{STATUS_BUILD}</StatusMessage>;
  }

  // BUILT/VALID → Mostra detalhes completos
  return (
    <ValidationDetails
      validationString={validationString}
      lastRunTime={lastRunTime}
      validationStatus={validationStatus}
    />
  );
};
```

**ValidationDetails render:**

```typescript
<div className="max-h-100 px-1 py-2.5">
  <div className="flex max-h-80 flex-col gap-2">
    {/* Mensagem de validação */}
    {validationString && (
      <div className="break-words text-sm text-foreground">
        {validationString}
      </div>
    )}

    {/* Timestamp da última execução */}
    {lastRunTime && (
      <TimeStamp
        prefix="Last run at"
        time={lastRunTime}
      />
    )}

    {/* Duração da execução */}
    <Duration duration={validationStatus?.data.duration} />
  </div>
</div>
```

#### 3. **Hooks Customizados**

**use-icons-status.tsx:**
```typescript
const useIconStatus = (buildStatus: BuildStatus | undefined) => {
  const renderIconStatus = () => {
    if (buildStatus === BuildStatus.BUILDING) {
      return <></>;  // Sem ícone durante building
    }

    if (buildStatus === BuildStatus.ERROR) {
      return (
        <ForwardedIconComponent
          name="CircleAlert"
          className="h-4 w-4 text-destructive"
        />
      );
    }

    if (buildStatus === BuildStatus.INACTIVE) {
      return (
        <ForwardedIconComponent
          name="CircleOff"
          className="h-4 w-4 text-muted-foreground"
        />
      );
    }

    return null;
  };

  return renderIconStatus();
};
```

**use-get-build-status.ts:**
```typescript
// Hook que observa mudanças no flowBuildStatus
export const useBuildStatus = (data: NodeDataType, nodeId: string) => {
  return useFlowStore((state) => {
    // Lógica de agregação para flows aninhados
    // ... (já explicado anteriormente)
    return state.flowBuildStatus[nodeId]?.status;
  });
};
```

---

## Gerenciamento de Estado (Zustand Store)

### FlowStore Structure

**Arquivo:** `stores/flowStore.ts`

```typescript
interface FlowStoreType {
  // ============================================================
  // ESTADOS DE BUILD
  // ============================================================
  isBuilding: boolean;
  // Flag global indicando se há algum build em andamento

  flowBuildStatus: Record<string, {
    status: BuildStatus;
    timestamp?: string;
  }>;
  // Estado de build de cada componente

  verticesBuild: {
    verticesIds: string[];           // Todos os IDs
    verticesLayers: VertexLayerElementType[][];  // Camadas de execução
    runId?: string;                  // ID da execução
    verticesToRun: string[];         // Quais vão rodar
  } | null;
  // Estrutura de execução calculada pelo backend

  flowPool: Record<string, VertexBuildTypeAPI[]>;
  // Cache de resultados de builds

  buildController: AbortController;
  // Controller para cancelar builds

  buildInfo: {
    error?: string[];
    success?: boolean;
  } | null;
  // Informações sobre o último build

  // ============================================================
  // AÇÕES DE BUILD
  // ============================================================
  buildFlow: (params) => Promise<void>;
  // Inicia processo de build

  setIsBuilding: (isBuilding: boolean) => void;
  // Define flag global

  updateBuildStatus: (nodeIdList: string[], status: BuildStatus) => void;
  // Atualiza status de componentes

  updateVerticesBuild: (vertices) => void;
  // Atualiza estrutura de vértices

  addDataToFlowPool: (data: VertexBuildTypeAPI, nodeId: string) => void;
  // Adiciona resultado ao cache

  updateFlowPool: (nodeId: string, data: VertexBuildTypeAPI, buildId?: string) => void;
  // Atualiza resultado no cache

  revertBuiltStatusFromBuilding: () => void;
  // Reverte BUILDING → BUILT (usado em cancelamento)

  stopBuilding: () => void;
  // Para build em andamento

  // ============================================================
  // EDGES E ANIMAÇÕES
  // ============================================================
  updateEdgesRunningByNodes: (ids: string[], running: boolean) => void;
  // Anima edges durante execução

  clearEdgesRunningByNodes: () => Promise<void>;
  // Limpa animações

  // ... outros estados e ações
}
```

### Funções Principais

#### updateBuildStatus

```typescript
updateBuildStatus: (nodeIdList: string[], status: BuildStatus) => {
  const newFlowBuildStatus = { ...get().flowBuildStatus };

  nodeIdList.forEach((id) => {
    newFlowBuildStatus[id] = { status };

    if (status == BuildStatus.BUILT) {
      const timestamp_string = new Date(Date.now()).toLocaleString();
      newFlowBuildStatus[id].timestamp = timestamp_string;
    }
  });

  set({ flowBuildStatus: newFlowBuildStatus });
},
```

**Quando é chamado:**
- Quando backend envia evento `build_start` → `BUILDING`
- Quando backend envia evento `end_vertex` → `BUILT` ou `ERROR`
- Quando backend envia evento `build_end` → `BUILT`
- Quando validação falha → `ERROR`

#### updateEdgesRunningByNodes

```typescript
updateEdgesRunningByNodes: (ids: string[], running: boolean) => {
  const edges = get().edges;

  const newEdges = edges.map((edge) => {
    if (
      edge.data?.sourceHandle &&
      ids.includes(edge.data.sourceHandle.id ?? "")
    ) {
      edge.animated = running;  // Ativa/desativa animação
      edge.className = running ? "running" : "";
    } else {
      edge.animated = false;
      edge.className = "not-running";
    }
    return edge;
  });

  set({ edges: newEdges });
},
```

**CSS das animações:**
```css
/* Edges animadas */
.running {
  stroke: #10b981;  /* Verde */
  stroke-width: 2;
  animation: dashdraw 0.5s linear infinite;
}

@keyframes dashdraw {
  to {
    stroke-dashoffset: -10;
  }
}

/* Edges que já rodaram */
.ran {
  stroke: #6b7280;  /* Cinza */
}
```

#### stopBuilding

```typescript
stopBuilding: () => {
  get().buildController.abort();  // Cancela requisição

  // Para animação de todos os edges
  get().updateEdgesRunningByNodes(
    get().nodes.map(n => n.id),
    false
  );

  set({ isBuilding: false });

  // Reverte componentes BUILDING → BUILT
  get().revertBuiltStatusFromBuilding();

  // Mostra alerta
  useAlertStore.getState().setErrorData({
    title: "Build stopped",
  });
},
```

---

## Métodos de Entrega de Eventos

O Langflow suporta **3 métodos** diferentes para receber atualizações do backend:

### 1. DIRECT (Mais Rápido) ⚡

**Como funciona:**
- Stream direto do endpoint de build
- Sem etapa intermediária
- Usa Server-Sent Events (SSE)

**Fluxo:**
```
Frontend                    Backend
   │                           │
   ├─ POST /build/{id} ────────►
   │  event_delivery=direct    │
   │                           │
   │◄──── SSE event stream ─────┤
   │  event: build_start        │
   │  data: {...}               │
   │                           │
   │◄──── SSE event stream ─────┤
   │  event: end_vertex         │
   │  data: {...}               │
   │                           │
   │◄──── SSE event stream ─────┤
   │  event: end                │
   │                           │
```

**Código:**
```typescript
if (eventDelivery === EventDeliveryType.DIRECT) {
  return performStreamingRequest({
    method: "POST",
    url: buildUrl,  // /api/v1/build/{flowId}
    body: postData,
    onData: async (event) => {
      const type = event["event"];
      const data = event["data"];
      return await onEvent(type, data, ...);
    },
    buildController,
  });
}
```

**Vantagens:**
- ✅ Mais rápido (sem overhead)
- ✅ Conexão única
- ✅ Menos latência

**Desvantagens:**
- ❌ Requer suporte a SSE no servidor
- ❌ Pode ter problemas com proxies

---

### 2. STREAMING (Médio) 🌊

**Como funciona:**
- Processo em 2 etapas
- 1ª etapa: Inicia build e recebe `job_id`
- 2ª etapa: Conecta a endpoint de eventos via SSE

**Fluxo:**
```
Frontend                    Backend
   │                           │
   ├─ POST /build/{id} ────────►
   │  event_delivery=streaming │
   │                           │
   │◄──── { job_id: "abc" } ────┤
   │                           │
   ├─ GET /events/{job_id} ────►
   │                           │
   │◄──── SSE event stream ─────┤
   │  event: vertices_sorted    │
   │                           │
   │◄──── SSE event stream ─────┤
   │  event: build_start        │
   │                           │
   │◄──── SSE event stream ─────┤
   │  event: end_vertex         │
```

**Código:**
```typescript
// 1. Inicia build
const buildResponse = await fetch(buildUrl, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(postData),
});

const { job_id } = await buildResponse.json();

// 2. Conecta a eventos
const eventsUrl = `/api/v1/build/events/${job_id}`;

if (eventDelivery === EventDeliveryType.STREAMING) {
  return performStreamingRequest({
    method: "GET",
    url: eventsUrl,
    onData: async (event) => { ... },
  });
}
```

**Vantagens:**
- ✅ Funciona em mais cenários
- ✅ Job ID permite reconexão
- ✅ Suporte a cancelamento

**Desvantagens:**
- ⚠️ Overhead de 2 requisições
- ⚠️ Latência ligeiramente maior

---

### 3. POLLING (Mais Lento) 🐌

**Como funciona:**
- Frontend faz requisições GET repetidas
- Verifica novos eventos a cada intervalo
- Fallback quando SSE não funciona

**Fluxo:**
```
Frontend                    Backend
   │                           │
   ├─ POST /build/{id} ────────►
   │  event_delivery=polling   │
   │                           │
   │◄──── { job_id: "abc" } ────┤
   │                           │
   ├─ GET /events/{job_id} ────►
   │                           │
   │◄──── { events: [...] } ────┤
   │                           │
   │  (aguarda 3 segundos)      │
   │                           │
   ├─ GET /events/{job_id} ────►
   │                           │
   │◄──── { events: [...] } ────┤
```

**Código:**
```typescript
async function pollBuildEvents(
  url: string,
  buildResults: Array<boolean>,
  verticesStartTimeMs: Map<string, number>,
  callbacks: { ... },
  abortController: AbortController,
): Promise<void> {

  const POLL_INTERVAL = 3000;  // 3 segundos

  while (!abortController.signal.aborted) {
    const response = await fetch(url, {
      signal: abortController.signal,
    });

    const { events } = await response.json();

    for (const event of events) {
      const shouldContinue = await onEvent(
        event.type,
        event.data,
        buildResults,
        verticesStartTimeMs,
        callbacks,
      );

      if (!shouldContinue) break;
    }

    // Verifica se acabou
    if (events.some(e => e.type === "end")) {
      break;
    }

    // Aguarda próximo poll
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
  }
}
```

**Vantagens:**
- ✅ Funciona em QUALQUER servidor
- ✅ Não requer SSE
- ✅ Compatível com proxies antigos

**Desvantagens:**
- ❌ Mais lento (latência de até 3s)
- ❌ Mais requisições
- ❌ Maior uso de banda

---

### Fallback Automático

**Arquivo:** `buildUtils.ts:142-162`

```typescript
export async function buildFlowVerticesWithFallback(
  params: BuildVerticesParams,
) {
  try {
    // Tenta com o método configurado
    return await buildFlowVertices({ ...params });
  } catch (e: any) {
    // Se falhar por incompatibilidade com SSE
    if (
      e.message === POLLING_MESSAGES.ENDPOINT_NOT_AVAILABLE ||
      e.message === POLLING_MESSAGES.STREAMING_NOT_SUPPORTED
    ) {
      // Faz fallback para POLLING
      return await buildFlowVertices({
        ...params,
        eventDelivery: EventDeliveryType.POLLING,
      });
    }
    throw e;
  }
}
```

**Configuração:**
```typescript
// Usuário pode escolher em Settings
const eventDelivery = useUtilityStore(state => state.eventDelivery);

// Valores possíveis:
EventDeliveryType.DIRECT     // Padrão (mais rápido)
EventDeliveryType.STREAMING  // Alternativa
EventDeliveryType.POLLING    // Fallback
```

---

## Sistema de Visualização

### Classes CSS por Estado

**Arquivo:** `get-class-from-build-status.ts`

```typescript
export const getSpecificClassFromBuildStatus = (
  buildStatus: BuildStatus | undefined,
  validationStatus: VertexBuildTypeAPI | null,
  isBuilding: boolean,
) => {
  // Se está buildando globalmente e este componente está BUILDING
  if (isBuilding && buildStatus === BuildStatus.BUILDING) {
    return "border-medium-indigo ring-medium-indigo shadow-round-build-node";
    // Borda roxa animada
  }

  // Se buildou com sucesso
  if (buildStatus === BuildStatus.BUILT && validationStatus?.valid) {
    return "border-built shadow-round-green-node";
    // Borda verde
  }

  // Se tem erro
  if (
    buildStatus === BuildStatus.ERROR ||
    (validationStatus && !validationStatus.valid)
  ) {
    return "border-error shadow-round-error-node";
    // Borda vermelha
  }

  // Se está inativo
  if (buildStatus === BuildStatus.INACTIVE) {
    return "border-ring/50";
    // Borda cinza
  }

  // Padrão
  return "";
};
```

**CSS correspondente:**
```css
/* Componente buildando (roxo animado) */
.border-medium-indigo {
  border-color: #6366f1;
}

.shadow-round-build-node {
  box-shadow: 0 0 0 1px #6366f1,
              0 0 15px rgba(99, 102, 241, 0.5);
  animation: pulse-border 1.5s ease-in-out infinite;
}

@keyframes pulse-border {
  0%, 100% {
    box-shadow: 0 0 0 1px #6366f1, 0 0 15px rgba(99, 102, 241, 0.5);
  }
  50% {
    box-shadow: 0 0 0 2px #6366f1, 0 0 20px rgba(99, 102, 241, 0.7);
  }
}

/* Componente com sucesso (verde) */
.border-built {
  border-color: #10b981;
}

.shadow-round-green-node {
  box-shadow: 0 0 0 1px #10b981,
              0 0 10px rgba(16, 185, 129, 0.3);
}

/* Componente com erro (vermelho) */
.border-error {
  border-color: #ef4444;
}

.shadow-round-error-node {
  box-shadow: 0 0 0 1px #ef4444,
              0 0 10px rgba(239, 68, 68, 0.3);
}
```

### Ícones por Estado

```typescript
// BUILDING
<IconComponent
  name="Loader2"
  className="animate-spin text-muted-foreground"
/>

// ERROR
<IconComponent
  name="CircleAlert"
  className="text-destructive"
/>

// INACTIVE
<IconComponent
  name="CircleOff"
  className="text-muted-foreground"
/>

// BUILT (mostra duração)
<div className="text-accent-emerald-foreground">
  1.2s
</div>
```

### Tooltips Informativos

```typescript
<ShadTooltip
  styleClasses={cn(
    "border rounded-xl",
    conditionSuccess
      ? "border-accent-emerald-foreground bg-success-background"
      : "border-destructive bg-error-background",
  )}
  content={
    <BuildStatusDisplay
      buildStatus={buildStatus}
      validationStatus={validationStatus}
      validationString={validationString}
      lastRunTime={lastRunTime}
    />
  }
  side="bottom"
>
  {/* Conteúdo com hover */}
</ShadTooltip>
```

**Exemplos de tooltips:**

**BUILT:**
```
┌─────────────────────────────────────┐
│ ✅ Valid                            │
│                                     │
│ Last run at: 1/15/2024, 10:30:00 AM│
│ Duration: 1.2s                      │
└─────────────────────────────────────┘
```

**ERROR:**
```
┌─────────────────────────────────────┐
│ ❌ Error Building Component         │
│                                     │
│ • Missing required field: api_key   │
│ • Invalid format for input          │
└─────────────────────────────────────┘
```

**BUILDING:**
```
┌─────────────────────────────────────┐
│ 🔄 Building...                      │
└─────────────────────────────────────┘
```

---

## Animações e Feedback Visual

### 1. Animação do Botão Play

```typescript
// Hover transforma em botão de parar
const iconName =
  BuildStatus.BUILDING === buildStatus
    ? isHovered
      ? "Square"      // ⏹️ Botão de parar
      : "Loader2"     // ⌛ Loading
    : "Play";         // ▶️ Play

const iconClasses = cn(
  "h-3.5 w-3.5 transition-all",
  isHovered ? "text-foreground" : "text-muted-foreground",
  BuildStatus.BUILDING === buildStatus &&
    (isHovered ? "text-status-red" : "animate-spin"),
);
```

**Comportamento:**
- Normal: ▶️ Play (cinza)
- Hover: ▶️ Play (mais escuro)
- Building: ⌛ Loader2 (girando)
- Building + Hover: ⏹️ Square (vermelho) - para parar

### 2. Animação de Edges

```typescript
// Anima edges de componentes em execução
updateEdgesRunningByNodes: (ids: string[], running: boolean) => {
  const newEdges = edges.map((edge) => {
    if (ids.includes(edge.data.sourceHandle.id)) {
      edge.animated = running;
      edge.className = running ? "running" : "";
    }
    return edge;
  });
}
```

**CSS:**
```css
.running {
  stroke: #10b981;
  stroke-width: 2;
  stroke-dasharray: 5;
  animation: dashdraw 0.5s linear infinite;
}

@keyframes dashdraw {
  from {
    stroke-dashoffset: 0;
  }
  to {
    stroke-dashoffset: -10;
  }
}
```

**Resultado:**
- Edge fica verde
- Tracejado animado move-se continuamente
- Indica fluxo de dados

### 3. Animação de Borda do Componente

```css
/* Durante build */
.shadow-round-build-node {
  animation: pulse-border 1.5s ease-in-out infinite;
}

@keyframes pulse-border {
  0%, 100% {
    box-shadow: 0 0 0 1px #6366f1, 0 0 15px rgba(99, 102, 241, 0.5);
  }
  50% {
    box-shadow: 0 0 0 2px #6366f1, 0 0 20px rgba(99, 102, 241, 0.7);
  }
}
```

**Resultado:**
- Borda roxa "pulsa"
- Shadow cresce e diminui
- Chama atenção para componente em execução

### 4. Tempo Mínimo de Visualização

```typescript
const MIN_VISUAL_BUILD_TIME_MS = 300;

const startTimeMs = verticesStartTimeMs.get(buildData.id);
if (startTimeMs) {
  const delta = Date.now() - startTimeMs;
  if (delta < MIN_VISUAL_BUILD_TIME_MS) {
    await new Promise(resolve =>
      setTimeout(resolve, MIN_VISUAL_BUILD_TIME_MS - delta)
    );
  }
}
```

**Por quê?**
- Builds muito rápidos (<300ms) ficam invisíveis
- Usuário não percebe que algo aconteceu
- Delay artificial garante feedback visual

---

## Telemetria e Analytics

### Eventos Rastreados

**1. Flow Build Clicked:**
```typescript
track("Flow Build - Clicked", { stopNodeId: nodeId });
```

**2. Flow Build Completed:**
```typescript
trackFlowBuild(
  flowName,
  hasError: false,
  { flowId }
);
```

**3. Flow Build Error:**
```typescript
trackFlowBuild(
  flowName,
  hasError: true,
  { flowId, error: errorMessages }
);
```

**4. Data Loaded (AstraDB):**
```typescript
if (log.message.includes("Adding") && log.message.includes("documents")) {
  trackDataLoaded(
    flowId,
    flowName,
    "AstraDB Vector Store",
    vertexId
  );
}
```

### Estrutura dos Dados

```typescript
// Analytics payload
{
  event: "Flow Build - Clicked",
  properties: {
    stopNodeId: "ChatOutput-abc123",
    userId: "user-xyz",
    timestamp: 1705334400000,
    flowId: "550e8400-e29b-41d4-a716-446655440000",
    flowName: "My Chat Bot"
  }
}
```

---

## Casos de Uso Práticos

### Caso 1: Build de Componente Único

**Cenário:** Usuário clica Play em um ChatInput

```
1. Usuário clica ▶️ em ChatInput
   ↓
2. handleClickRun() é chamado
   ↓
3. buildFlow({ stopNodeId: "ChatInput-abc" })
   ↓
4. Backend valida upstream nodes
   ↓
5. vertices_sorted evento
   - Marca ChatInput como TO_BUILD
   ↓
6. build_start evento
   - Marca ChatInput como BUILDING
   - Ícone vira Loader2 (⌛)
   - Borda fica roxa animada
   ↓
7. end_vertex evento
   - Se sucesso: marca como BUILT
   - Mostra duração (ex: "0.5s")
   - Borda fica verde
   ↓
8. end evento
   - Define isBuilding = false
```

**Timeline:**
```
0ms    → Click
100ms  → Request enviado
150ms  → vertices_sorted recebido
200ms  → build_start recebido
500ms  → Componente executado
800ms  → end_vertex recebido (300ms delay visual mínimo)
850ms  → end recebido
```

### Caso 2: Build de Flow Completo

**Cenário:** Flow com 3 componentes: ChatInput → OpenAI → ChatOutput

```
1. Usuário clica ▶️ em ChatOutput (stopNodeId)
   ↓
2. Backend identifica upstream: [ChatInput, OpenAI, ChatOutput]
   ↓
3. vertices_sorted
   - IDs: ["ChatInput-a", "OpenAI-b", "ChatOutput-c"]
   - to_run: ["ChatInput-a", "OpenAI-b", "ChatOutput-c"]
   ↓
4. Execução sequencial:

   ┌─────────────────────┐
   │ ChatInput           │
   │ Status: BUILDING    │ ← build_start
   │ Ícone: ⌛          │
   └─────────────────────┘
           ↓ (2s)
   ┌─────────────────────┐
   │ ChatInput           │
   │ Status: BUILT ✅    │ ← end_vertex
   │ Duration: 2.0s      │
   └─────────────────────┘
           ↓
   Edge fica verde animado 🟢➜
           ↓
   ┌─────────────────────┐
   │ OpenAI              │
   │ Status: BUILDING    │ ← build_start
   │ Ícone: ⌛          │
   └─────────────────────┘
           ↓ (5s)
   ┌─────────────────────┐
   │ OpenAI              │
   │ Status: BUILT ✅    │ ← end_vertex
   │ Duration: 5.2s      │
   └─────────────────────┘
           ↓
   Edge fica verde animado 🟢➜
           ↓
   ┌─────────────────────┐
   │ ChatOutput          │
   │ Status: BUILDING    │ ← build_start
   │ Ícone: ⌛          │
   └─────────────────────┘
           ↓ (0.5s)
   ┌─────────────────────┐
   │ ChatOutput          │
   │ Status: BUILT ✅    │ ← end_vertex
   │ Duration: 0.5s      │
   └─────────────────────┘
           ↓
5. end evento
   - isBuilding = false
   - Todas as animações param
```

**Total:** ~8 segundos

### Caso 3: Build com Erro

**Cenário:** OpenAI sem API key

```
1. vertices_sorted
   - Define ordem
   ↓
2. ChatInput build_start
   ↓
3. ChatInput end_vertex (sucesso)
   ↓
4. OpenAI build_start
   ↓
5. OpenAI end_vertex (ERRO!)
   {
     valid: false,
     data: {
       outputs: {
         result: [{
           message: {
             type: "error",
             errorMessage: "Missing required field: api_key"
           }
         }]
       }
     }
   }
   ↓
6. onBuildError é chamado
   - Modal de erro aparece
   - Título: "Error Building Component"
   - Lista: ["Missing required field: api_key"]
   ↓
7. updateBuildStatus(["OpenAI-b"], BuildStatus.ERROR)
   - Borda vermelha
   - Ícone ⚠️
   ↓
8. Build para (não continua para ChatOutput)
   ↓
9. end evento
   - isBuilding = false
```

**UI Result:**
```
┌─────────────────────┐
│ ChatInput           │
│ ✅ 2.0s             │
└─────────────────────┘
         ↓
┌─────────────────────┐
│ OpenAI              │
│ ⚠️ Error            │  ← Vermelho
└─────────────────────┘
         ↓
┌─────────────────────┐
│ ChatOutput          │
│ (não executou)      │
└─────────────────────┘
```

### Caso 4: Cancelamento de Build

**Cenário:** Usuário para build no meio

```
1. Build em andamento
   - OpenAI está BUILDING
   ↓
2. Usuário hover no botão Play
   - Ícone muda para ⏹️ (Square)
   - Fica vermelho
   ↓
3. Usuário clica
   ↓
4. stopBuilding() é chamado
   ↓
5. buildController.abort()
   - Cancela requisição HTTP
   - Backend para execução
   ↓
6. updateEdgesRunningByNodes(allIds, false)
   - Remove animações
   ↓
7. revertBuiltStatusFromBuilding()
   - Componentes BUILDING → BUILT
   ↓
8. Alert: "Build stopped"
   ↓
9. isBuilding = false
```

---

## Erros Comuns e Como São Tratados

### 1. Campos Obrigatórios Faltando

**Erro:**
```
Missing required field: api_key
```

**Detecção:**
```typescript
// Durante validação antes do build
const errorsObjs = validateNodes(nodesToValidate, edges);

// Cada node retorna:
{
  id: "OpenAI-abc",
  errors: ["Missing required field: api_key"]
}
```

**Tratamento:**
```typescript
if (errors.length > 0) {
  setErrorData({
    title: MISSED_ERROR_ALERT,
    list: errors,
  });
  get().updateBuildStatus(ids, BuildStatus.ERROR);
  get().setIsBuilding(false);
  throw new Error("Invalid components");
}
```

**UI:**
- ❌ Modal de erro aparece
- ❌ Componente fica com borda vermelha
- ❌ Tooltip mostra "Missing Required Fields"
- ❌ Build não inicia

### 2. Erro Durante Execução

**Erro:**
```
OpenAI API error: Invalid API key
```

**Detecção:**
```typescript
// Backend retorna end_vertex com valid: false
{
  valid: false,
  data: {
    outputs: {
      result: [{
        message: {
          type: "error",
          errorMessage: "OpenAI API error: Invalid API key"
        }
      }]
    }
  }
}
```

**Tratamento:**
```typescript
if (!buildData.valid) {
  const errorMessages = Object.keys(buildData.data.outputs).flatMap(key => {
    return outputs
      .filter(log => isErrorLogType(log.message))
      .map(log => log.message.errorMessage);
  });

  onBuildError("Error Building Component", errorMessages, [{ id }]);
  onBuildUpdate(buildData, BuildStatus.ERROR, "");
  buildResults.push(false);
  return false;
}
```

**UI:**
- ❌ Modal de erro aparece
- ❌ Componente fica com borda vermelha
- ❌ Ícone ⚠️ aparece
- ❌ Tooltip mostra mensagem de erro
- ❌ Build para (não continua)

### 3. Timeout de Rede

**Erro:**
```
Network timeout
```

**Detecção:**
```typescript
onNetworkError: (error: Error) => {
  if (error.name === "AbortError") {
    onBuildStopped && onBuildStopped();
    return;
  }
  onBuildError("Error Building Component", [
    "Network error. Please check the connection to the server.",
  ]);
}
```

**Tratamento:**
```typescript
// API interceptor detecta timeout
api.interceptors.response.use(
  response => response,
  async (error) => {
    if (error.code === 'ECONNABORTED') {
      // Timeout!
    }
    // ...
  }
);
```

**UI:**
- ⚠️ Alert: "Network error. Please check the connection..."
- ⚠️ Componentes BUILDING ficam BUILT
- ⚠️ isBuilding = false

### 4. Backend Crash (500 Error)

**Erro:**
```
500 Internal Server Error
```

**Detecção:**
```typescript
async function clearBuildVerticesState(error) {
  if (error?.response?.status === 500) {
    const vertices = useFlowStore.getState().verticesBuild;
    useFlowStore
      .getState()
      .updateBuildStatus(vertices?.verticesIds ?? [], BuildStatus.BUILT);
    useFlowStore.getState().setIsBuilding(false);
  }
}
```

**Tratamento:**
- Reverte todos para BUILT
- Define isBuilding = false
- Permite tentar novamente

---

## Performance e Otimizações

### 1. Tempo Mínimo Visual

**Problema:** Builds instantâneos são invisíveis

**Solução:**
```typescript
const MIN_VISUAL_BUILD_TIME_MS = 300;

if (delta < MIN_VISUAL_BUILD_TIME_MS) {
  await new Promise(resolve =>
    setTimeout(resolve, MIN_VISUAL_BUILD_TIME_MS - delta)
  );
}
```

### 2. Debounce de Tokens

**Problema:** Streaming de tokens muito rápido causa re-renders excessivos

**Solução:**
```typescript
setTimeout(() => {
  flushSync(() => {
    useMessagesStore.getState().updateMessageText(data.id, data.chunk);
  });
}, 10);
```

### 3. Zustand Selectors

**Problema:** Re-render de todos os componentes quando um muda

**Solução:**
```typescript
// ❌ Ruim: subscreve ao store inteiro
const flowStore = useFlowStore();

// ✅ Bom: subscreve apenas ao buildStatus
const buildStatus = useFlowStore(state =>
  state.flowBuildStatus[nodeId]?.status
);
```

### 4. Memo de Ícones

**Problema:** Re-render de ícones a cada mudança

**Solução:**
```typescript
const iconStatus = useIconStatus(buildStatus);
// Memo interno no hook
```

### 5. FlushSync para Atualizações Críticas

**Problema:** React batching pode atrasar atualizações importantes

**Solução:**
```typescript
flushSync(() => {
  useMessagesStore.getState().updateMessageText(id, chunk);
});
```

### 6. AbortController para Cancelamento

**Problema:** Requisições continuam após cancelamento

**Solução:**
```typescript
const buildController = new AbortController();

// Cancela todas as requisições pendentes
buildController.abort();
```

---

## Conclusão

O sistema de build do Langflow é uma máquina de estados complexa e bem orquestrada que:

✅ **Gerencia** 5 estados diferentes de build
✅ **Coordena** múltiplos componentes executando em sequência
✅ **Anima** feedback visual em tempo real
✅ **Trata** erros graciosamente
✅ **Suporta** 3 métodos de entrega de eventos
✅ **Otimiza** performance com memoization e selectors
✅ **Rastreia** analytics para melhorias
✅ **Permite** cancelamento a qualquer momento

### Arquitetura em Resumo

```
┌─────────────────────────────────────────────────────────────────┐
│                         SISTEMA DE BUILD                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  UI Layer (React)                                              │
│  ├─ NodeStatus Component                                       │
│  ├─ BuildStatusDisplay                                         │
│  └─ Hooks (useBuildStatus, useIconStatus)                     │
│                          ↕                                      │
│  State Management (Zustand)                                    │
│  ├─ flowBuildStatus: { [nodeId]: { status, timestamp } }     │
│  ├─ isBuilding: boolean                                       │
│  ├─ verticesBuild: { ids, layers, runId }                   │
│  └─ Actions: buildFlow, updateBuildStatus, stopBuilding      │
│                          ↕                                      │
│  Build Logic (buildUtils.ts)                                  │
│  ├─ buildFlowVertices()                                       │
│  ├─ onEvent() → Processa eventos do backend                  │
│  └─ updateVerticesOrder()                                     │
│                          ↕                                      │
│  Event Delivery                                                │
│  ├─ DIRECT    (fastest)                                       │
│  ├─ STREAMING (medium)                                        │
│  └─ POLLING   (fallback)                                      │
│                          ↕                                      │
│  Backend API                                                   │
│  └─ POST /api/v1/build/{flowId}                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

Este documento cobre **TUDO** sobre como o sistema de build funciona no Langflow, desde o click do usuário até a atualização visual final.
