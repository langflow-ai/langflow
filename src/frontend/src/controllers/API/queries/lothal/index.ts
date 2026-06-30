import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { LothalPhaseId } from "@/pages/lothal/components/phases";
import { api } from "../../api";

// Types use plain names within the `lothal` namespace and mirror the
// `/api/v1/lothal/` contract (api-endpoints.md) exactly. Phase ids are
// declared once — in pages/lothal/components/phases.ts — and re-exported
// here under the contract's name (a type-only import, erased at build).

export type Phase = LothalPhaseId;

export type Project = {
  id: string;
  user_id: string;
  name: string;
  phase: Phase;
  prd_content: string | null;
  // Legacy xyflow graph column, retained for pre-D2 projects until a later
  // column-drop migration (Epic D backfills it into D2 via D.13). No frontend
  // code reads it any more — the diagram is D2 source, fetched via `useDiagram`
  // (GET /diagram). Null for every project created after the D2 pivot.
  diagram_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: string;
  project_id: string;
  role: "USER" | "ASSISTANT";
  content: string;
  suggestions: string[];
  phase: string;
  created_at: string;
};

// --- Diagram (D2 source + server-rendered SVG, Epic D) ----------------------
// The diagram artifact is D2 source text now, not an xyflow graph (Epic D). The
// generator emits D2 (D.2), the backend persists it verbatim and renders it to
// SVG on read (D.3/D.6); `GET /diagram` hands back both. `d2` is `null` once a
// project is past CLARIFICATION but before the generator has emitted anything;
// `svg` is `null` when there is no `d2` or rendering failed. The frontend just
// displays the SVG and ships no D2 compiler of its own.

export type Diagram = {
  d2: string | null;
  svg: string | null;
};

// --- Artifacts (architecture file-map + rendered diagrams, Epic E) ----------
// The ARCHITECTURE stage emits a flat `{path: content}` artifact map (Epic E.3)
// — `adr.md` plus `diagrams/*.d2` — into `lothal_project.artifacts`. `GET
// /artifacts` (Epic E.4) hands that map back as `artifacts`, and server-renders
// every `diagrams/*.d2` entry to SVG in `svgs`, keyed by the same path. The ADR
// is Markdown and has no SVG entry. `artifacts` is `{}` once a project is past
// CLARIFICATION but before the generator has emitted anything; an `svgs` value
// is `null` when its diagram couldn't be rendered (compiler unavailable / render
// failure). The frontend renders the ADR markdown itself and just displays the
// SVGs — it ships no D2 compiler of its own.

export type Artifacts = {
  artifacts: Record<string, string>;
  svgs: Record<string, string | null>;
};

// `POST /diagram/approve` (Epic D.11) advances ARCHITECTURE →
// CODE_GENERATION and returns the project's phase afterwards.
export type DiagramApprove = {
  phase: Phase;
};

// A single generated file. Mirrors `CodeFile` / `CodeResponse` in the contract
// (`langflow/lothal/schemas.py`): `GET /code` returns `{ files: CodeFile[] }`.
export type CodeFile = {
  path: string;
  content: string;
};

const BASE = "/api/v1/lothal/projects/";

const PROJECTS_KEY = ["lothal", "projects"] as const;
// Single-project keys extend PROJECTS_KEY, so list-level invalidations
// (create/delete/chat) cascade to every open single-project query too.
const projectKey = (projectId: string) => [...PROJECTS_KEY, projectId] as const;
const messagesKey = (projectId: string) =>
  ["lothal", "messages", projectId] as const;
const diagramKey = (projectId: string) =>
  ["lothal", "diagram", projectId] as const;
const artifactsKey = (projectId: string) =>
  ["lothal", "artifacts", projectId] as const;
const codeKey = (projectId: string) => ["lothal", "code", projectId] as const;

// Deterministic failures must not be retried — retrying only delays the state
// the UI keys off them: a structured 501 (contract stub), a 403 (phase gate),
// a 404 (missing or foreign project). Real transient failures (network, 5xx)
// still get a couple of attempts.
const retrySkipping =
  (...statuses: number[]) =>
  (count: number, error: unknown): boolean => {
    const status = (error as { response?: { status?: number } })?.response
      ?.status;
    return (status === undefined || !statuses.includes(status)) && count < 2;
  };

