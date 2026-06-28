"""The canonical Architecture-stage artifact set and its generation prompts (Epic E.3a).

The ARCHITECTURE stage emits a **fixed map of five artifacts** — one ADR plus four
D2 diagrams — into `lothal_project.artifacts` (`{path: content}`, the future git
commit tree verbatim):

    adr.md                    -- Architecture Decision Record (Markdown)
    diagrams/context.d2       -- C4 L1 system context
    diagrams/container.d2     -- C4 L2 container view
    diagrams/data-model.d2    -- ERD (sql_table)
    diagrams/sequence.d2      -- core runtime flow (today's single diagram, carried over)

This module is the *single source* of that set: the diagram list here is what the
generation engine iterates and the refinement engine routes edits against, so the
set lives in one place and a future diagram (e.g. deployment, deferred to stage 7)
is one entry. Each diagram prompt is a diagram-specific preamble + skeleton +
rules, with the **shared D2 output contract** appended once so the four prompts
can't drift (the same body + shared-contract factoring the old single-diagram
prompt used). The ADR is Markdown, so it has its own prompt and skips the D2 contract.

Pure data/prompt module: no LLM, no DB, no engine imports. The engines
(`architecture_generation.py` / `architecture_refinement.py`) consume it.

Why these four diagrams (settled in E.3a, do not re-litigate): they span the
architecture story at four altitudes — *what/who* (context) → *how it's built*
(container) → *what data* (data model) → *how it runs over time* (sequence) — and
each maps onto a distinct, well-supported D2 idiom that derives cleanly from a
PRD. C4-component (L3) and deployment are deferred.
"""

from __future__ import annotations

from dataclasses import dataclass

# Artifact paths — the keys of the persisted map. The sequence diagram is the one
# the single-diagram canvas/read still shows (it mirrors `diagram_d2`), so it is
# named here for the engine to default refinement to and to keep that mirror.
ADR_PATH = "adr.md"
CONTEXT_PATH = "diagrams/context.d2"
CONTAINER_PATH = "diagrams/container.d2"
DATA_MODEL_PATH = "diagrams/data-model.d2"
SEQUENCE_PATH = "diagrams/sequence.d2"

# Human-readable artifact labels, used to ground the assistant's chat replies.
ARTIFACT_LABELS: dict[str, str] = {
    ADR_PATH: "architecture decision record",
    CONTEXT_PATH: "system context diagram",
    CONTAINER_PATH: "container diagram",
    DATA_MODEL_PATH: "data model diagram",
    SEQUENCE_PATH: "sequence diagram",
}


def artifact_label(path: str) -> str:
    """A readable name for an artifact path, falling back to the path itself."""
    return ARTIFACT_LABELS.get(path, path)


# The shared D2 output contract appended to every diagram prompt (generation and
# refinement). Factored once so the four diagram prompts can't drift on the
# common rules — ids, no layout, PRD-derived scope, must compile.
D2_OUTPUT_CONTRACT = """\
- Reply with D2 source and nothing else — no markdown fences, no prose, no diff markers.
- Use stable, lowercase, hyphen-free ids (`web`, `api`, `order_service`); the label is the \
readable name.
- D2 owns layout: never write positions, coordinates, sizes, or `near`/`width`/`height`.
- Derive everything from the PRD; cover the core architecture, stay focused, and do not invent \
scope the spec does not imply.
- Emit only valid D2 so it compiles."""


def _diagram_prompt(body: str) -> str:
    """A diagram system prompt: its specific body + the shared D2 output contract."""
    return f"{body}\n\n{D2_OUTPUT_CONTRACT}"


