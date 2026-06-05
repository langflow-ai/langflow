import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  type Project,
  useCreateProject,
  useDeleteProject,
  useProjects,
} from "@/controllers/API/queries/lothal";

const PHASE_LABELS: Record<string, string> = {
  CLARIFICATION: "Clarifying",
  DIAGRAM_GENERATION: "Generating Diagram",
  DIAGRAM_REFINEMENT: "Refining Diagram",
  CODE_GENERATION: "Generating Code",
  DONE: "Done",
};

const PHASE_COLORS: Record<string, string> = {
  CLARIFICATION: "bg-blue-100 text-blue-700",
  DIAGRAM_GENERATION: "bg-yellow-100 text-yellow-700",
  DIAGRAM_REFINEMENT: "bg-purple-100 text-purple-700",
  CODE_GENERATION: "bg-orange-100 text-orange-700",
  DONE: "bg-green-100 text-green-700",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function NewProjectModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (name: string) => void;
}) {
  const [name, setName] = useState("");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          New Project
        </h2>
        <Input
          autoFocus
          placeholder="Project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) =>
            e.key === "Enter" && name.trim() && onCreate(name.trim())
          }
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!name.trim()} onClick={() => onCreate(name.trim())}>
            Create
          </Button>
        </div>
      </div>
    </div>
  );
}

function ProjectCard({
  project,
  onDelete,
}: {
  project: Project;
  onDelete: (id: string) => void;
}) {
  const navigate = useNavigate();
  const phaseLabel = PHASE_LABELS[project.phase] ?? project.phase;
  const phaseColor = PHASE_COLORS[project.phase] ?? "bg-gray-100 text-gray-600";

  return (
    <div
      role="button"
      tabIndex={0}
      className="group flex cursor-pointer flex-col gap-3 rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
      onClick={() => navigate(`/lothal/${project.id}`)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          navigate(`/lothal/${project.id}`);
        }
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent
            name="FolderOpen"
            className="h-5 w-5 text-gray-400"
          />
          <span className="font-medium text-gray-900">{project.name}</span>
        </div>
        <button
          className="invisible rounded p-1 text-gray-400 hover:text-red-500 group-hover:visible"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(project.id);
          }}
        >
          <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
        </button>
      </div>
      <div className="flex items-center justify-between">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${phaseColor}`}
        >
          {phaseLabel}
        </span>
        <span className="text-xs text-gray-400">
          {formatDate(project.updated_at)}
        </span>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [showModal, setShowModal] = useState(false);
  const { data: projects, isLoading } = useProjects();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();

  const handleCreate = (name: string) => {
    createProject.mutate(name, { onSuccess: () => setShowModal(false) });
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-gray-200 px-8 py-5">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Lothal</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Describe what you want to build — get a diagram, then code.
          </p>
        </div>
        <Button onClick={() => setShowModal(true)} className="gap-2">
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          New Project
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        {/* Hero Section */}
        <div className="mb-8 rounded-2xl border bg-gradient-to-r from-blue-50 to-purple-50 p-6">
          <h2 className="text-3xl font-bold">Build Software with AI 🚀</h2>
          <p className="mt-2 text-gray-600">
            Describe your idea, refine diagrams, and generate production-ready
            code.
          </p>
        </div>
        {isLoading ? (
          <div className="flex h-40 items-center justify-center text-sm text-gray-400">
            Loading…
          </div>
        ) : !projects?.length ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <ForwardedIconComponent
              name="Sparkles"
              className="h-10 w-10 text-gray-300"
            />
            <p className="text-sm text-gray-500">
              No projects yet. Create one to get started.
            </p>
            <Button
              variant="outline"
              onClick={() => setShowModal(true)}
              className="gap-2"
            >
              <ForwardedIconComponent name="Plus" className="h-4 w-4" />
              New Project
            </Button>
          </div>
        ) : (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <p className="text-sm text-gray-500">Total Projects</p>
                <p className="mt-2 text-3xl font-bold">
                  {projects?.length ?? 0}
                </p>
              </div>

              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <p className="text-sm text-gray-500">Active Projects</p>
                <p className="mt-2 text-3xl font-bold">
                  {projects?.filter((p) => p.phase !== "DONE").length ?? 0}
                </p>
              </div>

              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <p className="text-sm text-gray-500">Completed</p>
                <p className="mt-2 text-3xl font-bold">
                  {projects?.filter((p) => p.phase === "DONE").length ?? 0}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((p) => (
                <ProjectCard
                  key={p.id}
                  project={p}
                  onDelete={(id) => deleteProject.mutate(id)}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {showModal && (
        <NewProjectModal
          onClose={() => setShowModal(false)}
          onCreate={handleCreate}
        />
      )}
    </div>
  );
}
