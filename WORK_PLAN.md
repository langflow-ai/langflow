# Langflow 功能开发工作计划

> **编写日期**: 2026-07-08  
> **优先级原则**: 组件/模块添加类任务优先，页面修改和Backend服务改造类任务置后

---

## 总体状态

| # | 功能 | 状态 | 优先级 | 类型 |
|---|------|------|--------|------|
| 1 | tirtonserver服务端管理 | ✅ 已完成 | — | Backend管理 |
| 2 | pgvector插入+查询组件 | ⬜ 待开发 | 🔴 P0-高 | 组件添加 |
| 3 | 单工作流应用导出 | ⬜ 待开发 | 🟡 P2-中 | Backend+Frontend |
| 4 | Project工作流卡片化 | ✅ 已完成 | — | Frontend UI |
| 5 | 工作流发布成样例模板 | ⬜ 待开发 | 🟢 P3-低 | Backend+Frontend |
| 6 | LLM-Skill组件 | ⬜ 待开发 | 🔴 P0-高 | 组件添加 |
| 7 | ❓AI工作流用途说明 | ⬜ 待开发 | 🟡 P2-中 | Frontend+LLM |
| 8 | 代码生成时对话框添加模块引用 | ⬜ 待开发 | 🟢 P3-低 | Frontend |

---

## P0 - 高优先级（组件/模块添加类）

### Feature 2: pgvector 插入 + 查询组件拆分

**现状**: 已有 `PGVectorStoreComponent`（`src/lfx/src/lfx/components/pgvector/pgvector.py`），同时包含插入和查询功能。  
**目标**: 拆分为两个独立组件，方便流程编排中灵活组合。

| 子任务 | 描述 | 涉及文件 | 预估工时 |
|--------|------|----------|------|
| 2.1 | 创建 `PGVectorInsertComponent` 组件 | 新建 `pgvector/insert.py`，继承 `LCVectorStoreComponent`，仅保留 `build_vector_store()` 和 `ingest_data` 相关逻辑 | 4d   |
| 2.2 | 创建 `PGVectorQueryComponent` 组件 | 新建 `pgvector/query.py`，继承 `LCVectorStoreComponent`，仅保留 `search_documents()` 和 `search_query` 相关逻辑 | 4d   |
| 2.3 | 更新 `pgvector/__init__.py` | 添加新组件的 lazy-loading 注册 | 0.5d |
| 2.4 | 注册到顶层 `__init__.py` | 在 `src/lfx/src/lfx/components/__init__.py` 中添加新组件名称 | 0.5d |
| 2.5 | 添加前端图标 | 在 `src/frontend/src/icons/` 创建图标，注册到 `lazyIconImports.ts` | 1d   |
| 2.6 | 单元测试 | 编写插入和查询组件的单元测试 | 2d   |

**依赖关系**: 2.3 → 2.1/2.2，2.4/2.5并行

---

### Feature 6: LLM-Skill 组件

**现状**: 无 Skill 概念，但已有 `FlowToolComponent`、`RunFlowComponent` 等作为 Agent 工具的组件模式。  
**目标**: 新增一个组件，让 LLM/Agent 能够调用预设的 Skill（如文件处理、数据分析等）。类似 LangChain 的 `tool` 概念，但封装为 Skill 注册表。

| 子任务 | 描述 | 涉及文件 | 预估工时 |
|--------|------|----------|------|
| 6.1 | 设计 Skill 注册协议 | 定义 Skill 接口：`name`、`description`、`parameters`(JSON Schema)、`execute()` 方法 | 2d   |
| 6.2 | 创建 `SkillRegistry` 管理器 | 新建 `src/lfx/src/lfx/skills/registry.py`，管理 Skill 的注册、发现、调用 | 4d   |
| 6.3 | 创建 `LCSkillToolComponent` 基类 | 继承 `LCToolComponent`，封装 Skill 调用逻辑，输出 `Tool` 类型供 Agent 使用 | 1d   |
| 6.4 | 创建内置 Skill 示例 | 如 `FileReaderSkill`、`WebSearchSkill`、`CodeExecutorSkill` 等 | 0.5d |
| 6.5 | 创建 `SkillSelectorComponent` | 让用户在流程中选择要启用的 Skill 列表 | 1d   |
| 6.6 | 注册组件并添加图标 | 顶层注册 + 前端图标 | 0.5d |
| 6.7 | 单元测试 | 测试 Skill 注册、调用、Agent 集成 | 2d   |

