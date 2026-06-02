# Canvas Node Types

## Overview

Two simple node types for sequence diagrams. Each node is just a label with a visual indicator of its type — no parameter panels, no complex state.

Registered in `src/frontend/src/pages/FlowPage/consts.ts` alongside the existing `genericNode` and `noteNode`.

```ts
export const nodeTypes = {
  genericNode: GenericNode,
  noteNode: NoteNode,
  actorNode: ActorNode,   // ← new
  systemNode: SystemNode, // ← new
};
```

---

## Node Types

### `actorNode` — Human actor (User, Admin, etc.)

```
┌──────────┐
│    👤    │
│  User    │
└──────────┘
```

- Person icon at top
- Label below (e.g. `User`, `Admin`)
- xyflow handles in/out for edges

### `systemNode` — System, service, or interface

```
┌──────────────────┐
│  Chat Interface  │
└──────────────────┘
```

- Plain rounded rectangle
- Label centred (e.g. `Chat Interface`, `LLM Engine`)
- xyflow handles in/out for edges

---

## xyflow JSON Shape

```json
{
  "nodes": [
    {
      "id": "user",
      "type": "actorNode",
      "position": { "x": 100, "y": 50 },
      "data": { "label": "User" }
    },
    {
      "id": "chat",
      "type": "systemNode",
      "position": { "x": 300, "y": 50 },
      "data": { "label": "Chat Interface" }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "user",
      "target": "chat",
      "label": "submit spec",
      "data": { "order": 1 }
    }
  ]
}
```

`data` only ever needs `label`. Nothing else.

---

## Mermaid ↔ xyflow Mapping

| Mermaid | xyflow type |
|---|---|
| `actor User` | `actorNode` |
| `participant Chat as Chat Interface` | `systemNode` |
| `User->>Chat: message` | edge with `label` |

The Mermaid → xyflow parser is a small utility that iterates declarations and maps them to nodes/edges. The reverse (xyflow → Mermaid) serialises nodes back to `actor`/`participant` declarations and edges to `->>`  lines.
