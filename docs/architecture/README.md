# Langflow 架构文档

## 工程结构图

`src/` 下 6 大模块及其子模块：

| 模块 | 角色 | 关键子模块 |
|------|------|-----------|
| **backend/** | Python 后端 (langflow-base) | api/(v1+v2路由), services/(服务层), processing/(流执行), agentic/(AI辅助), alembic/(迁移) |
| **frontend/** | React 19 + Vite 前端 | pages/(页面), components/ui+core, stores/(Zustand状态), CustomNodes/(XYFlow), types, controllers |
| **lfx/** | 核心运行时 (共享引擎) | components/(109+组件), graph/(图执行引擎), services/(服务框架), cli/(命令行), custom/(组件基类) |
| **sdk/** | Python SDK | client.py (HTTP), models.py, environments.py |
| **bundles/** | 扩展包 | duckduckgo, arxiv, ibm, docling |
| **langflow-stepflow/** | 实验性后端 | Stepflow 执行后端 (alpha) |

## 系统架构图

5 层运行时架构（自上而下）：

| 层 | 组件 |
|----|------|
| **展示层** | React SPA → FlowPage / Zustand / XYFlow / shadcn/ui / Axios |
| **API 网关层** | FastAPI (uvicorn/gunicorn) → API v1 (REST/SSE) / v2 (Workflow) / Agentic API |
| **服务层** | Auth → Database → Chat → Storage → Tracing (OTel) → Telemetry → Cache → Session → Task Queue → Store |
| **核心引擎层** | LFX Runtime → Graph Engine / Component Framework / Service Framework / CLI / 109+内置组件 / Custom Components / Plugins / LangChain Core |
| **基础设施层** | SQLite/PostgreSQL / Redis / LLM APIs / Vector Stores / LangFuse/LangSmith |