const skip501Retry = retrySkipping(501);

// The stub-backed queries (messages/diagram/code) have nothing fresher to
// fetch for minutes at a time — and react-query's default staleTime of 0
// refetches them on every window focus, hammering known-501 endpoints. Once
// live they stay correct: every mutation that changes them invalidates their
// keys, which bypasses staleTime.
const STUB_STALE_MS = 5 * 60 * 1000;

// --- Projects --------------------------------------------------------------

async function listProjects(): Promise<Project[]> {
  const res = await api.get<Project[]>(BASE);
  return res.data;
}

async function createProject(name: string): Promise<Project> {
  const res = await api.post<Project>(BASE, { name });
  return res.data;
}

async function deleteProject(id: string): Promise<void> {
  await api.delete(`${BASE}${id}`);
}

export function useProjects() {
  return useQuery({ queryKey: PROJECTS_KEY, queryFn: listProjects });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKey(id),
    queryFn: async () => {
      const res = await api.get<Project>(`${BASE}${id}`);
      return res.data;
    },
    enabled: id.length > 0,
    // A 404 is deterministic — the project is gone, or another user's.
    retry: retrySkipping(404),
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: PROJECTS_KEY }),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: PROJECTS_KEY }),
  });
}

// --- Messages --------------------------------------------------------------

export function useMessages(projectId: string) {
  return useQuery({
    queryKey: messagesKey(projectId),
    queryFn: async () => {
      const res = await api.get<Message[]>(`${BASE}${projectId}/messages`);
      return res.data;
    },
    // The endpoint is a 501 stub until Epic 1 — don't retry that (the UI keys
    // its NotReady state off the error, and retrying just delays it).
    retry: skip501Retry,
    staleTime: STUB_STALE_MS,
  });
}

// A chat turn. `content` is the message; `artifact` is the active artifact key
// the user is refining in the ARCHITECTURE stage (e.g. `diagrams/context.d2`),
// which routes a refine turn to the right artifact in the map (Epic E.3/E.5).
// Omitted for clarification turns and the first (generation) turn.
export type SendMessageVars = {
  content: string;
  artifact?: string | null;
};

export function useSendMessage(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: SendMessageVars) => {
      const res = await api.post<Message>(`${BASE}${projectId}/chat`, {
        content: vars.content,
        // Only send a target when one is set — the backend defaults a refine
        // with no target to the sequence diagram, and rejects an unknown key.
        ...(vars.artifact ? { artifact: vars.artifact } : {}),
      });
      return res.data;
    },
    onSuccess: () => {
      // The reply may advance the phase or (re)generate the diagram — refresh the
      // conversation, the project list (phase badge), the legacy diagram canvas,
      // and the architecture artifact map (ADR + diagram set).
      qc.invalidateQueries({ queryKey: messagesKey(projectId) });
      qc.invalidateQueries({ queryKey: PROJECTS_KEY });
      qc.invalidateQueries({ queryKey: diagramKey(projectId) });
      qc.invalidateQueries({ queryKey: artifactsKey(projectId) });
    },
  });
}

// --- Diagram ---------------------------------------------------------------

export function useDiagram(projectId: string, enabled = true) {
  return useQuery({
    queryKey: diagramKey(projectId),
    queryFn: async () => {
      const res = await api.get<Diagram>(`${BASE}${projectId}/diagram`);
      return res.data;
    },
    // Phase-gated: the canvas only enables this past CLARIFICATION (no diagram
    // exists before then). The 501 stub (until Epic 2) and the 403 phase gate
    // are both deterministic — the UI keys NotReady off them.
    enabled,
    retry: retrySkipping(501, 403),
    staleTime: STUB_STALE_MS,
  });
}

