# 4. The Graph Engine (LFX) — Heart of Langflow

Everything you draw on the canvas becomes a **Graph** of **Vertex** nodes connected by **Edge** objects.

## Core types

```mermaid
classDiagram
    class Graph {
        +start: Vertex
        +end: Vertex
        +vertices: dict~str, Vertex~
        +edges: list~Edge~
        +flow_id, flow_name, user_id
        +initialize_run()
        +async_start() async
        +get_sorted_vertices() layers
    }

    class Vertex {
        +id: str
        +base_name: str
        +full_data: NodeData
        +built_object: Component
        +built_result: Any
        +raw_params: dict
        +artifacts: dict
        +state: ACTIVE|INACTIVE|ERROR
        +build() async
        +run() async
    }

    class Edge {
        +source: str
        +target: str
        +output_socket: str
        +input_socket: str
    }

    class Component {
        +display_name
        +inputs: list~Input~
        +outputs: list~Output~
        +process() : Message
    }

    Graph "1" *-- "many" Vertex
    Graph "1" *-- "many" Edge
    Vertex "1" --> "1" Component : built_object
    Edge ..> Vertex : source/target
```

## Execution algorithm

```mermaid
flowchart TD
    A[Flow JSON from DB or payload] --> B[Graph.from_payload<br/>parse nodes/edges]
    B --> C[Validate: acyclic,<br/>types compatible]
    C --> D[Topological sort<br/>→ execution layers]
    D --> E{For each layer}
    E --> F[For each vertex in layer<br/>parallel]
    F --> G[Pull inputs from<br/>upstream artifacts]
    G --> H[vertex.build<br/>instantiate Component]
    H --> I[vertex.run<br/>call method e.g. process]
    I --> J{Success?}
    J -- yes --> K[Cache result in<br/>vertex.built_result]
    J -- no --> L[state = ERROR<br/>propagate downstream]
    K --> M[Emit SSE event<br/>to frontend]
    L --> M
    M --> E
    E -- done --> N[Return final output<br/>+ end event]
```

## Key files

- `src/lfx/src/lfx/graph/graph/base.py` — `Graph` class
- `src/lfx/src/lfx/graph/vertex/base.py` — `Vertex` class (states: `ACTIVE`, `INACTIVE`, `ERROR`)
- `src/lfx/src/lfx/graph/edge/base.py` — `Edge` and `CycleEdge`
- `src/lfx/src/lfx/custom/custom_component/component.py` — base `Component`
- `src/lfx/src/lfx/components/` — 200+ built-in components (LLMs, vector stores, tools, agents…)
- `src/lfx/src/lfx/interface/initialize.py` — component auto-discovery

## What a Component looks like

A Component is just a Python class declaring `inputs`, `outputs`, and a method per output. The framework introspects those declarations to auto-generate the UI panel, the JSON schema, and the typed wiring rules — so the same class is both UI and runtime.

```python
from langflow.custom import Component
from langflow.io import MessageTextInput, Output

class MyComponent(Component):
    display_name = "My Component"
    description  = "What it does"
    icon         = "component-icon"

    inputs = [
        MessageTextInput(name="input_value", display_name="Input"),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="process"),
    ]

    def process(self) -> Message:
        return Message(text=self.input_value)
```

> **Heads up:** the *class name* is the stable identifier the UI uses to match nodes in saved flows. Renaming it is a breaking change.

## Why layered execution?

A topological sort partitions vertices into **layers** where everything in one layer can run in parallel. The engine:

1. Computes the layers once per build.
2. For each layer, runs all vertices concurrently.
3. Pulls each vertex's inputs from upstream vertices' cached `built_result`.
4. Emits an SSE event after every vertex so the UI can light up nodes as they complete.

Errors don't abort the whole graph — they mark the failing vertex `ERROR`, and downstream vertices that depended on it become `INACTIVE`.
