// The Workspace's right pane during the PROTOTYPE stage (Epic UI, Stories
// U.8/U.9). Lothal drives Open Design (OD) as a headless prototyping engine: on
// entry the architecture-approved project is seeded into OD and a run starts
// (U.4). This pane embeds OD's own project page directly — the user gets OD's
// full UI (its chat history, edit tools, live preview) inside Lothal and refines
// there — then Approves to advance to code generation (U.7), which copies the
// artifacts into the Lothal project.
//
// OD's web UI normally bounces first-run visitors to an onboarding / "Sign in to
// Open Design Cloud" chooser. The generate step pre-completes that on OD's daemon
// (`onboardingCompleted` + a pinned local agent, see lothal/prototype.py), so the
// embedded deep-link lands straight on the project page with no prompts.
//
// States:
//   not PROTOTYPE phase   → nothing (the Workspace only mounts this in PROTOTYPE)
//   loading               → "opening" line
//   501 (stub)            → NotReady ("not live yet")
//   other error           → NotReady ("couldn't load")
//   IDLE                  → auto-trigger generation, show "starting" placeholder
//   GENERATING (no embed) → "building" placeholder
//   embed available       → OD's project page embedded; Approve advances the stage

import { type ReactNode, useEffect, useRef, useState } from "react";
import type { Project } from "@/controllers/API/queries/lothal";
import {
  type PrototypeArtifact,
  useApprovePrototype,
  useGeneratePrototype,
  usePrototype,
} from "@/controllers/API/queries/lothal";
import { Button } from "./Button";
import { isNotImplemented, NotReady } from "./NotReady";

function PaneLoading({ label }: { label: string }) {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 13,
        color: "var(--ink-soft)",
      }}
    >
      {label}
    </div>
  );
}

// The pre-ready placeholder: a calm "we're working on it" surface with pulsing
// dots, shown while OD seeds the project before the embed becomes available.
function BuildingPlaceholder({ title, sub }: { title: string; sub: string }) {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 14,
        padding: "0 32px",
        textAlign: "center",
      }}
    >
      <div style={{ display: "inline-flex", gap: 6 }}>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="pulse"
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--accent)",
              animationDelay: `${i * 0.18}s`,
            }}
          />
        ))}
      </div>
      <div
        className="serif"
        style={{ fontSize: 20, color: "var(--ink)", fontStyle: "italic" }}
      >
        {title}
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-soft)", maxWidth: 420 }}>
        {sub}
      </div>
    </div>
  );
}

// OD's own project page, embedded. This is OD's full web UI (chat, tools, live
// preview) deep-linked to this project; onboarding is pre-completed on the daemon
// so it renders the project directly. It's our own trusted OD instance, so the
// frame runs unsandboxed — OD needs its own origin (cookies/storage) and scripts
// to function, and sandboxing it without same-origin would break the app.
function OdFrame({ url }: { url: string }) {
  return (
    <iframe
      title="Open Design prototype"
      src={url}
      style={{
        width: "100%",
        height: "100%",
        border: "none",
        display: "block",
        background: "#fff",
      }}
    />
  );
}

// The finished prototype itself — the captured design HTML, rendered in a
// SANDBOXED frame (no same-origin, so it can't touch the app) with none of OD's
// editing chrome. This is what a read-only revisit of an approved prototype
// shows: just the built screen.
function PreviewFrame({ html }: { html: string }) {
  return (
    <iframe
      title="Prototype preview"
      srcDoc={html}
      sandbox="allow-scripts allow-forms"
      style={{
        width: "100%",
        height: "100%",
        border: "none",
        display: "block",
        background: "#fff",
      }}
    />
  );
}

