// Lothal dashboard (Story B.2) — the dockyard's front desk. Rebuilt onto the
// B.1 design system: a themed surface with a harbor watermark, an editorial
// hero, a stats row, and a phase-aware grid of project cards. Wired to the
// live project CRUD (`useProjects` / `useCreateProject` / `useDeleteProject`).

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  type Project,
  useCreateProject,
  useDeleteProject,
  useProjects,
} from "@/controllers/API/queries/lothal";
import useAuthStore from "@/stores/authStore";
import {
  Button,
  EmptyHint,
  HarborWatermark,
  LOTHAL_VERSION,
  LothalMark,
  phaseStatus,
  StatusDot,
  TopBar,
} from "../components";
import { LothalSurface, useLothalTheme } from "../theme/LothalSurface";

// The API serialises naive UTC timestamps (no offset); treat them as UTC so the
// browser doesn't shift them by its own local offset.
function toDate(iso: string): Date {
  const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasTz ? iso : `${iso}Z`);
}

function formatDate(iso: string) {
  return toDate(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Relative within a week ("just now", "2 hours ago", "yesterday", "3 days
// ago"); an absolute date beyond that. Deliberately not moment.fromNow():
// the design wants this exact copy plus the absolute-date switch after a
// week, which fromNow doesn't do — moment.utc would only cover the TZ half.
function relativeTime(iso: string): string {
  const diffMs = Date.now() - toDate(iso).getTime();
  const min = Math.floor(diffMs / 60_000);
  const hr = Math.floor(min / 60);
  const day = Math.floor(hr / 24);
  if (min < 1) return "just now";
  if (min < 60) return `${min} minute${min === 1 ? "" : "s"} ago`;
  if (hr < 24) return `${hr} hour${hr === 1 ? "" : "s"} ago`;
  if (day === 1) return "yesterday";
  if (day < 7) return `${day} days ago`;
  return formatDate(iso);
}

function PlusGlyph({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M8 3v10M3 8h10"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

// --- New-project modal -------------------------------------------------------

function NewProjectModal({
  busy,
  error,
  onClose,
  onCreate,
}: {
  busy: boolean;
  error?: string | null;
  onClose: () => void;
  onCreate: (name: string) => void;
}) {
  const [name, setName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const trimmed = name.trim();

  // Focus the field on open and close on Escape.
  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      {/* Dimmed backdrop — a button so click-to-dismiss stays keyboard-accessible. */}
      <button
        type="button"
        aria-label="Close dialog"
        onClick={onClose}
        style={{
          position: "absolute",
          inset: 0,
          border: "none",
          padding: 0,
          background: "rgba(20, 0, 13, 0.55)",
          cursor: "default",
        }}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="New project"
        style={{
          position: "relative",
          zIndex: 1,
          width: "100%",
          maxWidth: 420,
          background: "var(--paper)",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--radius-lg)",
          padding: 22,
          boxShadow: "0 18px 50px rgba(0, 0, 0, 0.35)",
        }}
      >
        <h2 className="serif" style={{ fontSize: 23, marginBottom: 4 }}>
          New project
        </h2>
        <p style={{ fontSize: 13, color: "var(--ink-mute)", marginBottom: 16 }}>
          Name your build — you can describe it in detail once it’s open.
        </p>
        <input
          ref={inputRef}
          aria-label="Project name"
          placeholder="e.g. Tide Tracker"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && trimmed && !busy) onCreate(trimmed);
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "var(--accent)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "var(--border-strong)";
          }}
          style={{
            width: "100%",
            height: 40,
            padding: "0 12px",
            background: "var(--surface)",
            color: "var(--ink)",
            border: "1px solid var(--border-strong)",
            borderRadius: 8,
            fontFamily: "var(--sans)",
            fontSize: 14,
            outline: "none",
          }}
        />
        {error && (
          <p
            role="alert"
            style={{ marginTop: 12, fontSize: 13, color: "#e5484d" }}
          >
            {error}
          </p>
        )}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            marginTop: 18,
          }}
        >
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="accent"
            disabled={!trimmed || busy}
            onClick={() => onCreate(trimmed)}
          >
            {busy ? "Creating…" : "Create"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// --- Cards -------------------------------------------------------------------

function NewProjectTile({ onClick }: { onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
        minHeight: 156,
        borderRadius: "var(--radius-lg)",
        border: `1.5px dashed ${hover ? "var(--accent)" : "var(--border-strong)"}`,
        background: hover ? "var(--accent-soft)" : "transparent",
        color: hover ? "var(--ink)" : "var(--ink-mute)",
        cursor: "pointer",
        fontFamily: "var(--sans)",
        transition:
          "border-color .15s ease, background .15s ease, color .15s ease",
      }}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 38,
          height: 38,
          borderRadius: "50%",
          border: "1px solid var(--border-strong)",
          color: "var(--ink-mute)",
        }}
      >
        <PlusGlyph size={16} />
      </span>
      <span className="serif" style={{ fontSize: 17, fontStyle: "italic" }}>
        Start a new project
      </span>
      <span className="mono" style={{ fontSize: 11, color: "var(--ink-soft)" }}>
        N
      </span>
    </button>
  );
}

