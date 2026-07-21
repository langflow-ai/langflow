# Langflow Java SDK

基于 JDK 21、OkHttp 4 和 Jackson 的 Langflow Java SDK。v1 与 v2 使用独立目录和包，避免接口模型混用。

## 构建

```bash
cd src/sdk-java
mvn test
```

## v1

```java
import org.langflow.sdk.v1.LangflowClient;

try (var client = LangflowClient.builder("http://localhost:7860")
        .apiKey(System.getenv("LANGFLOW_API_KEY"))
        .build()) {
    var response = client.run("my-flow", "你好");
    System.out.println(response.firstTextOutput());
}
```

URL、端口、API Key 和超时均可配置：

```java
var client = LangflowClient.builder("localhost", 7860)
    .scheme("http")
    .apiKey(System.getenv("LANGFLOW_API_KEY"))
    .connectTimeout(Duration.ofSeconds(10))
    .readTimeout(Duration.ofSeconds(60))
    .writeTimeout(Duration.ofSeconds(60))
    .callTimeout(Duration.ofSeconds(90))
    .build();
```

`.timeout(Duration)` 可一次设置全部四类超时；`builder("https://host:port")` 仍然可用。v1 和 v2 Builder 提供相同的配置接口。

## DEBUG 请求日志（Spring Boot）

SDK 会在 DEBUG 级别记录请求 URL、请求参数、响应参数、HTTP 状态码和耗时。API Key、Authorization 以及常见密码/Token 字段会脱敏。

```yaml
logging:
  level:
    org.langflow.sdk.http: DEBUG
    org.langflow.sdk.sse: DEBUG
```

普通响应日志最大记录 1 MB，超过部分会标记为 `<truncated>`。SSE 响应不会被预读取，而是通过 `org.langflow.sdk.sse` 逐事件记录。

SSE 基于 `okhttp-sse`，返回 JDK `Flow.Publisher`：

```java
client.stream("my-flow", new RunRequest("你好")).subscribe(subscriber);
```

v1 当前包含 Flow CRUD、运行与 SSE、Project CRUD；模型位于 `org.langflow.sdk.v1.model`。

## v2

```java
import org.langflow.sdk.v2.LangflowClient;
import org.langflow.sdk.v2.model.V2Models.WorkflowRequest;

try (var client = LangflowClient.builder("http://localhost:7860")
        .apiKey(System.getenv("LANGFLOW_API_KEY"))
        .build()) {
    var result = client.execute(WorkflowRequest.synchronous(
        "my-flow", Map.of("ChatInput-1.input_value", "你好")));
}
```

v2 包含 Workflow 同步/后台执行、任务状态查询和停止任务；模型位于 `org.langflow.sdk.v2.model`。服务端目前对 v2 streaming 返回 501，因此 SDK 未伪造不可用的流式能力。

