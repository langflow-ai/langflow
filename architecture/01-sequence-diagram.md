# Sequence Diagram — Product Building Flow

This diagram captures the meta-flow: how a user goes from a product idea to generated code.

```mermaid
sequenceDiagram
    actor User
    participant Chat as 💬 Chat Interface
    participant LLM as 🤖 LLM Engine
    participant Canvas as 🎨 Interactive Canvas

    rect rgb(224, 242, 254)
        Note over User, LLM: 📋 PHASE 1 — Specification
        User->>Chat: Submit product specification
    end

    rect rgb(220, 252, 231)
        Note over User, LLM: 🔄 PHASE 2 — Clarification Loop
        loop Until full clarity reached
            Chat->>LLM: Forward spec / answers
            LLM->>Chat: Return clarifying questions
            Chat->>User: Display questions (options or free text)
            User->>Chat: Answer questions
        end
        Note over User, LLM: ✅ Shared understanding established
    end

    rect rgb(254, 243, 199)
        Note over LLM, Canvas: 🗂️ PHASE 3 — Diagram Generation
        LLM->>LLM: Generate sequence diagram
        LLM->>Canvas: Render sequence diagram
    end

    rect rgb(243, 232, 255)
        Note over User, Canvas: ✏️ PHASE 4 — Diagram Refinement Loop
        loop Until user approves
            Canvas->>User: Display interactive diagram

            alt 🖱️ User edits on Canvas
                User->>Canvas: Modify diagram (drag and drop)
                Canvas->>LLM: Send full updated diagram + prior context
                LLM->>LLM: Validate changes are coherent
                LLM->>Canvas: Return validated / adjusted diagram
            else 💬 User edits via Chat
                User->>Chat: Describe change in natural language
                Chat->>LLM: Forward change request + current diagram
                LLM->>LLM: Apply change, validate coherence
                LLM->>Canvas: Render updated diagram
            end

            User->>Chat: ✅ Approve diagram
        end
    end

    rect rgb(254, 226, 226)
        Note over LLM, Chat: 🚀 PHASE 5 — Code Generation
        LLM->>LLM: Generate application code
        LLM->>Chat: Deliver final code to User
    end
```

## Notes

- The clarification loop terminates on LLM confidence, not a fixed number of turns.
- Canvas edits and chat edits are equivalent paths — LLM remains the single source of truth for diagram state.
- Code generation is a single step here; it will be expanded into its own sequence diagram in a later iteration.