function ProjectCard({
  project,
  onOpen,
  onDelete,
}: {
  project: Project;
  onOpen: () => void;
  onDelete: () => void;
}) {
  const [hover, setHover] = useState(false);
  // The card-footer line. The design shows turns/commits here, but those
  // counts aren't on the project list yet, so we surface the phase-derived
  // status from the shared phase metadata.
  const status = phaseStatus(project.phase);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        // Only open from the card itself — ignore Enter/Space bubbling up from
        // a nested control (e.g. the delete button activated by keyboard).
        if (e.target !== e.currentTarget) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: 172,
        padding: 18,
        borderRadius: "var(--radius-lg)",
        background: "var(--surface)",
        border: `1px solid ${hover ? "var(--border-strong)" : "var(--border)"}`,
        cursor: "pointer",
        transform: hover ? "translateY(-2px)" : "translateY(0)",
        boxShadow: hover ? "0 12px 28px rgba(0, 0, 0, 0.22)" : "none",
        transition:
          "transform .12s ease, box-shadow .15s ease, border-color .15s ease",
      }}
    >
      {/* Top row: phase status (left) · timestamp + delete (right) */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
        }}
      >
        <StatusDot phase={project.phase} />
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            className="mono"
            style={{ fontSize: 11, color: "var(--ink-soft)" }}
          >
            {relativeTime(project.updated_at)}
          </span>
          <button
            type="button"
            aria-label={`Delete ${project.name}`}
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            style={{
              flexShrink: 0,
              display: "inline-flex",
              padding: 2,
              border: "none",
              background: "transparent",
              color: "var(--ink-soft)",
              cursor: "pointer",
              opacity: hover ? 1 : 0,
              transition: "opacity .15s ease, color .15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--accent)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--ink-soft)";
            }}
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden
            >
              <path
                d="M3 4h10M6.5 4V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1M5 4l.5 9a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1L11 4"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Project name */}
      <span
        className="serif"
        style={{
          marginTop: 14,
          fontSize: 21,
          lineHeight: 1.15,
          color: "var(--ink)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {project.name}
      </span>

      {/* Footer: a phase-appropriate status line, pinned to the card's base */}
      <div
        style={{
          marginTop: "auto",
          paddingTop: 12,
          borderTop: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 7,
          fontSize: 12,
        }}
      >
        {status.action && (
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "var(--accent)",
            }}
          />
        )}
        <span
          style={{ color: status.action ? "var(--accent)" : "var(--ink-soft)" }}
        >
          {status.text}
        </span>
      </div>
    </div>
  );
}

// --- Page --------------------------------------------------------------------