**依赖关系**: 6.1 → 6.2 → 6.3 → 6.4/6.5 → 6.6/6.7

---

## P2 - 中优先级（Backend服务 + Frontend页面）

### Feature 3: 单工作流应用导出

**现状**: 已有 Flow JSON 导出（`exportModal`）和 CLI `lfx run` 命令。  
**目标**: 将单个工作流导出为独立可运行应用，支持两种模式：
- **API模式**: 生成 FastAPI 服务，通过 HTTP 接口调用工作流
- **CLI模式**: 生成独立 Python 脚本，通过命令行直接运行

| 子任务 | 描述 | 涉及文件 | 预估工时 |
|--------|------|----------|------|
| 3.1 | 设计导出包结构 | 确定导出包的文件结构（如 `Dockerfile`、`requirements.txt`、`app.py`、`flow.json`） | 1d   |
| 3.2 | 后端：生成 FastAPI 包装脚本 | 新建 `src/backend/base/langflow/services/export/`，根据 Flow JSON 生成 FastAPI 应用代码 | 3d   |
| 3.3 | 后端：生成 CLI 运行脚本 | 根据 Flow JSON 生成 `lfx run` 等效的独立脚本 | 1d   |
| 3.4 | 后端：打包接口 | 新建 `POST /api/v1/flows/{id}/export-app`，返回 ZIP 包（含 Dockerfile + 脚本 + flow.json） | 1d   |
| 3.5 | 前端：导出模态框 | 新增"导出为应用"按钮，选择 API/CLI 模式，触发下载 | 2d   |
| 3.6 | 集成测试 | 导出后验证可独立运行 | 1d   |

**依赖关系**: 3.1 → 3.2/3.3 → 3.4 → 3.5 → 3.6

---

### Feature 7: AI 工作流用途说明（❓按钮）

**现状**: 工作流列表页 `ListComponent` 展示名称/图标/描述，Assistant Panel 支持 AI 对话。  
**目标**: 在工作流列表的每个 workflow 旁添加 ❓ 按钮，点击后调用 LLM 生成该工作流的具体作用和使用方法。

| 子任务 | 描述 | 涉及文件 | 预估工时 |
|--------|------|----------|------|
| 7.1 | 后端：Flow 分析接口 | 新建 `POST /api/v1/flows/{id}/analyze`，读取 Flow JSON，构造 Prompt 发送给 LLM，返回描述 | 2d   |
| 7.2 | 前端：❓ 按钮 UI | 在 `ListComponent` 的 Flow 卡片操作区添加 ❓ 按钮 | 1d   |
| 7.3 | 前端：分析结果弹窗 | 创建模态框展示 AI 返回的用途说明，支持复制/分享 | 1d   |
| 7.4 | 前端：Loading 状态 | 按钮点击后的流式加载动画（复用 SSE 模式） | 2d   |
| 7.5 | 后端测试 | 验证分析接口的 Prompt 质量和返回格式 | 1d   |

**依赖关系**: 7.1 与 7.2/7.3/7.4 可并行，最终集成测试 7.5

---

## P3 - 低优先级（页面改造为主）

### Feature 5: 工作流发布成样例模板

**现状**: 已有 Starter Projects 模板系统（`initial_setup/starter_projects/`）和模板搜索 API（`template_search.py`）。  
**目标**: 允许用户将自己创建的工作流发布为公共样例模板，供其他用户浏览和导入。

| 子任务 | 描述 | 涉及文件 | 预估工时 |
|--------|------|----------|------|
| 5.1 | 后端：模板发布接口 | `POST /api/v1/flows/{id}/publish-template`，将 Flow 标记为模板并保存到模板库 | 2d   |
| 5.2 | 后端：用户模板管理接口 | `GET/PATCH/DELETE /api/v1/templates/user/`，管理用户自己发布的模板 | 1d   |
| 5.3 | 后端：模板市场接口 | 扩展现有 `template_search.py`，支持搜索用户发布的模板 | 1d   |
| 5.4 | 前端：发布按钮 | Flow 操作菜单中添加"发布为模板"选项，填写模板信息（分类、标签、截图） | 1d   |
| 5.5 | 前端：模板市场页面 | 新建模板浏览页面，展示用户发布的模板，支持搜索/筛选/导入 | 2d   |
| 5.6 | 数据库：模板表 | 添加 `FlowTemplate` 模型（template_id、publisher_id、category、tags、download_count） | 2d   |
| 5.7 | 集成测试 | 端到端发布-浏览-导入流程测试 | 2d   |