// The architecture artifact map + rendered diagram SVGs (Epic E.4). Phase-gated
// exactly like `useDiagram`: the ARCHITECTURE-stage pane only enables this past
// CLARIFICATION (no artifacts exist before then). The 403 phase gate is
// deterministic — the UI keys its placeholder/NotReady state off it — and the
// endpoint is live (Epic E.4), but skip a stray 501 too for parity with the
// other stub-era reads.
export function useArtifacts(projectId: string, enabled = true) {
  return useQuery({
    queryKey: artifactsKey(projectId),
    queryFn: async () => {
      const res = await api.get<Artifacts>(`${BASE}${projectId}/artifacts`);
      return res.data;
    },
    enabled,
    retry: retrySkipping(501, 403),
    staleTime: STUB_STALE_MS,
  });
}

// Approve the current diagram (Epic D.11): advances ARCHITECTURE →
// CODE_GENERATION on the server and retains the D2. Invalidates the project
// queries so the phase badge, stepper, and right-pane (canvas → code) update,
// and the diagram + artifact map so the approved output is re-read under the
// new phase.
export function useApproveDiagram(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<DiagramApprove>(
        `${BASE}${projectId}/diagram/approve`,
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PROJECTS_KEY });
      qc.invalidateQueries({ queryKey: diagramKey(projectId) });
      qc.invalidateQueries({ queryKey: artifactsKey(projectId) });
    },
  });
}

// --- Code ------------------------------------------------------------------

// The generated files for a project. A 501 stub until Epic 4 lights up code
// generation; the Code view keys its NotReady state off that. `files` is `[]`
// while generation is in progress.
export function useCode(projectId: string) {
  return useQuery({
    queryKey: codeKey(projectId),
    queryFn: async () => {
      const res = await api.get<{ files: CodeFile[] }>(
        `${BASE}${projectId}/code`,
      );
      return res.data.files;
    },
    retry: skip501Retry,
    staleTime: STUB_STALE_MS,
  });
}

// --- Prototype (Open Design integration, Epic UI) --------------------------
// The PROTOTYPE stage drives Open Design (OD) as a headless prototyping engine.
// `GET /prototype` (Story U.5) returns the run lifecycle status, the OD linkage,
// an embeddable OD URL, and the artifact list; `generate`/`refine`/`approve`
// (U.4/U.6/U.7) drive it. Field names are snake_case on the wire (the rest of
// the Lothal API), mapped to plain names here.

export type PrototypeStatus = "IDLE" | "GENERATING" | "READY" | "APPROVED";

export type PrototypeArtifact = {
  path: string;
  kind: string;
  title: string;
  preview_url: string | null;
};

export type PrototypeState = {
  status: PrototypeStatus;
  od_project_id: string | null;
  od_conversation_id: string | null;
  // The ready-to-iframe OD URL the backend resolves (null until OD is reachable
  // and a public OD base is configured) — kept for an optional "open in OD" link.
  embed_url: string | null;
  // The primary design's HTML, rendered inline in a sandboxed iframe (the design
  // itself, not OD's web UI). Null until a design exists.
  preview_html: string | null;
  artifacts: PrototypeArtifact[];
};

const prototypeKey = (projectId: string) =>
  ["lothal", "prototype", projectId] as const;

// `GET /prototype` (Story U.5). Phase-gated to PROTOTYPE onward: a read before
// then is a deterministic 403 (the UI keys its placeholder/NotReady off it), so
// skip retrying that, the stray 501, and the 409 a wrong-phase action returns.
// Polls while the run is GENERATING so the pane advances to READY (and surfaces
// new artifacts) without a manual refresh; idle otherwise.
export function usePrototype(projectId: string, enabled = true) {
  return useQuery({
    queryKey: prototypeKey(projectId),
    queryFn: async () => {
      const res = await api.get<PrototypeState>(
        `${BASE}${projectId}/prototype`,
      );
      return res.data;
    },
    enabled,
    retry: retrySkipping(501, 403, 409),
    refetchInterval: (query) =>
      query.state.data?.status === "GENERATING" ? 4000 : false,
  });
}