// Fallback when OD can't be embedded (no public OD base configured): list the
// produced artifacts with any preview links, so the pane is still useful.
function ArtifactList({ artifacts }: { artifacts: PrototypeArtifact[] }) {
  if (artifacts.length === 0) {
    return (
      <BuildingPlaceholder
        title="No prototype artifacts yet"
        sub="Open Design hasn't produced any files for this prototype yet. They'll appear here as it works."
      />
    );
  }
  return (
    <div
      style={{ height: "100%", overflowY: "auto", padding: "18px var(--pad)" }}
    >
      <ul
        style={{
          listStyle: "none",
          margin: 0,
          padding: 0,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {artifacts.map((a) => (
          <li
            key={a.path}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              padding: "10px 12px",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
            }}
          >
            <span
              style={{ display: "flex", flexDirection: "column", minWidth: 0 }}
            >
              <span style={{ fontSize: 13, color: "var(--ink)" }}>
                {a.title}
              </span>
              <span
                className="mono"
                style={{ fontSize: 11, color: "var(--ink-soft)" }}
              >
                {a.kind} · {a.path}
              </span>
            </span>
            {a.preview_url && (
              <a
                href={a.preview_url}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: 12,
                  color: "var(--accent)",
                  whiteSpace: "nowrap",
                }}
              >
                Open preview ↗
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

// Phases in which the approved prototype stays readable — mirrors the backend
// `_PROTOTYPE_VISIBLE_PHASES`. Lets a later stage browse back to the prototype.
const PROTOTYPE_VISIBLE = new Set([
  "PROTOTYPE",
  "PLAN",
  "CODE_GENERATION",
  "DONE",
]);

export function PrototypePane({ project }: { project: Project }) {
  // Editing/approving the prototype is live only during PROTOTYPE; from PLAN
  // onward the pane is a read-only review of the approved prototype.
  const inPrototype = project.phase === "PROTOTYPE";
  const { data, isLoading, isError, error } = usePrototype(
    project.id,
    PROTOTYPE_VISIBLE.has(project.phase),
  );
  const generate = useGeneratePrototype(project.id);
  const approve = useApprovePrototype(project.id);

  const status = data?.status;

  // Auto-seed on entry: once the read reports IDLE (architecture just approved,
  // nothing started yet) kick off generation a single time. The ref guards
  // against re-firing across the renders the invalidation/poll triggers.
  const seededRef = useRef(false);
  useEffect(() => {
    seededRef.current = false;
  }, [project.id]);
  useEffect(() => {
    // Only auto-seed while the project is actually in PROTOTYPE — browsing back
    // to a read-only prototype from a later phase must not kick off generation.
    if (inPrototype && status === "IDLE" && !seededRef.current) {
      seededRef.current = true;
      generate.mutate();
    }
  }, [inPrototype, status, generate]);

  // Latch a successful approve so a second click can't 409 against the now
  // CODE_GENERATION phase in the window before the project refetch swaps the pane.
  const [approved, setApproved] = useState(false);
  const [approveFailed, setApproveFailed] = useState(false);
  useEffect(() => {
    setApproved(false);
    setApproveFailed(false);
  }, [project.id]);

  const onApprove = async () => {
    if (approve.isPending || approved) return;
    setApproveFailed(false);
    try {
      await approve.mutateAsync();
      setApproved(true);
    } catch {
      setApproveFailed(true);
    }
  };

  // --- States --------------------------------------------------------------

  if (isLoading) {
    return <PaneLoading label="Opening the prototype…" />;
  }
  if (isError) {
    return isNotImplemented(error) ? (
      <NotReady title="The prototype isn't live yet" error={error} />
    ) : (
      <NotReady
        title="Couldn't load the prototype"
        detail="Something went wrong reaching the prototype engine. Try again in a moment."
      />
    );
  }

  // The auto-seed kick (IDLE → generate) failed. Without this the pane would sit
  // on "Starting…" forever — the read stays IDLE, the seed is latched so it won't
  // re-fire, and the polling read only advances once a run exists. Surface the
  // failure with a manual retry.
  if (status === "IDLE" && generate.isError) {
    return (
      <NotReady
        title="Couldn't start the prototype"
        detail="The prototype engine couldn't be reached to begin generation. Try again in a moment."
        action={
          <Button variant="accent" onClick={() => generate.mutate()}>
            Retry
          </Button>
        }
      />
    );
  }

  const artifacts = data?.artifacts ?? [];
  const embedUrl = data?.embed_url ?? null;
  const previewHtml = data?.preview_html ?? null;
  const isBuilding = status === "IDLE" || status === "GENERATING";

  // Read-only revisit (the project has moved past PROTOTYPE): show the FINISHED
  // prototype — the captured design itself, sandboxed, with none of OD's editing
  // chrome — rather than the live OD editor. Falls back to the artifact list, then
  // a clear "nothing was captured" note (e.g. an old prototype approved with no
  // built design).
  let body: ReactNode;
  if (!inPrototype) {
    body = previewHtml ? (
      <PreviewFrame html={previewHtml} />
    ) : artifacts.length > 0 ? (
      <ArtifactList artifacts={artifacts} />
    ) : (
      <BuildingPlaceholder
        title="No prototype to show"
        sub="This stage has no captured prototype — it was approved before a design was built. Re-enter the prototype stage to build one."
      />
    );
  } else {
    // Live PROTOTYPE stage: OD's own project page, embedded, so the user can
    // answer the design brief, iterate, and refine. Falls back to a building
    // placeholder (no public OD base) then the artifact list.
    body = embedUrl ? (
      <OdFrame url={embedUrl} />
    ) : isBuilding ? (
      <BuildingPlaceholder
        title={
          status === "IDLE"
            ? "Starting your prototype…"
            : "Building your prototype…"
        }
        sub="Lothal is generating an interactive UI/UX prototype from your approved architecture. This can take a little while — it'll appear here when it's ready."
      />
    ) : (
      <ArtifactList artifacts={artifacts} />
    );
  }

  const canApprove = inPrototype;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      <div style={{ flex: 1, minHeight: 0 }}>{body}</div>

      {canApprove && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            padding: "10px var(--pad)",
            borderTop: "1px solid var(--border)",
            background: "var(--paper)",
          }}
        >
          {/* You edit + refine inside the embedded Open Design above (its own
              chat + tools); "Open in new tab" is just a full-screen convenience. */}
          {embedUrl ? (
            <a
              href={embedUrl}
              target="_blank"
              rel="noreferrer"
              style={{
                fontSize: 13,
                color: "var(--ink-soft)",
                whiteSpace: "nowrap",
              }}
            >
              Open in new tab ↗
            </a>
          ) : (
            <span />
          )}
          <span
            style={{ display: "inline-flex", alignItems: "center", gap: 12 }}
          >
            {approveFailed && (
              <span style={{ fontSize: 12, color: "var(--warn)" }}>
                Couldn’t approve just now — try again.
              </span>
            )}
            <Button
              variant="accent"
              onClick={onApprove}
              disabled={approve.isPending || approved}
            >
              {approve.isPending || approved
                ? "Approving…"
                : "Approve & generate code"}
            </Button>
          </span>
        </div>
      )}
    </div>
  );
}