function DashboardView() {
  const navigate = useNavigate();
  const { theme } = useLothalTheme();
  const username = useAuthStore((s) => s.userData?.username);
  const initial = username ? username.charAt(0).toUpperCase() : "";
  const [showModal, setShowModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const { data: projects, isLoading, isError, refetch } = useProjects();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();

  const list = projects ?? [];
  const total = list.length;
  const underway = list.filter((p) => p.phase !== "DONE").length;
  const delivered = list.filter((p) => p.phase === "DONE").length;

  const openModal = () => {
    setCreateError(null);
    setShowModal(true);
  };

  // "N" opens the new-project modal (the dashboard advertises this shortcut).
  // Ignored while typing in a field, with a modifier held, or when the modal
  // is already open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "n" && e.key !== "N") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      if (
        el &&
        (el.tagName === "INPUT" ||
          el.tagName === "TEXTAREA" ||
          el.isContentEditable)
      ) {
        return;
      }
      if (showModal) return;
      e.preventDefault();
      setCreateError(null);
      setShowModal(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showModal]);

  const handleCreate = (name: string) => {
    setCreateError(null);
    createProject.mutate(name, {
      onSuccess: (created) => {
        setShowModal(false);
        navigate(`/lothal/${created.id}`);
      },
      onError: () => {
        setCreateError("Couldn’t create the project. Please try again.");
      },
    });
  };

  const handleDelete = (project: Project) => {
    // Deletion is irreversible and there's no undo — confirm first.
    if (window.confirm(`Delete “${project.name}”? This cannot be undone.`)) {
      deleteProject.mutate(project.id);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <TopBar
        left={
          <span
            style={{ display: "inline-flex", alignItems: "center", gap: 10 }}
          >
            <span style={{ color: "var(--accent)" }}>
              <LothalMark size={22} />
            </span>
            <span className="serif" style={{ fontSize: 22 }}>
              Lothal
            </span>
            <span
              className="mono"
              style={{ fontSize: 11, color: "var(--ink-soft)" }}
            >
              v{LOTHAL_VERSION}
            </span>
          </span>
        }
        right={
          <span
            style={{ display: "inline-flex", alignItems: "center", gap: 18 }}
          >
            <span style={{ fontSize: 13.5, color: "var(--ink-mute)" }}>
              Docs
            </span>
            <span style={{ fontSize: 13.5, color: "var(--ink-mute)" }}>
              Settings
            </span>
            <span
              aria-label={username ? `Account: ${username}` : "Account"}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 30,
                height: 30,
                borderRadius: "50%",
                background: "var(--accent)",
                color: "var(--accent-fg)",
                fontSize: 12.5,
                fontWeight: 600,
              }}
            >
              {initial}
            </span>
          </span>
        }
      />

      <main
        style={{
          position: "relative",
          flex: 1,
          overflowY: "auto",
        }}
      >
        <HarborWatermark
          style={{ color: "var(--ink)" }}
          opacity={theme === "dark" ? 0.08 : 0.06}
        />

        <div
          style={{
            position: "relative",
            zIndex: 1,
            minHeight: "100%",
            boxSizing: "border-box",
            maxWidth: 1040,
            margin: "0 auto",
            padding: "32px 28px 40px",
            display: "flex",
            flexDirection: "column",
            gap: 28,
          }}
        >
          {/* Hero */}
          <section style={{ maxWidth: 660 }}>
            <div className="label" style={{ color: "var(--accent)" }}>
              Your workshop
            </div>
            <h1
              className="serif"
              style={{
                marginTop: 10,
                fontSize: 44,
                lineHeight: 1.1,
                letterSpacing: "-0.01em",
              }}
            >
              Describe it.{" "}
              <span style={{ fontStyle: "italic", color: "var(--ink-soft)" }}>
                Shape it.
              </span>{" "}
              Ship it.
            </h1>
            <p
              style={{
                marginTop: 14,
                fontSize: 15,
                lineHeight: 1.6,
                color: "var(--ink-mute)",
              }}
            >
              Lothal turns a conversation into a sequence diagram, then into a
              working codebase. No assumptions. Every project starts with the
              same patient questions until what you mean and what gets built are
              the same thing.
            </p>
            <div
              style={{
                marginTop: 20,
                display: "flex",
                gap: 10,
                flexWrap: "wrap",
              }}
            >
              <Button variant="accent" size="lg" onClick={openModal}>
                <PlusGlyph size={16} />
                New project
              </Button>
              <Button variant="outline" size="lg" onClick={openModal}>
                Import a spec
              </Button>
            </div>
          </section>

          {/* Projects */}
          <section
            style={{ display: "flex", flexDirection: "column", gap: 16 }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                gap: 16,
                flexWrap: "wrap",
                borderBottom: "1px solid var(--border)",
                paddingBottom: 12,
              }}
            >
              <h2 className="serif" style={{ fontSize: 22 }}>
                Projects
              </h2>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 18,
                  fontSize: 13,
                }}
              >
                <span
                  style={{
                    color: "var(--ink)",
                    borderBottom: "1px solid var(--ink)",
                    paddingBottom: 3,
                  }}
                >
                  All · {total}
                </span>
                <span style={{ color: "var(--ink-soft)" }}>
                  In progress · {underway}
                </span>
                <span style={{ color: "var(--ink-soft)" }}>
                  Delivered · {delivered}
                </span>
              </div>
            </div>

            {isLoading ? (
              <div
                style={{
                  padding: 40,
                  textAlign: "center",
                  fontSize: 13,
                  color: "var(--ink-soft)",
                }}
              >
                Loading the harbor…
              </div>
            ) : isError ? (
              <div
                role="alert"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 16,
                  padding: "16px 0 8px",
                }}
              >
                <EmptyHint
                  title="Couldn’t reach the harbor"
                  sub="We couldn’t load your projects. Check your connection and try again."
                />
                <Button variant="outline" onClick={() => refetch()}>
                  Try again
                </Button>
              </div>
            ) : total === 0 ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 16,
                  padding: "16px 0 8px",
                }}
              >
                <EmptyHint
                  title="No vessels in the harbor"
                  sub="Describe what you want to build and a new project takes shape here."
                  kbd="N to start"
                />
                <Button variant="accent" onClick={openModal}>
                  <PlusGlyph />
                  New project
                </Button>
              </div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(248px, 1fr))",
                  gap: 16,
                }}
              >
                {list.map((p) => (
                  <ProjectCard
                    key={p.id}
                    project={p}
                    onOpen={() => navigate(`/lothal/${p.id}`)}
                    onDelete={() => handleDelete(p)}
                  />
                ))}
                <NewProjectTile onClick={openModal} />
              </div>
            )}
          </section>

          {/* Footer */}
          <footer
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              flexWrap: "wrap",
              marginTop: "auto",
              paddingTop: 20,
              borderTop: "1px solid var(--border)",
            }}
          >
            <span style={{ fontSize: 13, color: "var(--ink-soft)" }}>
              Lothal turns intent into implementation, one diagram at a time.
            </span>
            <span
              className="mono"
              style={{ fontSize: 11.5, color: "var(--ink-soft)" }}
            >
              built on langflow
            </span>
          </footer>
        </div>
      </main>

      {showModal && (
        <NewProjectModal
          busy={createProject.isPending}
          error={createError}
          onClose={() => setShowModal(false)}
          onCreate={handleCreate}
        />
      )}
    </div>
  );
}

export default function Dashboard() {
  return (
    <LothalSurface>
      <DashboardView />
    </LothalSurface>
  );
}
