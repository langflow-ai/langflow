# Langflow SDK Spring Boot Demo

JDK 21 + Spring Boot 4.1.0 示例，同时演示 Langflow SDK v1 和 v2。

## 启动

先将 SDK 安装到本地 Maven 仓库：

```bash
cd ../sdk-java
mvn clean install
```

启动 Demo：

```bash
cd ../sdk-java-springboot-demo
export LANGFLOW_API_KEY="your-api-key"
mvn spring-boot:run
```

默认连接 `http://localhost:7860`，Demo 监听 `8080`。所有配置均可通过 `application.yml` 中列出的环境变量覆盖。

## v1

```bash
curl http://localhost:8080/demo/v1/flows

curl -X POST http://localhost:8080/demo/v1/run \
  -H 'Content-Type: application/json' \
  -d '{"flowId":"your-flow-id","inputValue":"你好"}'

curl -N 'http://localhost:8080/demo/v1/stream?flowId=your-flow-id&inputValue=你好'
```

## v2

同步运行：

```bash
curl -X POST http://localhost:8080/demo/v2/run \
  -H 'Content-Type: application/json' \
  -d '{"flowId":"your-flow-id","background":false,"inputs":{"ChatInput-1.input_value":"你好"}}'
```

后台运行时将 `background` 改成 `true`，然后查询或停止：

```bash
curl 'http://localhost:8080/demo/v2/status?jobId=your-job-id'
curl -X POST http://localhost:8080/demo/v2/stop -H 'Content-Type: application/json' -d '{"jobId":"your-job-id"}'
```

v2 需要 Langflow 服务端开启 Developer API。组件输入键必须使用真实的 `组件ID.参数名`。