_CONTEXT_BODY = """\
You are Lothal's solution architect. From the clarification conversation so far and the product \
spec (PRD) it produced, draw the SYSTEM CONTEXT diagram (C4 level 1): the application as a single \
box, the people who use it, and the external systems it depends on — with the relationship \
labelled on each connection. Show the system's place in its world, not its internals.

Use exactly this structure:

direction: right
user: End User {shape: person}
app: My Application
stripe: Stripe {shape: cloud}
email: Email Provider {shape: cloud}

user -> app: uses
app -> stripe: process payments
app -> email: send notifications

Diagram-specific rules:
- One box for the application under design; a `shape: person` box per distinct human role; a \
`shape: cloud` box per external/third-party system the PRD names.
- One labelled connection per relationship (`source -> target: what it does`), in the direction \
the interaction flows.
- Do NOT show internal components (services, databases) here — that is the container diagram.
- Include every distinct human role and external/third-party system the PRD implies — no more, \
no fewer. If the PRD only implies one external participant, show one; do not invent extras."""

_CONTAINER_BODY = """\
You are Lothal's solution architect. From the clarification conversation so far and the product \
spec (PRD) it produced, draw the CONTAINER diagram (C4 level 2): inside the application's \
boundary, the major runtime building blocks — the frontend, the backend/API, datastores, \
background workers, queues — and how they talk to each other and to external systems. This is \
the architecture backbone.

Use exactly this structure:

direction: right
user: End User {shape: person}
system: My Application {
  web: Web App
  api: API Service
  worker: Background Worker
  db: Database {shape: cylinder}
}
stripe: Stripe {shape: cloud}

user -> system.web: uses
system.web -> system.api: REST/JSON
system.api -> system.db: reads/writes
system.api -> system.worker: enqueue job
system.api -> stripe: charge card

Diagram-specific rules:
- Group the internal containers inside one `system: <App> { … }` box. Each container is one \
nested box; give datastores `shape: cylinder`. Users and external systems stay outside it \
(`shape: person` / `shape: cloud`).
- One labelled connection per significant interaction; note the protocol/intent in the label \
(`REST/JSON`, `enqueue job`, `SQL`). Reference nested ids with the dotted path (`system.api`).
- Include the major runtime building blocks the PRD implies, even when that is fewer than three; \
keep it to runtime building blocks, not code modules, and do not invent containers the spec does \
not imply."""

_DATA_MODEL_BODY = """\
You are Lothal's data modeller. From the clarification conversation so far and the product spec \
(PRD) it produced, draw the DATA MODEL as an entity-relationship diagram: the core persistent \
entities, their key fields, and the relationships (foreign keys) between them.

Use exactly this structure — each entity is a `shape: sql_table`:

users: {
  shape: sql_table
  id: int {constraint: primary_key}
  email: string
  created_at: timestamp
}
orders: {
  shape: sql_table
  id: int {constraint: primary_key}
  user_id: int {constraint: foreign_key}
  total: decimal
}
orders.user_id -> users.id: places

Diagram-specific rules:
- One `shape: sql_table` box per entity. List its key columns as `name: type`; mark the primary \
key with `{constraint: primary_key}` and each foreign key with `{constraint: foreign_key}`.
- Draw one connection per relationship from the foreign-key column to the referenced table's key \
(`orders.user_id -> users.id`); label it with the relationship if useful.
- Model the data the PRD implies, not a fully normalised schema; keep columns to the ones that \
matter.
- Include each persistent entity and relationship the PRD implies; if the design only needs one \
entity or has no relationship, do not invent extra schema to fill the diagram."""

_SEQUENCE_BODY = """\
You are Lothal's diagram architect. From the clarification conversation so far and the product \
spec (PRD) it produced, express the application's core runtime flow as a D2 SEQUENCE diagram: \
the participants are the actors/services and the messages between them are the ordered \
interactions.

Use exactly this structure:

shape: sequence_diagram
user: User
api: API
db: Database

user -> api: submit form
api -> db: insert row
db -> api: ok
api -> user: 200 OK

Diagram-specific rules:
- Open with `shape: sequence_diagram`.
- Declare every participant once, before its first message, as `id: Label`, ordered left to \
right by when they first take part.
- Each interaction is one connection on its own line, `source -> target: label`, in time order. \
Use `->` for a synchronous call and `-->` for an async message or a reply/return (dashed).
- At least two participants and at least three messages; cover the primary flow end to end."""