**依赖关系**: 5.6 → 5.1/5.2 → 5.3 → 5.4/5.5 → 5.7

---

### Feature 8: 代码生成时对话框添加模块引用

**现状**: Assistant Panel 已支持代码生成（`SimplifiedCodeTabComponent` 渲染），`ContentDisplay.tsx` 处理 `"code"` 类型的 content block。  
**目标**: 在 AI 对话生成的代码块中，增加"添加此模块到工作流"的引用操作。

| 子任务 | 描述 | 涉及文件 | 预估工时 |
|--------|------|----------|------|
| 8.1 | 前端：修改代码块渲染 | 在 `SimplifiedCodeTabComponent` 或 `ContentDisplay.tsx` 的代码块中添加"添加到画布"按钮 | 1.5d |
| 8.2 | 前端：解析代码为 Node | 将生成的 Python 代码解析为对应的组件节点，调用 `addNode` 添加到当前画布 | 1d   |
| 8.3 | 前端：按钮交互与反馈 | 点击后的成功/失败提示，已在画布中的重复检测 | 2d   |
| 8.4 | 后端：代码→Node 解析增强 | 在 `assistant_runner.py` 的 flow update 逻辑中增强代码 block 到 Node 的映射 | 2d   |
| 8.5 | 测试 | 验证不同组件代码的解析和添加 | 1d   |

**依赖关系**: 8.1 → 8.2 → 8.3，8.4可并行，8.5收尾

---

## 推荐开发顺序

```
阶段一（第1-2周）：P0 组件添加
├── Feature 2: pgvector插入+查询组件      ──── 并行 ────┐
└── Feature 6: LLM-Skill组件              ──── 并行 ────┘

阶段二（第3-4周）：P2 Backend+Frontend
├── Feature 3: 单工作流应用导出           ──── 串行 ────┐
└── Feature 7: ❓AI工作流用途说明         ──── 并行 ────┘

阶段三（第5-6周）：P3 页面改造
├── Feature 5: 工作流发布成样例模板       ──── 串行 ────┐
└── Feature 8: 代码生成模块引用           ──── 并行 ────┘
```

## 风险与注意事项

| 风险项 | 影响功能 | 缓解措施 |
|--------|----------|----------|
| PGVector 组件拆分破坏现有流程兼容性 | Feature 2 | 保留原 `PGVectorStoreComponent` 并标记 `legacy=True`，新组件使用新类名 |
| Skill 组件需要 LLM Function Calling 支持 | Feature 6 | 基于已有 `StructuredTool` 模式实现，兼容 OpenAI/Anthropic |
| 导出应用的依赖管理复杂 | Feature 3 | 生成 `requirements.txt` 锁定版本，使用 `lfx` 核心作为依赖 |
| 模板发布涉及权限控制 | Feature 5 | 复用现有 RBAC 体系，添加 `TemplateAction.PUBLISH` 权限 |
| AI 分析流质量依赖 LLM 能力 | Feature 7 | 使用结构化 Prompt + JSON 输出格式，提供 fallback 默认描述 |

---

## 关键技术参考

| 功能 | 参考实现 | 位置 |
|------|----------|------|
| 组件创建 | `PGVectorStoreComponent`、`CalculatorToolComponent` | `src/lfx/src/lfx/components/pgvector/`、`tools/` |
| 组件注册 | `__init__.py` lazy-loading 模式 | 各组件目录 + 顶层 `components/__init__.py` |
| Tool 组件 | `LCToolComponent` 基类 | `src/lfx/src/lfx/base/langchain_utilities/model.py` |
| Flow 导出 | `downloadFlow()` + ZIP 打包 | `src/frontend/src/utils/reactflowUtils.ts`、`flows_helpers.py` |
| 模板系统 | `template_search.py`、Starter Projects | `src/backend/base/langflow/agentic/utils/` |
| AI 对话 | Assistant Panel + SSE 流式 | `src/frontend/src/components/core/assistantPanel/` |
| 代码渲染 | `SimplifiedCodeTabComponent` | `src/frontend/src/components/core/codeTabsComponent/` |
| 工作流卡片 | `ListComponent` + `Card` UI | `src/frontend/src/pages/MainPage/components/list/` |