// Start (or reuse) prototype generation (Story U.4). Idempotent on the server —
// a re-entry reuses the existing OD project. Invalidates the prototype state,
// the chat thread (the stage-entry marker, U.10), and the project list (badge).
export function useGeneratePrototype(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<PrototypeState>(
        `${BASE}${projectId}/prototype/generate`,
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: prototypeKey(projectId) });
      qc.invalidateQueries({ queryKey: messagesKey(projectId) });
      qc.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}

// A Lothal-side refine instruction → a new OD run in the same conversation
// (Story U.6). Moves the status back to GENERATING; the polling read picks it up.
// A refine bumps the project's updated_at, so refresh the list ordering too.
export function useRefinePrototype(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (content: string) => {
      const res = await api.post<PrototypeState>(
        `${BASE}${projectId}/prototype/refine`,
        { content },
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: prototypeKey(projectId) });
      qc.invalidateQueries({ queryKey: messagesKey(projectId) });
      qc.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}

// Approve the prototype (Story U.7): the server copies the artifacts, posts a
// chat summary (U.10), and advances PROTOTYPE → CODE_GENERATION. Returns the new
// phase (the `DiagramApprove` shape). Invalidates the project (phase badge,
// stepper, right-pane swap), prototype state, chat thread, and code.
export function useApprovePrototype(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<DiagramApprove>(
        `${BASE}${projectId}/prototype/approve`,
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PROJECTS_KEY });
      qc.invalidateQueries({ queryKey: prototypeKey(projectId) });
      qc.invalidateQueries({ queryKey: messagesKey(projectId) });
      qc.invalidateQueries({ queryKey: codeKey(projectId) });
    },
  });
}

// --- Plan (verification-driven PM tree, Epic U-PLAN) -----------------------
// The PLAN stage is OUR product: its endpoints ARE the canonical Lothal API
// (`/projects/{id}/plan/*`), bridged server-side to the standalone PM service. A
// native pane renders the tree — no iframe. `GET /plan` returns a snapshot (the
// PM tree id, its nodes, and links); mutations add nodes/links and `approve`
// advances PLAN → CODE_GENERATION. Field names are snake_case on the wire.

export type PlanNodeKind = "app" | "component" | "epic" | "story";

export type PlanNode = {
  id: string;
  parent_id: string | null;
  kind: PlanNodeKind;
  state: string;
  name: string;
  depth: number;
};

export type PlanLink = {
  id: string;
  source_id: string;
  target_id: string;
  link_type: string;
};

export type PlanTree = {
  plan_id: string;
  nodes: PlanNode[];
  links: PlanLink[];
};

const planKey = (projectId: string) => ["lothal", "plan", projectId] as const;

// `GET /plan`. Phase-gated to PLAN onward: a read before then is a deterministic
// 403 (the pane keys its NotReady state off it), so skip retrying that, the stray
// 501, and the 409 a wrong-phase write returns.
export function usePlan(projectId: string, enabled = true) {
  return useQuery({
    queryKey: planKey(projectId),
    queryFn: async () => {
      const res = await api.get<PlanTree>(`${BASE}${projectId}/plan`);
      return res.data;
    },
    enabled,
    retry: retrySkipping(501, 403, 409),
  });
}

// Add a node to the tree. Invalidates the plan snapshot so the new node appears.
export function useCreatePlanNode(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      kind: PlanNodeKind;
      name: string;
      parent_id?: string | null;
    }) => {
      const res = await api.post<PlanNode>(
        `${BASE}${projectId}/plan/nodes`,
        body,
      );
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: planKey(projectId) }),
  });
}

// Approve the plan: advances PLAN → CODE_GENERATION. Returns the new phase
// (the `DiagramApprove` shape). Invalidates the project (phase badge, stepper,
// right-pane swap), the plan snapshot, and code.
export function useApprovePlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<DiagramApprove>(
        `${BASE}${projectId}/plan/approve`,
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PROJECTS_KEY });
      qc.invalidateQueries({ queryKey: planKey(projectId) });
      qc.invalidateQueries({ queryKey: codeKey(projectId) });
    },
  });
}