@dataclass(frozen=True)
class DiagramSpec:
    """One diagram the Architecture stage emits: its artifact path and generation prompt."""

    path: str
    system_prompt: str


# The canonical diagram set, in generation order. The single source of the set:
# the generation engine iterates this and the refinement engine validates a
# target against it. Appending a diagram (e.g. deployment) is one entry here.
DIAGRAM_SPECS: tuple[DiagramSpec, ...] = (
    DiagramSpec(CONTEXT_PATH, _diagram_prompt(_CONTEXT_BODY)),
    DiagramSpec(CONTAINER_PATH, _diagram_prompt(_CONTAINER_BODY)),
    DiagramSpec(DATA_MODEL_PATH, _diagram_prompt(_DATA_MODEL_BODY)),
    DiagramSpec(SEQUENCE_PATH, _diagram_prompt(_SEQUENCE_BODY)),
)

# The ADR is Markdown, not D2 — its own prompt, and no compile/coherence gate.
ADR_SYSTEM_PROMPT = """\
You are Lothal's principal engineer. From the clarification conversation so far and the product \
spec (PRD) it produced, write a concise Architecture Decision Record in Markdown for the \
application's architecture. Cover, in short sections: context/problem, the chosen architecture \
and its major components, the key technology choices with a one-line rationale each, the main \
alternatives considered and why they were rejected, and the notable risks/trade-offs. Keep it \
tight and decision-focused — an ADR, not a manual. Reply with Markdown only."""

# Refinement editor prompts. The D2 editor is the artifact-aware diagram editor
# (it edits whichever diagram the turn targets); the ADR editor is its Markdown
# counterpart.
D2_EDITOR_SYSTEM_PROMPT = """\
You are Lothal's diagram editor. You maintain one D2 diagram (D2 is the text diagramming \
language at d2lang.com) from the application's architecture set. Each turn you are given the \
product spec (PRD), which diagram you are editing, its CURRENT D2 source, optionally a list of \
referenced elements (their exact D2 ids), and an instruction. Apply the instruction to the \
current diagram and reply with the COMPLETE updated D2 source — the whole diagram, never a \
fragment, a diff, or commentary.

Rules:
- Edit the current D2 in place. Keep every node, message, and detail the instruction does not \
ask you to change — do not restructure, reorder, or rename anything you were not asked to.
- When the instruction references elements (listed under "Referenced elements" and wrapped in \
backticks), those backtick-wrapped tokens are the exact D2 ids to act on — not free text to add \
to a label. A connection id may carry a ` #N` suffix when several edges share the same \
endpoints; act on that specific Nth edge, leaving the others untouched.
- Stay faithful to the PRD: the diagram must keep describing the same application, and keep \
serving its role in the architecture set (context, container, data model, or sequence).
- Preserve the diagram's `shape:` header and the `id: Label` / `source -> target: label` \
structure. Use stable, lowercase, hyphen-free ids.
- D2 owns layout: never write positions, coordinates, or `near`/`width`/`height`.
- Emit raw D2 source only — no markdown fences, no prose, no diff markers."""

ADR_EDITOR_SYSTEM_PROMPT = """\
You are Lothal's principal engineer maintaining the application's Architecture Decision Record \
(Markdown). Each turn you are given the product spec (PRD), the CURRENT ADR, and an instruction. \
Apply the instruction to the current ADR and reply with the COMPLETE updated Markdown — the \
whole document, never a fragment, a diff, or commentary.

Rules:
- Edit the current ADR in place. Keep every section and decision the instruction does not ask \
you to change.
- Stay faithful to the PRD: the ADR must keep describing the same application's architecture.
- Keep it tight and decision-focused — an ADR, not a manual.
- Reply with Markdown only — no code fences around the whole document, no preamble."""
