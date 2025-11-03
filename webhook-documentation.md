# Documentação Completa do Sistema de Webhook do Langflow

## Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Componente Webhook (LFX)](#componente-webhook-lfx)
4. [Backend API](#backend-api)
5. [Frontend (Interface)](#frontend-interface)
6. [Fluxo de Execução Completo](#fluxo-de-execução-completo)
7. [Sistema de Autenticação](#sistema-de-autenticação)
8. [Estruturas de Dados](#estruturas-de-dados)
9. [Exemplos de Uso](#exemplos-de-uso)
10. [Detalhes de Implementação](#detalhes-de-implementação)

---

## Visão Geral

O sistema de webhook do Langflow permite que flows sejam executados através de chamadas HTTP POST externas, possibilitando integração com sistemas externos. O webhook recebe dados via HTTP, processa-os através do flow e executa a tarefa em background.

### Características Principais

- **Execução Assíncrona**: Webhooks são executados em background usando FastAPI BackgroundTasks
- **Autenticação Opcional**: Suporta autenticação via API key (configurável)
- **Payload Flexível**: Aceita qualquer JSON como payload
- **Componente Dedicado**: Possui um componente específico (WebhookComponent) que recebe os dados
- **Geração Automática de cURL**: O frontend gera automaticamente comandos cURL para facilitar testes

---

## Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                      EXTERNAL SYSTEM                        │
│                   (HTTP POST Request)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    LANGFLOW BACKEND                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │  /api/v1/webhook/{flow_id_or_name}                 │    │
│  │  (endpoints.py:501)                                │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  get_webhook_user()                                │    │
│  │  - Valida autenticação se WEBHOOK_AUTH_ENABLE=true │    │
│  │  - Retorna flow owner se desabilitado              │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  get_all_webhook_components_in_flow()              │    │
│  │  - Busca todos componentes Webhook no flow         │    │
│  │  - Cria tweaks para injetar payload                │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                              │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  simple_run_flow_task()                            │    │
│  │  - Executa em BackgroundTask                       │    │
│  │  - Logs telemetria                                 │    │
│  └────────────┬───────────────────────────────────────┘    │
└───────────────┼──────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                    FLOW EXECUTION                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │  WebhookComponent.build_data()                     │    │
│  │  - Recebe payload via tweak "data"                 │    │
│  │  - Parse JSON                                      │    │
│  │  - Retorna Data object                             │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Componente Webhook (LFX)

### Localização
`src/lfx/src/lfx/components/data/webhook.py`

### Implementação Completa

```python
class WebhookComponent(Component):
    display_name = "Webhook"
    documentation: str = "https://docs.langflow.org/components-data#webhook"
    name = "Webhook"
    icon = "webhook"

    inputs = [
        MultilineInput(
            name="data",
            display_name="Payload",
            info="Receives a payload from external systems via HTTP POST.",
            advanced=True,
        ),
        MultilineInput(
            name="curl",
            display_name="cURL",
            value="CURL_WEBHOOK",  # Placeholder substituído pelo frontend
            advanced=True,
            input_types=[],
        ),
        MultilineInput(
            name="endpoint",
            display_name="Endpoint",
            value="BACKEND_URL",  # Placeholder substituído pelo frontend
            advanced=False,
            copy_field=True,
            input_types=[],
        ),
    ]
    outputs = [
        Output(display_name="Data", name="output_data", method="build_data"),
    ]

    def build_data(self) -> Data:
        """
        Processa o payload recebido do webhook.

        Comportamento:
        1. Se não há dados, retorna Data vazio
        2. Tenta fazer parse do JSON
        3. Se falhar o parse, encapsula em {"payload": raw_data}
        4. Retorna Data object com o payload processado
        """
        message: str | Data = ""
        if not self.data:
            self.status = "No data provided."
            return Data(data={})

        try:
            # Remove quebras de linha escapadas do JSON
            my_data = self.data.replace('"\n"', '"\\n"')
            body = json.loads(my_data or "{}")
        except json.JSONDecodeError:
            # Se não for JSON válido, encapsula como payload
            body = {"payload": self.data}
            message = f"Invalid JSON payload. Please check the format.\n\n{self.data}"

        data = Data(data=body)
        if not message:
            message = data
        self.status = message
        return data
```

### Campos do Componente

1. **data** (Payload):
   - Tipo: MultilineInput
   - Recebe o payload do webhook via tweak
   - Advanced: true (não aparece por padrão na UI)
   - Preenchido automaticamente pelo endpoint

2. **curl** (cURL Command):
   - Tipo: MultilineInput
   - Value default: "CURL_WEBHOOK"
   - Substituído pelo frontend com comando cURL completo
   - Read-only no frontend
   - Advanced: true

3. **endpoint** (Endpoint URL):
   - Tipo: MultilineInput
   - Value default: "BACKEND_URL"
   - Substituído pelo frontend com URL real
   - Copy-enabled (botão de copiar)
   - Advanced: false (visível por padrão)

---

## Backend API

### Endpoint Principal: `POST /api/v1/webhook/{flow_id_or_name}`

**Localização**: `src/backend/base/langflow/api/v1/endpoints.py:501`

### Implementação Detalhada

```python
@router.post("/webhook/{flow_id_or_name}", response_model=dict, status_code=HTTPStatus.ACCEPTED)
async def webhook_run_flow(
    flow_id_or_name: str,
    flow: Annotated[Flow, Depends(get_flow_by_id_or_endpoint_name)],
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Executa um flow via webhook.

    Args:
        flow_id_or_name: UUID ou endpoint_name do flow
        flow: Flow carregado (dependency injection)
        request: Request HTTP
        background_tasks: Gerenciador de tarefas assíncronas

    Returns:
        dict: {"message": "Task started in the background", "status": "in progress"}

    Status Code: 202 ACCEPTED (task assíncrona iniciada)
    """
```

### Fluxo de Execução do Endpoint

#### 1. Autenticação
```python
# Determina o usuário baseado na config de autenticação
webhook_user = await get_webhook_user(flow_id_or_name, request)

# Localização: src/backend/base/langflow/services/auth/utils.py:263
async def get_webhook_user(flow_id: str, request: Request) -> UserRead:
    settings_service = get_settings_service()

    if not settings_service.auth_settings.WEBHOOK_AUTH_ENABLE:
        # Modo sem autenticação: usa o dono do flow
        flow_owner = await get_user_by_flow_id_or_endpoint_name(flow_id)
        if flow_owner is None:
            raise HTTPException(status_code=404, detail="Flow not found")
        return flow_owner

    # Modo com autenticação: valida API key
    api_key = request.headers.get("x-api-key") or request.query_params.get("x-api-key")

    if not api_key:
        raise HTTPException(
            status_code=403,
            detail="API key required when webhook authentication is enabled"
        )

    # Valida API key
    async with get_db_service().with_session() as db:
        result = await check_key(db, api_key)
        if not result:
            raise HTTPException(status_code=403, detail="Invalid API key")

        authenticated_user = UserRead.model_validate(result, from_attributes=True)

    # Verifica ownership do flow
    flow_owner = await get_user_by_flow_id_or_endpoint_name(flow_id)
    if flow_owner.id != authenticated_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only execute webhooks for flows you own"
        )

    return authenticated_user
```

#### 2. Extração do Payload
```python
try:
    data = await request.body()
except Exception as exc:
    raise HTTPException(status_code=500, detail=str(exc))

if not data:
    raise HTTPException(
        status_code=400,
        detail="Request body is empty. You should provide a JSON payload containing the flow ID."
    )
```

#### 3. Identificação de Componentes Webhook
```python
# Localização: src/backend/base/langflow/services/database/models/flow/utils.py:15
def get_all_webhook_components_in_flow(flow_data: dict | None):
    """
    Busca todos os componentes Webhook no flow.

    Um componente é identificado como webhook se seu ID contém "Webhook".

    Returns:
        list[dict]: Lista de nodes que são componentes Webhook
    """
    if not flow_data:
        return []
    return [node for node in flow_data.get("nodes", []) if "Webhook" in node.get("id")]
```

#### 4. Criação de Tweaks
```python
# Busca todos componentes webhook no flow
webhook_components = get_all_webhook_components_in_flow(flow.data)
tweaks = {}

# Injeta o payload em todos os componentes webhook
for component in webhook_components:
    tweaks[component["id"]] = {
        "data": data.decode() if isinstance(data, bytes) else data
    }
```

#### 5. Criação do Request Simplificado
```python
input_request = SimplifiedAPIRequest(
    input_value="",           # Vazio para webhooks
    input_type="chat",        # Tipo padrão
    output_type="chat",       # Tipo padrão
    tweaks=tweaks,            # Contém o payload injetado
    session_id=None,          # Sem sessão para webhooks
)
```

#### 6. Execução em Background
```python
run_id = str(uuid4())
background_tasks.add_task(
    simple_run_flow_task,
    flow=flow,
    input_request=input_request,
    api_key_user=webhook_user,
    telemetry_service=telemetry_service,
    start_time=start_time,
    run_id=run_id,
)

return {"message": "Task started in the background", "status": "in progress"}
```

### Função de Execução em Background

```python
async def simple_run_flow_task(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    stream: bool = False,
    api_key_user: User | None = None,
    event_manager: EventManager | None = None,
    telemetry_service=None,
    start_time: float | None = None,
    run_id: str | None = None,
):
    """
    Executa o flow como BackgroundTask.

    Características:
    - Não levanta exceções (para não quebrar o background task)
    - Registra telemetria de sucesso/falha
    - Logs de erro via logger
    """
    try:
        result = await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=stream,
            api_key_user=api_key_user,
            event_manager=event_manager,
            run_id=run_id,
        )

        # Telemetria de sucesso
        if telemetry_service and start_time is not None:
            await telemetry_service.log_package_run(
                RunPayload(
                    run_is_webhook=True,
                    run_seconds=int(time.perf_counter() - start_time),
                    run_success=True,
                    run_error_message="",
                    run_id=run_id,
                )
            )
        return result

    except Exception as exc:
        await logger.aexception(f"Error running flow {flow.id} task")

        # Telemetria de erro
        if telemetry_service and start_time is not None:
            await telemetry_service.log_package_run(
                RunPayload(
                    run_is_webhook=True,
                    run_seconds=int(time.perf_counter() - start_time),
                    run_success=False,
                    run_error_message=str(exc),
                    run_id=run_id,
                )
            )
        return None
```

---

## Frontend (Interface)

### Componentes React

#### 1. WebhookFieldComponent

**Localização**: `src/frontend/src/components/core/parameterRenderComponent/components/webhookFieldComponent/index.tsx`

```typescript
export default function WebhookFieldComponent({
  value,
  handleOnNewValue,
  editNode = false,
  id = "",
  nodeInformationMetadata,
  ...baseInputProps
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  const { userData } = useContext(AuthContext);
  const [userId, setUserId] = useState("");
  const { mutate: getBuildsMutation } = useGetBuildsMutation();
  const hasInitialized = useRef(false);
  const modalProps = getModalPropsApiKey();

  // Identifica qual campo está sendo renderizado
  const isBackendUrl = nodeInformationMetadata?.variableName === "endpoint";
  const isCurlWebhook = nodeInformationMetadata?.variableName === "curl";
  const isAuth = nodeInformationMetadata?.isAuth;

  // Mostra botão de gerar token apenas para endpoint URL
  const showGenerateToken = (isBackendUrl && !editNode && !isAuth) ||
                            (ENABLE_DATASTAX_LANGFLOW && !editNode);

  // Força build do flow quando o componente é montado
  useEffect(() => {
    const getBuilds = (!editNode && isBackendUrl && !hasInitialized.current) ||
                      (ENABLE_DATASTAX_LANGFLOW && !editNode);

    if (getBuilds) {
      hasInitialized.current = true;
      getBuildsMutation({
        flowId: nodeInformationMetadata?.flowId!,
      });
    }
  }, []);

  return (
    <div className="grid w-full gap-2">
      {/* Campo Endpoint URL */}
      {isBackendUrl && (
        <div>
          <CopyFieldAreaComponent
            id={id}
            value={value}
            editNode={editNode}
            handleOnNewValue={handleOnNewValue}
            {...baseInputProps}
          />
        </div>
      )}

      {/* Campo cURL */}
      {isCurlWebhook && (
        <div>
          <TextAreaComponent
            id={id}
            value={value}
            editNode={editNode}
            handleOnNewValue={handleOnNewValue}
            {...baseInputProps}
            nodeInformationMetadata={nodeInformationMetadata}
          />
        </div>
      )}

      {/* Botão para gerar API Key */}
      {showGenerateToken && (
        <div>
          <SecretKeyModalButton userId={userId} modalProps={modalProps} />
        </div>
      )}
    </div>
  );
}
```

#### 2. CopyFieldAreaComponent (Endpoint URL)

**Localização**: `src/frontend/src/components/core/parameterRenderComponent/components/copyFieldAreaComponent/index.tsx`

```typescript
const BACKEND_URL = "BACKEND_URL";
const { protocol, host } = customGetHostProtocol();
const URL_WEBHOOK = `${protocol}//${host}/api/v1/webhook/`;

export default function CopyFieldAreaComponent({
  value,
  handleOnNewValue,
  editNode = false,
  id = "",
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const endpointName = currentFlow?.endpoint_name ?? currentFlow?.id ?? "";

  // Substitui BACKEND_URL pelo URL real
  const valueToRender = useMemo(() => {
    if (value === BACKEND_URL) {
      return `${URL_WEBHOOK}${endpointName}`;
    }
    return value;
  }, [value, endpointName]);

  const handleCopy = (event?: React.MouseEvent<HTMLDivElement>) => {
    navigator.clipboard.writeText(valueToRender);
    setSuccessData({ title: "Endpoint URL copied" });
    event?.stopPropagation();
  };

  return (
    <div className="w-full">
      <Input
        value={valueToRender}
        disabled
        // ... props
      />
      <IconComponent
        name={isCopied ? "Check" : "Copy"}
        onClick={handleCopy}
      />
    </div>
  );
}
```

#### 3. TextAreaComponent (cURL Command)

**Localização**: `src/frontend/src/components/core/parameterRenderComponent/components/textAreaComponent/index.tsx`

```typescript
const WEBHOOK_VALUE = "CURL_WEBHOOK";

export default function TextAreaComponent({
  value,
  nodeInformationMetadata,
  // ... props
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  const webhookAuthEnable = useUtilityStore((state) => state.webhookAuthEnable);

  const isWebhook = useMemo(
    () => nodeInformationMetadata?.nodeType === "webhook",
    [nodeInformationMetadata?.nodeType],
  );

  // Substitui CURL_WEBHOOK pelo comando cURL real
  useEffect(() => {
    if (isWebhook && value === WEBHOOK_VALUE) {
      const curlWebhookCode = getCurlWebhookCode({
        flowId: nodeInformationMetadata?.flowId!,
        webhookAuthEnable,
        flowName: nodeInformationMetadata?.flowName!,
        format: "singleline",
      });
      handleOnNewValue({ value: curlWebhookCode });
    }
  }, [isWebhook, value, nodeInformationMetadata, webhookAuthEnable]);

  const changeWebhookFormat = (format: "multiline" | "singleline") => {
    if (isWebhook) {
      const curlWebhookCode = getCurlWebhookCode({
        flowId: nodeInformationMetadata?.flowId!,
        webhookAuthEnable,
        flowName: nodeInformationMetadata?.flowName!,
        format,
      });
      handleOnNewValue({ value: curlWebhookCode });
    }
  };

  return (
    <div className="w-full">
      <Input
        value={value}
        readOnly={isWebhook}  // Read-only para webhooks
        // ... props
      />
      {/* Modal para exibir cURL em formato multilinha */}
      <ComponentTextModal
        value={value}
        onCloseModal={() => changeWebhookFormat("singleline")}
      >
        <div onClick={() => changeWebhookFormat("multiline")}>
          <IconComponent name="Scan" />
        </div>
      </ComponentTextModal>
    </div>
  );
}
```

### Geração de Comando cURL

**Localização**: `src/frontend/src/modals/apiModal/utils/get-curl-code.tsx`

```typescript
export function getCurlWebhookCode({
  flowId,
  webhookAuthEnable,
  endpointName,
  format = "multiline",
}: {
  flowId: string;
  webhookAuthEnable: boolean;
  endpointName?: string;
  format?: "multiline" | "singleline";
}) {
  const { protocol, host } = customGetHostProtocol();
  const baseUrl = `${protocol}//${host}/api/v1/webhook/${endpointName || flowId}`;

  const authHeader = webhookAuthEnable
    ? `-H 'x-api-key: <your api key>'`
    : "";

  if (format === "singleline") {
    return `curl -X POST "${baseUrl}" -H 'Content-Type: application/json' ${authHeader} -d '{"any": "data"}'`.trim();
  }

  // Formato multilinha
  return `curl -X POST \\
  "${baseUrl}" \\
  -H 'Content-Type: application/json' \\${
    webhookAuthEnable ? `\n  -H 'x-api-key: <your api key>' \\` : ""
  }${
    ENABLE_DATASTAX_LANGFLOW
      ? `\n  -H 'Authorization: Bearer <YOUR_APPLICATION_TOKEN>' \\`
      : ""
  }
  -d '{"any": "data"}'
  `.trim();
}
```

---

## Fluxo de Execução Completo

### Diagrama de Sequência

```
┌─────────┐        ┌──────────┐        ┌──────────┐        ┌─────────┐
│External │        │ Backend  │        │  Flow    │        │Webhook  │
│ System  │        │  API     │        │ Executor │        │Component│
└────┬────┘        └────┬─────┘        └────┬─────┘        └────┬────┘
     │                  │                   │                    │
     │ POST /webhook/   │                   │                    │
     │ {payload}        │                   │                    │
     ├─────────────────>│                   │                    │
     │                  │                   │                    │
     │                  │ get_webhook_user()│                    │
     │                  │ (auth check)      │                    │
     │                  │                   │                    │
     │                  │ get_all_webhook_  │                    │
     │                  │ components()      │                    │
     │                  │                   │                    │
     │  202 ACCEPTED    │                   │                    │
     │  (background)    │                   │                    │
     │<─────────────────┤                   │                    │
     │                  │                   │                    │
     │                  │ BackgroundTask    │                    │
     │                  │ simple_run_flow() │                    │
     │                  ├──────────────────>│                    │
     │                  │                   │                    │
     │                  │                   │ build_data()       │
     │                  │                   │ (with tweaks)      │
     │                  │                   ├───────────────────>│
     │                  │                   │                    │
     │                  │                   │   Data object      │
     │                  │                   │<───────────────────┤
     │                  │                   │                    │
     │                  │                   │ (continue flow     │
     │                  │                   │  execution)        │
     │                  │                   │                    │
     │                  │ log_telemetry()   │                    │
     │                  │<──────────────────┤                    │
     │                  │                   │                    │
```

### Passo a Passo Detalhado

1. **Sistema Externo Envia Request**
   ```bash
   curl -X POST "https://langflow.com/api/v1/webhook/my-flow" \
     -H "Content-Type: application/json" \
     -H "x-api-key: sk-xxx" \
     -d '{"message": "hello", "user_id": 123}'
   ```

2. **Backend Recebe Request**
   - Endpoint: `/api/v1/webhook/{flow_id_or_name}`
   - Status: 202 ACCEPTED (resposta imediata)

3. **Autenticação**
   - Se `WEBHOOK_AUTH_ENABLE=false`: usa dono do flow
   - Se `WEBHOOK_AUTH_ENABLE=true`: valida API key e ownership

4. **Preparação do Payload**
   ```python
   # Busca componentes webhook
   webhook_components = [
       {
           "id": "Webhook-abc123",
           "data": {...}
       }
   ]

   # Cria tweaks
   tweaks = {
       "Webhook-abc123": {
           "data": '{"message": "hello", "user_id": 123}'
       }
   }
   ```

5. **Criação do Request Interno**
   ```python
   input_request = SimplifiedAPIRequest(
       input_value="",
       input_type="chat",
       output_type="chat",
       tweaks=tweaks,
       session_id=None,
   )
   ```

6. **Execução em Background**
   - Task assíncrona iniciada
   - Response imediato ao cliente
   - Execução real acontece após o response

7. **Processamento no Flow**
   - Graph é construído do flow.data
   - Tweaks são aplicados
   - Componente Webhook recebe o payload via tweak

8. **WebhookComponent.build_data()**
   ```python
   # self.data contém o payload injetado
   data = {"message": "hello", "user_id": 123}

   # Parse e retorna Data object
   return Data(data=data)
   ```

9. **Continuação do Flow**
   - Data object é passado para próximos componentes
   - Flow executa normalmente

10. **Telemetria e Logging**
    - Registra sucesso/falha
    - Tempo de execução
    - Run ID para tracking

---

## Sistema de Autenticação

### Configuração

A autenticação de webhooks é controlada pela variável de ambiente:

```bash
WEBHOOK_AUTH_ENABLE=true   # Requer API key
WEBHOOK_AUTH_ENABLE=false  # Sem autenticação (usa dono do flow)
```

### Modo Sem Autenticação (WEBHOOK_AUTH_ENABLE=false)

```python
async def get_webhook_user(flow_id: str, request: Request) -> UserRead:
    settings_service = get_settings_service()

    if not settings_service.auth_settings.WEBHOOK_AUTH_ENABLE:
        # Busca o dono do flow
        flow_owner = await get_user_by_flow_id_or_endpoint_name(flow_id)
        if flow_owner is None:
            raise HTTPException(status_code=404, detail="Flow not found")
        return flow_owner  # Executa como dono do flow
```

**Comportamento:**
- Não requer API key
- Executa webhook como o usuário dono do flow
- Qualquer pessoa pode chamar o webhook
- Útil para webhooks públicos ou ambientes internos seguros

**Exemplo de chamada:**
```bash
curl -X POST "https://langflow.com/api/v1/webhook/my-flow" \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

### Modo Com Autenticação (WEBHOOK_AUTH_ENABLE=true)

```python
async def get_webhook_user(flow_id: str, request: Request) -> UserRead:
    # ... código anterior ...

    # Extrai API key
    api_key = request.headers.get("x-api-key") or request.query_params.get("x-api-key")

    if not api_key:
        raise HTTPException(
            status_code=403,
            detail="API key required when webhook authentication is enabled"
        )

    # Valida API key
    async with get_db_service().with_session() as db:
        result = await check_key(db, api_key)
        if not result:
            raise HTTPException(status_code=403, detail="Invalid API key")

        authenticated_user = UserRead.model_validate(result, from_attributes=True)

    # Verifica ownership
    flow_owner = await get_user_by_flow_id_or_endpoint_name(flow_id)
    if flow_owner.id != authenticated_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only execute webhooks for flows you own"
        )

    return authenticated_user
```

**Comportamento:**
- Requer API key válida (header ou query param)
- Valida que a API key pertence ao dono do flow
- Nega acesso se API key for de outro usuário
- Mais seguro para ambientes produção

**Exemplo de chamada (header):**
```bash
curl -X POST "https://langflow.com/api/v1/webhook/my-flow" \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-lf-xxx" \
  -d '{"message": "hello"}'
```

**Exemplo de chamada (query param):**
```bash
curl -X POST "https://langflow.com/api/v1/webhook/my-flow?x-api-key=sk-lf-xxx" \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

### Validação de Ownership

O sistema garante que:
1. API key seja válida
2. API key pertença ao dono do flow
3. Usuário só pode executar webhooks dos próprios flows

```python
# Fluxo de validação
flow_owner = await get_user_by_flow_id_or_endpoint_name(flow_id)
if flow_owner.id != authenticated_user.id:
    raise HTTPException(
        status_code=403,
        detail="Access denied: You can only execute webhooks for flows you own"
    )
```

---

## Estruturas de Dados

### SimplifiedAPIRequest

**Localização**: `src/backend/base/langflow/api/v1/schemas.py:338`

```python
class SimplifiedAPIRequest(BaseModel):
    input_value: str | None = Field(
        default=None,
        description="The input value"
    )
    input_type: InputType | None = Field(
        default="chat",
        description="The input type"
    )
    output_type: OutputType | None = Field(
        default="chat",
        description="The output type"
    )
    output_component: str | None = Field(
        default="",
        description="If there are multiple output components, you can specify which one."
    )
    tweaks: Tweaks | None = Field(
        default=None,
        description="The tweaks"
    )
    session_id: str | None = Field(
        default=None,
        description="The session id"
    )
```

**Uso no Webhook:**
```python
input_request = SimplifiedAPIRequest(
    input_value="",           # Vazio para webhooks
    input_type="chat",
    output_type="chat",
    tweaks={
        "Webhook-abc123": {"data": '{"message": "hello"}'}
    },
    session_id=None,
)
```

### Tweaks Structure

**Definição**: `langflow.schema.graph.Tweaks`

```python
# Type alias
Tweaks = dict[str, dict[str, Any]]

# Exemplo para webhook
tweaks = {
    "Webhook-abc123": {        # ID do componente Webhook
        "data": '{"user": "john", "action": "login"}'  # Payload como string
    },
    "ChatInput-xyz789": {      # Outros componentes também podem ter tweaks
        "input_value": "Hello"
    }
}
```

### Data Object (LFX)

**Localização**: `lfx.schema.data`

```python
from lfx.schema.data import Data

# Retorno do WebhookComponent
data = Data(data={
    "user": "john",
    "action": "login",
    "timestamp": 1234567890
})

# Estrutura interna
class Data:
    data: dict | list | str | int | float | bool
    # ... outros campos
```

### RunPayload (Telemetria)

**Localização**: `langflow.services.telemetry.schema`

```python
@dataclass
class RunPayload:
    run_is_webhook: bool      # True para execuções via webhook
    run_seconds: int          # Tempo de execução em segundos
    run_success: bool         # Sucesso ou falha
    run_error_message: str    # Mensagem de erro (vazio se sucesso)
    run_id: str | None        # UUID único da execução
```

**Exemplo de uso:**
```python
await telemetry_service.log_package_run(
    RunPayload(
        run_is_webhook=True,
        run_seconds=5,
        run_success=True,
        run_error_message="",
        run_id="550e8400-e29b-41d4-a716-446655440000",
    )
)
```

---

## Exemplos de Uso

### Exemplo 1: Webhook Simples (Sem Autenticação)

**Configuração:**
```bash
WEBHOOK_AUTH_ENABLE=false
```

**Flow:**
```
Webhook → Text Output
```

**Chamada:**
```bash
curl -X POST "https://langflow.com/api/v1/webhook/my-flow" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello from external system",
    "timestamp": 1234567890
  }'
```

**Response (imediato):**
```json
{
  "message": "Task started in the background",
  "status": "in progress"
}
```

**O que acontece:**
1. Request aceito imediatamente (202)
2. Payload `{"message": "...", "timestamp": ...}` injetado no Webhook component
3. Flow executa em background
4. WebhookComponent.build_data() retorna Data object com o payload
5. Próximos componentes recebem os dados

### Exemplo 2: Webhook com Autenticação

**Configuração:**
```bash
WEBHOOK_AUTH_ENABLE=true
```

**Chamada:**
```bash
curl -X POST "https://langflow.com/api/v1/webhook/my-flow" \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-lf-abc123xyz..." \
  -d '{
    "user_id": 123,
    "action": "process_data",
    "data": [1, 2, 3, 4, 5]
  }'
```

**Validações realizadas:**
1. API key existe?
2. API key é válida?
3. API key pertence ao dono do flow?

**Se alguma falhar:**
```json
{
  "detail": "Invalid API key"
}
```
ou
```json
{
  "detail": "Access denied: You can only execute webhooks for flows you own"
}
```

### Exemplo 3: Webhook com JSON Complexo

**Payload:**
```json
{
  "event": "order_created",
  "order": {
    "id": "ORD-12345",
    "customer": {
      "name": "John Doe",
      "email": "john@example.com"
    },
    "items": [
      {
        "product_id": "PROD-1",
        "quantity": 2,
        "price": 29.99
      },
      {
        "product_id": "PROD-2",
        "quantity": 1,
        "price": 49.99
      }
    ],
    "total": 109.97,
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Flow:**
```
Webhook → Python Code → Chat Output
```

**Python Code Component:**
```python
from langflow.custom import Component
from langflow.io import Output
from lfx.schema.data import Data

class ProcessOrder(Component):
    inputs = [
        DataInput(name="webhook_data")
    ]
    outputs = [
        Output(name="result", method="process")
    ]

    def process(self) -> str:
        # Acessa dados do webhook
        order_data = self.webhook_data.data

        # Processa
        order_id = order_data["order"]["id"]
        total = order_data["order"]["total"]
        customer = order_data["order"]["customer"]["name"]

        return f"Order {order_id} for {customer} - Total: ${total}"
```

### Exemplo 4: Webhook com Payload Inválido (JSON)

**Chamada:**
```bash
curl -X POST "https://langflow.com/api/v1/webhook/my-flow" \
  -H "Content-Type: application/json" \
  -d 'this is not json'
```

**O que acontece:**
```python
# No WebhookComponent.build_data()
try:
    body = json.loads(data)  # Falha!
except json.JSONDecodeError:
    # Encapsula em payload
    body = {"payload": "this is not json"}
    message = f"Invalid JSON payload. Please check the format.\n\nthis is not json"

# Retorna Data object mesmo assim
return Data(data=body)
```

**Result:**
```python
data.data = {
    "payload": "this is not json"
}
```

### Exemplo 5: Múltiplos Webhooks em um Flow

**Flow:**
```
Webhook-1 (Entrada A) ─┐
                        ├─→ Merge → Process → Output
Webhook-2 (Entrada B) ─┘
```

**Backend behavior:**
```python
webhook_components = get_all_webhook_components_in_flow(flow.data)
# Retorna: [
#   {"id": "Webhook-1-abc", ...},
#   {"id": "Webhook-2-xyz", ...}
# ]

# Cria tweaks para TODOS os webhooks
tweaks = {
    "Webhook-1-abc": {"data": '{"type": "A", ...}'},
    "Webhook-2-xyz": {"data": '{"type": "A", ...}'},  # Mesmo payload
}
```

**Resultado:**
- Ambos os componentes Webhook recebem o mesmo payload
- Cada um pode processá-lo independentemente
- Útil para flows com múltiplas entradas webhook

### Exemplo 6: Endpoint Name vs Flow ID

**Por endpoint name:**
```bash
curl -X POST "https://langflow.com/api/v1/webhook/order-processor" \
  -H "Content-Type: application/json" \
  -d '{"order_id": 123}'
```

**Por flow ID:**
```bash
curl -X POST "https://langflow.com/api/v1/webhook/550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{"order_id": 123}'
```

**Backend resolution:**
```python
# Dependency injection em endpoints.py
async def get_flow_by_id_or_endpoint_name(
    flow_id_or_name: str,
    ...
) -> Flow:
    # Tenta por UUID primeiro
    try:
        flow_id = UUID(flow_id_or_name)
        flow = await get_flow_by_id(flow_id)
        if flow:
            return flow
    except ValueError:
        pass

    # Se não for UUID, tenta por endpoint_name
    flow = await get_flow_by_endpoint_name(flow_id_or_name)
    if flow:
        return flow

    raise HTTPException(404, "Flow not found")
```

---

## Detalhes de Implementação

### 1. Identificação de Componentes Webhook

**Método usado:**
```python
def get_all_webhook_components_in_flow(flow_data: dict | None):
    if not flow_data:
        return []
    return [
        node
        for node in flow_data.get("nodes", [])
        if "Webhook" in node.get("id")
    ]
```

**Formato do ID:**
```python
# Padrão gerado pelo Langflow
"Webhook-abc123"     # ✅ Detectado
"webhook-xyz789"     # ✅ Detectado (case-insensitive? Não!)
"MyWebhook-123"      # ✅ Detectado (contém "Webhook")
"WebhookCustom-456"  # ✅ Detectado
"MyComponent-789"    # ❌ NÃO detectado
```

**IMPORTANTE:** O nome do componente deve conter exatamente "Webhook" (case-sensitive).

### 2. Injeção de Payload via Tweaks

**Mecanismo:**
```python
# 1. Payload recebido
raw_payload = b'{"message": "hello"}'

# 2. Conversão para string
payload_str = raw_payload.decode() if isinstance(raw_payload, bytes) else raw_payload

# 3. Criação de tweak
tweaks = {
    "Webhook-abc123": {
        "data": payload_str  # String JSON
    }
}

# 4. Aplicação no graph
graph_data = process_tweaks(graph_data, tweaks, stream=False)

# 5. No componente
# self.data agora contém '{"message": "hello"}'
```

**Fluxo de dados:**
```
HTTP Body → bytes → string → tweak → component.data → JSON parse → Data object
```

### 3. Execução em Background

**FastAPI BackgroundTasks:**
```python
background_tasks = BackgroundTasks()

# Adiciona tarefa
background_tasks.add_task(
    simple_run_flow_task,
    flow=flow,
    input_request=input_request,
    # ... outros args
)

# Response imediato (tarefa ainda não executou)
return {"message": "Task started in the background", "status": "in progress"}

# Tarefa executa APÓS o response ser enviado
```

**Vantagens:**
- Response rápido ao cliente
- Webhook não bloqueia
- Suporta execuções longas

**Desvantagens:**
- Cliente não recebe resultado
- Não há callback automático
- Precisa implementar mecanismo próprio de notificação se necessário

### 4. Tratamento de Erros

**No endpoint:**
```python
try:
    data = await request.body()
except Exception as exc:
    raise HTTPException(status_code=500, detail=str(exc))

if not data:
    raise HTTPException(status_code=400, detail="Request body is empty...")
```

**No background task:**
```python
async def simple_run_flow_task(...):
    try:
        result = await simple_run_flow(...)
        # Log sucesso
    except Exception as exc:
        await logger.aexception(f"Error running flow {flow.id} task")
        # Log erro (mas NÃO levanta exceção)
        return None
```

**No componente:**
```python
def build_data(self) -> Data:
    if not self.data:
        self.status = "No data provided."
        return Data(data={})

    try:
        body = json.loads(self.data)
    except json.JSONDecodeError:
        # Não falha! Encapsula como payload
        body = {"payload": self.data}
        message = f"Invalid JSON payload..."

    return Data(data=body)
```

### 5. Telemetria

**Pontos de tracking:**

1. **Início da execução:**
```python
start_time = time.perf_counter()
```

2. **Fim com sucesso:**
```python
await telemetry_service.log_package_run(
    RunPayload(
        run_is_webhook=True,
        run_seconds=int(time.perf_counter() - start_time),
        run_success=True,
        run_error_message="",
        run_id=run_id,
    )
)
```

3. **Fim com erro:**
```python
await telemetry_service.log_package_run(
    RunPayload(
        run_is_webhook=True,
        run_seconds=int(time.perf_counter() - start_time),
        run_success=False,
        run_error_message=str(exc),
        run_id=run_id,
    )
)
```

**Dados coletados:**
- Se foi webhook (vs API normal)
- Tempo de execução
- Sucesso/Falha
- Mensagem de erro
- Run ID único

### 6. Substituição de Placeholders no Frontend

**Placeholders definidos:**
```typescript
// No componente Python
value="BACKEND_URL"     // Para endpoint
value="CURL_WEBHOOK"    // Para cURL
value="MCP_SSE"         // Para MCP SSE

// Substituições no frontend
"BACKEND_URL" → "https://langflow.com/api/v1/webhook/my-flow"
"CURL_WEBHOOK" → "curl -X POST \"https://...\" -d '{...}'"
"MCP_SSE" → "https://langflow.com/api/v1/mcp/sse"
```

**Momento da substituição:**
```typescript
// 1. Componente monta
useEffect(() => {
  if (value === "BACKEND_URL") {
    const realUrl = `${protocol}//${host}/api/v1/webhook/${endpointName}`;
    handleOnNewValue({ value: realUrl });
  }
}, [value, endpointName]);

// 2. Renderização
const valueToRender = useMemo(() => {
  if (value === "BACKEND_URL") {
    return `${URL_WEBHOOK}${endpointName}`;
  }
  return value;
}, [value, endpointName]);
```

### 7. Configuração de Polling

**Frontend config:**
```typescript
// ConfigResponse
webhook_polling_interval: int  // Intervalo em ms

// Exemplo no .env
WEBHOOK_POLLING_INTERVAL=5000  // 5 segundos
```

**Uso:**
```typescript
// Frontend busca builds periodicamente
useEffect(() => {
  const interval = setInterval(() => {
    getBuildsMutation({ flowId });
  }, webhookPollingInterval);

  return () => clearInterval(interval);
}, []);
```

**Finalidade:**
- Garante que flow está buildado antes de usar webhook
- Atualiza endpoint URL se flow for renomeado
- Sincroniza estado entre frontend e backend

### 8. Session Management

**Webhooks não usam sessões:**
```python
input_request = SimplifiedAPIRequest(
    # ...
    session_id=None,  # Sempre None para webhooks
)
```

**Razão:**
- Webhooks são stateless por natureza
- Cada chamada é independente
- Não há conceito de "conversa" como no chat

**Se precisar de sessão:**
- Enviar session_id no payload
- Usar componente customizado para extrair e usar
- Implementar lógica própria de gerenciamento

---

## Conclusão

O sistema de webhook do Langflow é uma solução robusta e bem arquitetada que permite:

✅ **Integração Externa**: Qualquer sistema pode chamar flows via HTTP POST
✅ **Execução Assíncrona**: Responses rápidos, execução em background
✅ **Autenticação Flexível**: Com ou sem API key
✅ **Payload Flexível**: Aceita qualquer JSON
✅ **UI Amigável**: Geração automática de URLs e comandos cURL
✅ **Telemetria**: Tracking completo de execuções
✅ **Tratamento de Erros**: Graceful degradation em múltiplos pontos

### Pontos de Atenção para Melhorias

1. **Falta de Callback**: Cliente não recebe resultado da execução
   - Considerar: webhooks de retorno, polling endpoint, WebSocket

2. **Identificação de Componentes**: Baseada em substring "Webhook" no ID
   - Considerar: campo específico no schema, type property

3. **Múltiplos Webhooks**: Todos recebem o mesmo payload
   - Considerar: routing por path, identificação por header

4. **Sessões**: Não suportadas nativamente
   - Considerar: suporte opcional via payload

5. **Rate Limiting**: Não implementado
   - Considerar: throttling por usuário/flow

6. **Retries**: Não há retry automático em falhas
   - Considerar: retry queue, dead letter queue

7. **Payload Size**: Sem limite explícito documentado
   - Considerar: validação e documentação de limites

Este documento cobre todos os aspectos do sistema de webhook do Langflow em sua implementação atual. Use-o como referência para entender, manter e evoluir o sistema.
