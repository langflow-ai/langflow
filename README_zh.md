# Langflow: 可视化 AI 应用构建平台

[Langflow](https://langflow.org) 是一个强大的工具，用于构建和部署 AI 驱动的代理（Agent）和工作流（Workflow）。它为开发者同时提供了可视化的创作体验和内置的 API 服务器，使得每一个构建的代理都能轻松转化为 API 端点，并集成到基于任何框架或技术栈的应用程序中。Langflow 功能全面，支持所有主流的大语言模型（LLM）、向量数据库以及不断增长的 AI 工具库。

## 低代码驱动工作流原理

Langflow 的核心是其低代码特性，允许用户通过图形化界面快速构建复杂的人工智能应用，而无需深入编写每一行代码。其工作原理主要基于以下概念和流程：

**1. 可视化构建与前端交互**

用户在 Langflow 的图形界面上，通过从组件库中拖拽组件到画布上，并使用连接线（Edges）将它们连接起来，从而定义了一个工作流（Flow）。

*   **组件选择与参数配置**：用户为每个组件设置特定的参数，例如填写提示模板、选择模型、配置 API 密钥等。
*   **前端数据结构**：这些操作在前端被转换成一种 JSON 数据结构，描述了所有的组件（节点 Nodes）、它们的参数、以及它们之间的连接关系（Edges）。这个 JSON 对象随后会被发送到 Langflow 后端。

**2. 后端图表示 (`Graph` 对象) 与组件 (`Component`) 封装**

当后端接收到前端发送的 Flow 定义（JSON 数据）后，会进行以下处理：

*   **`Graph` 对象的实例化**：Langflow 使用 `Graph.from_payload(payload)` (或类似方法) 将接收到的 JSON 数据解析并构建成一个 `Graph` 对象实例。这个 `Graph` 对象是整个工作流在后端的核心表示。
    ```python
    # 概念性代码片段，源于 src/backend/base/langflow/graph/graph/base.py
    class Graph:
        def __init__(self, flow_id: str | None = None, ...):
            self.vertices: list[Vertex] = [] # 存储图中的所有顶点 (组件实例的封装)
            self.edges: list[Edge] = []     # 存储图中的所有边 (连接)
            self.vertex_map: dict[str, Vertex] = {} # 通过ID快速访问顶点
            # ... 其他属性和方法

        @classmethod
        def from_payload(cls, payload: dict, ...):
            graph = cls(...)
            vertices_data = payload.get("nodes", [])
            edges_data = payload.get("edges", [])
            # 根据 vertices_data 和 edges_data 创建 Vertex 和 Edge 对象
            # 并将它们添加到 graph.vertices 和 graph.edges 列表中
            graph.add_nodes_and_edges(vertices_data, edges_data)
            return graph
    ```

*   **`Vertex` (顶点) 作为组件的容器**：图中的每个节点（组件）被实例化为一个 `Vertex` 对象。`Vertex` 对象充当实际组件逻辑的容器和上下文。它会根据节点类型加载并实例化相应的 `Component` 子类。

*   **`Component` (组件) 封装业务逻辑与接口**：每个 `Vertex` 内部都包含一个 `Component` 的实例。`Component` 类 (位于 `src/backend/base/langflow/custom/custom_component/component.py`) 是所有功能组件的基石。开发者通过继承此类来创建自定义组件。
    *   **定义输入输出**：`Component` 通过类属性 `inputs: list[InputTypes]` 和 `outputs: list[Output]` 来声明其数据接口。
        ```python
        # 概念性代码片段，源于 src/backend/base/langflow/custom/custom_component/component.py
        from langflow.template.field.base import Input, Output
        from langflow.custom.custom_component.component import Component

        class MyCustomComponent(Component):
            display_name: str = "我的自定义组件"
            description: str = "这是一个自定义组件的示例"
            inputs = [
                Input(name="text_input", display_name="文本输入", field_type="str", required=True),
                Input(name="temperature", display_name="温度参数", field_type="float", value=0.7)
            ]
            outputs = [
                Output(name="processed_text", display_name="处理后文本", method="process_text_method")
            ]

            async def process_text_method(self) -> str:
                text = self.text_input # 访问输入参数
                temp = self.temperature
                # ... 执行一些处理逻辑 ...
                return f"处理后的: {text} (温度: {temp})"
        ```
    *   **封装执行逻辑**：组件的核心功能通过其方法实现，特别是与 `Output` 定义中 `method` 属性关联的方法。例如，上述 `process_text_method` 就是 `processed_text` 输出的实际执行逻辑。当工作流执行到这个组件的这个输出时，该方法会被调用。

**3. 执行编排与数据流动**

当一个 Flow 被触发执行时：

*   **拓扑排序与执行计划**：`Graph` 对象首先对其包含的 `Vertex`（组件）进行拓扑排序（例如通过 `get_sorted_vertices` 逻辑），以确定一个无环的执行顺序。这确保了前置组件的输出在其依赖组件执行之前就已经准备好。
    ```python
    # 概念性代码片段，源于 src/backend/base/langflow/graph/graph/base.py
    class Graph:
        # ...
        def sort_vertices(self, ...) -> list[str]: # 返回第一层可执行的顶点ID
            first_layer, remaining_layers = get_sorted_vertices(
                vertices_ids=self.get_vertex_ids(),
                # ... 其他图结构信息 ...
            )
            self._sorted_vertices_layers = [first_layer, *remaining_layers] # 存储分层执行计划
            return first_layer
    ```

*   **顺序/并行调用组件**：`Graph` 按照计算出的顺序（或对同一层级的组件进行并行处理）调用每个 `Vertex` 的 `build()` 方法。
    *   `Vertex.build()` 方法会进一步调用其内部 `Component` 实例的 `build_results()` (或类似的核心执行入口)。
    *   `Component.build_results()` 负责执行与该组件当前需要计算的输出所关联的方法（如上面例子中的 `process_text_method`）。

*   **数据传递**：当一个组件的方法执行完毕并返回结果后，这个结果会通过 `Graph` 中定义的 `Edge` (连接) 传递给下一个连接的组件，作为其输入参数的值。这个过程持续进行，直到整个 Flow 执行完毕。

*   **结果返回**：最终输出组件的结果被收集，并可以展示给用户或通过 API 返回给调用者。

通过这种方式，Langflow 实现了一种低代码的编程范式：用户通过可视化操作定义了组件的组合和数据流，而 Langflow 后端则将这些定义转换为一个可执行的、由 `Graph` 对象管理的、由各个 `Component` 实例具体执行业务逻辑的计算图。开发者可以专注于实现单个 `Component` 的功能，而 Langflow 负责处理它们的编排和执行。

## 工作流是如何组织的

在 Langflow 中，工作流 (Flow) 的组织和管理是其核心功能之一。它实现了一套自有的图（Graph）构建、管理和执行机制，其核心是 `langflow.graph.graph.base.Graph` 类。虽然其目标（编排 LLM 应用）与 LangGraph 等工具类似，都是基于图的思想，但 Langflow 的 `Graph` 实现是其自身项目的一部分，拥有其独特的设计。

工作流主要通过以下关键元素和机制来组织，下面将结合代码结构进行说明：

*   **核心图引擎 (`Graph` 类) 与后端图结构**:
    *   每个在 Langflow 中创建的 Flow 在后端都由一个 `langflow.graph.graph.base.Graph` Python 对象表示。这个 `Graph` 对象是工作流的中心枢纽，它维护了构成该 Flow 的所有元素及其关系。
    *   `Graph` 对象负责：
        *   存储和管理工作流中的所有顶点 (`Vertex`) 和边 (`Edge`)。
            ```python
            # 概念性代码片段，源于 src/backend/base/langflow/graph/graph/base.py
            class Graph:
                def __init__(self, ...):
                    self.vertices: list[Vertex] = []  # Vertex 对象的列表
                    self.edges: list[Edge] = []      # Edge 对象的列表
                    self.vertex_map: dict[str, Vertex] = {vertex.id: vertex for vertex in self.vertices} # 便于通过ID查找Vertex
                    # ...
            ```
        *   从前端发送的 JSON 定义 (payload) 构建图结构。
        *   准备执行环境，例如通过 `prepare()` 方法进行图的校验和初始化执行队列。
        *   编排和驱动整个工作流的执行，例如通过 `process()` 或 `astep()` 方法。

*   **顶点 (`Vertex` 类)**:
    *   图中的每个组件节点在后端由 `langflow.graph.vertex.base.Vertex` 类的实例表示。
    *   `Vertex` 是 `Component` 实例的直接封装者和执行上下文。它不直接包含业务逻辑，而是加载并持有一个 `Component` 实例。
    *   `Vertex` 负责：
        *   根据节点定义（从前端传来）实例化对应的 `Component` 子类。
            ```python
            # 概念性代码片段，源于 src/backend/base/langflow/graph/graph/base.py
            class Graph:
                def _create_vertex(self, frontend_data: NodeData) -> Vertex:
                    # ... 根据 frontend_data['data']['type'] 等信息确定 Vertex 的具体类型 ...
                    vertex_class = self._get_vertex_class(...)
                    vertex_instance = vertex_class(frontend_data, graph=self) # 创建 Vertex
                    # Vertex 内部会负责实例化其 Component
                    return vertex_instance
            ```
        *   调用其内部 `Component` 的 `build()` 或 `build_results()` 方法来执行实际的节点逻辑。
        *   管理节点的执行状态（例如，是否已构建、是否激活、是否为循环的一部分）。
        *   处理与边的连接，获取输入数据并传递输出数据。

*   **组件实例 (`Component` 类)**:
    *   实际的业务逻辑由 `langflow.custom.custom_component.component.Component` 的子类实例执行。
    *   `Vertex` 在初始化时会创建并持有其对应的 `Component` 实例。
    *   `Component` 定义了节点的输入、输出和核心处理方法，如前一节所述。

*   **边 (`Edge` 类)**:
    *   组件之间的连接由 `langflow.graph.edge.base.Edge` 类的实例表示。
    *   `Edge` 清晰地定义了数据流：它连接了一个源 `Vertex` (的某个输出) 和一个目标 `Vertex` (的某个输入)。
    *   `Graph` 对象存储所有 `Edge`，并利用这些连接信息构建邻接关系，如 `predecessor_map` (前驱节点映射) 和 `successor_map` (后继节点映射)，这些是进行拓扑排序和执行调度的基础。

*   **执行流程与调度**:
    *   **拓扑排序**: 在执行之前，`Graph` 对象通常会调用类似 `get_sorted_vertices` 的逻辑（在 `Graph.sort_vertices()` 中使用）来对所有 `Vertex` 进行拓扑排序。这会产生一个分层的执行序列，确保依赖项在其使用者之前被执行。
        ```python
        # 概念性代码片段，源于 src/backend/base/langflow/graph/graph/utils.py
        def get_sorted_vertices(vertices_ids: list[str], graph_dict: dict, ...) -> tuple[list[str], list[list[str]]]:
            # ... 实现拓扑排序算法 ...
            # 返回第一层可执行的节点列表和后续层的节点列表
            return first_layer, layers
        ```
    *   **状态管理与迭代执行**: `Graph` 通过 `RunnableVerticesManager` (`run_manager`) 等机制来跟踪哪些 `Vertex` 当前是可运行的，哪些已经运行过，以及处理循环等复杂情况。
    *   **分步执行**: `Graph.astep()` 方法允许工作流分步异步执行，这对于交互式应用和流式输出非常重要。它一次处理执行队列中的一个或多个顶点，然后更新图的状态，并确定下一批可运行的顶点。

*   **与 LangGraph 的对比**:
    *   Langflow 的图编排机制在设计目标上与 LangGraph 有相似之处——都是为了构建和执行由多个步骤组成的 AI 应用，特别是围绕大语言模型的应用。两者都采用了图（Graph）作为核心的数据结构来表示工作流。
    *   然而，Langflow 拥有其独立的、自包含的图引擎实现 (`langflow.graph` 模块)。它并非直接建立在 LangGraph 库之上。Langflow 的 `Graph`, `Vertex`, 和 `Component` 体系是其自身框架的一部分，专为支持其可视化界面和组件化架构而设计。Langflow 的组件可以灵活地封装和使用 Langchain 的库（包括 LangGraph 中可能用到的原子操作），但其整体的图的构建、管理和执行是由 Langflow 自身的代码逻辑控制的。

总结来说，Langflow 的工作流是通过一个精心设计的、自有的图引擎来组织的。该引擎以 `Graph` 对象为核心，管理 `Vertex`（作为 `Component` 的容器）和 `Edge`（定义数据流）。通过拓扑排序和状态管理，Langflow 能够高效、灵活地执行用户在可视化界面上定义的复杂 AI 工作流。

## ✨ 主要特性

*   **可视化构建器界面**：快速上手并迭代您的 AI 应用。
*   **源码访问**：允许您使用 Python 自定义任何组件。
*   **交互式演练场（Playground）**：通过逐步控制，立即测试和优化您的 Flow。
*   **多智能体编排**：具备对话管理和检索功能。
*   **部署为 API**：或导出为 JSON 文件用于 Python 应用。
*   **可观测性**：与 LangSmith、LangFuse 及其他工具集成。
*   **企业级就绪**：具备安全性和可扩展性。

## ⚡️ 快速开始

Langflow 需要 [Python 3.10 到 3.13](https://www.python.org/downloads/release/python-3100/) 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。

1.  安装 Langflow，运行：
    ```shell
    uv pip install langflow
    ```

2.  运行 Langflow，执行：
    ```shell
    uv run langflow run
    ```

3.  在浏览器中打开 Langflow 的默认地址 `http://127.0.0.1:7860`。

更多关于 Langflow 安装的信息，包括 Docker 和桌面版选项，请参阅[安装 Langflow](https://docs.langflow.org/get-started-installation)（英文）。

## ⭐ 保持更新

在 GitHub 上 Star Langflow 项目，以便即时收到新版本的通知。

## 👋 如何贡献

我们欢迎所有级别的开发者参与贡献。如果您想做出贡献，请查看我们的[贡献指南](./CONTRIBUTING.md)（英文）并帮助 Langflow 变得更好。
