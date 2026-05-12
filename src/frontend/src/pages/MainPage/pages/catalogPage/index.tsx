import { useMemo, useState } from "react";
import {
  cancelMCPJob,
  type MCPJob,
  type MCPJobStatus,
  useListMCPJobs,
} from "@/controllers/API/queries/mcp-jobs/use-list-mcp-jobs";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import type { FlowType } from "@/types/flow";

type CatalogTab = "tools" | "skills" | "events";

interface TabButtonProps {
  active: boolean;
  label: string;
  count?: number;
  onClick: () => void;
}

function TabButton({ active, label, count, onClick }: TabButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "px-4 py-2 text-sm font-medium border-b-2 -mb-px " +
        (active
          ? "border-primary text-primary"
          : "border-transparent text-muted-foreground hover:text-foreground")
      }
    >
      {label}
      {typeof count === "number" && (
        <span className="ml-2 px-1.5 py-0.5 rounded bg-muted text-xs">
          {count}
        </span>
      )}
    </button>
  );
}

interface StatusBadgeProps {
  status: MCPJobStatus;
}

function StatusBadge({ status }: StatusBadgeProps) {
  const colorMap: Record<MCPJobStatus, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    running: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    cancelled: "bg-gray-100 text-gray-800",
  };
  return (
    <span
      className={
        "inline-block px-2 py-0.5 rounded text-xs font-medium " +
        colorMap[status]
      }
    >
      {status}
    </span>
  );
}

interface ToolRow {
  flow_id: string;
  name: string;
  description: string;
  project_id: string | undefined;
  project_name: string;
  long_running: boolean;
}

interface ToolsTabProps {
  tools: ToolRow[];
  search: string;
}

function ToolsTab({ tools, search }: ToolsTabProps) {
  const filtered = useMemo(() => {
    if (!search) return tools;
    const needle = search.toLowerCase();
    return tools.filter(
      (t) =>
        t.name.toLowerCase().includes(needle) ||
        t.description.toLowerCase().includes(needle) ||
        t.project_name.toLowerCase().includes(needle),
    );
  }, [tools, search]);

  if (filtered.length === 0) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        No MCP tools yet. Toggle <code>mcp_enabled</code> on a flow from the MCP
        Server page to expose it as a tool.
      </div>
    );
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground border-b">
          <th className="py-2 px-3">Tool</th>
          <th className="py-2 px-3">Description</th>
          <th className="py-2 px-3">Project</th>
          <th className="py-2 px-3">Long-running</th>
        </tr>
      </thead>
      <tbody>
        {filtered.map((tool) => (
          <tr key={tool.flow_id} className="border-b hover:bg-muted/30">
            <td className="py-2 px-3 font-medium">{tool.name}</td>
            <td className="py-2 px-3 text-muted-foreground">
              {tool.description || (
                <span className="italic text-muted-foreground/60">
                  No description
                </span>
              )}
            </td>
            <td className="py-2 px-3 text-muted-foreground">
              {tool.project_name}
            </td>
            <td className="py-2 px-3">
              {tool.long_running ? (
                <span className="inline-block px-2 py-0.5 rounded bg-blue-100 text-blue-800 text-xs font-medium">
                  yes
                </span>
              ) : (
                <span className="text-muted-foreground/60 text-xs">no</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface EventsTabProps {
  jobs: MCPJob[];
  loading: boolean;
  search: string;
  onCancel: (jobId: string) => Promise<void>;
}

function EventsTab({ jobs, loading, search, onCancel }: EventsTabProps) {
  const filtered = useMemo(() => {
    if (!search) return jobs;
    const needle = search.toLowerCase();
    return jobs.filter(
      (j) =>
        j.tool_name.toLowerCase().includes(needle) ||
        j.id.toLowerCase().includes(needle),
    );
  }, [jobs, search]);

  if (loading) {
    return <div className="p-4 text-muted-foreground">Loading…</div>;
  }
  if (filtered.length === 0) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        No MCP job events. Long-running tool invocations will appear here as
        soon as a flow marked <code>long_running</code> is called over MCP.
      </div>
    );
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground border-b">
          <th className="py-2 px-3">Job ID</th>
          <th className="py-2 px-3">Tool</th>
          <th className="py-2 px-3">Status</th>
          <th className="py-2 px-3">Progress</th>
          <th className="py-2 px-3">Created</th>
          <th className="py-2 px-3"></th>
        </tr>
      </thead>
      <tbody>
        {filtered.map((job) => (
          <tr key={job.id} className="border-b hover:bg-muted/30">
            <td className="py-2 px-3 font-mono text-xs">
              {job.id.slice(0, 8)}…
            </td>
            <td className="py-2 px-3">{job.tool_name}</td>
            <td className="py-2 px-3">
              <StatusBadge status={job.status} />
            </td>
            <td className="py-2 px-3">{job.progress}%</td>
            <td className="py-2 px-3 text-xs text-muted-foreground">
              {new Date(job.created_at).toLocaleString()}
            </td>
            <td className="py-2 px-3 text-right">
              {(job.status === "pending" || job.status === "running") && (
                <button
                  type="button"
                  className="text-xs text-red-600 hover:underline"
                  onClick={() => {
                    void onCancel(job.id);
                  }}
                >
                  Cancel
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SkillsTab() {
  return (
    <div className="p-8 text-center text-muted-foreground">
      <p className="mb-2">Skills are not yet wired up.</p>
      <p className="text-xs">
        Once the FastMCP Server component publishes resources with the
        <code className="mx-1 px-1 bg-muted rounded">
          application/vnd.langflow.skill+json
        </code>
        mime type, they'll appear here.
      </p>
    </div>
  );
}

function buildToolRows(
  flows: FlowType[] | null | undefined,
  folderNames: Map<string, string>,
): ToolRow[] {
  if (!flows) return [];
  return flows
    .filter((f) => f.mcp_enabled === true)
    .map((f) => ({
      flow_id: f.id,
      name: f.action_name || f.name,
      description: f.action_description || f.description || "",
      project_id: f.folder_id,
      project_name: f.folder_id ? folderNames.get(f.folder_id) || "—" : "—",
      long_running: Boolean(f.long_running),
    }));
}

export default function CatalogPage() {
  const [tab, setTab] = useState<CatalogTab>("tools");
  const [search, setSearch] = useState("");

  const flows = useFlowsManagerStore((state) => state.flows);
  const folders = useFolderStore((state) => state.folders);

  const folderNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const f of folders) {
      if (f.id) map.set(f.id, f.name);
    }
    return map;
  }, [folders]);

  const tools = useMemo(
    () => buildToolRows(flows, folderNames),
    [flows, folderNames],
  );

  const { data, isLoading, refetch } = useListMCPJobs({ limit: 100 });
  const jobs = data ?? [];

  const handleCancel = async (jobId: string): Promise<void> => {
    try {
      await cancelMCPJob(jobId);
      await refetch();
    } catch (_error: unknown) {
      await refetch();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <header className="border-b px-6 py-4">
        <h1 className="text-xl font-semibold">MCP Catalog</h1>
        <p className="text-sm text-muted-foreground">
          Tools, skills, and long-running events across your projects.
        </p>
      </header>
      <div className="border-b px-6 flex items-end justify-between">
        <div className="flex gap-2">
          <TabButton
            active={tab === "tools"}
            label="Tools"
            count={tools.length}
            onClick={() => setTab("tools")}
          />
          <TabButton
            active={tab === "skills"}
            label="Skills"
            onClick={() => setTab("skills")}
          />
          <TabButton
            active={tab === "events"}
            label="Events"
            count={jobs.length}
            onClick={() => setTab("events")}
          />
        </div>
        <input
          type="search"
          placeholder="Search…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="my-3 px-3 py-1 text-sm rounded border bg-background w-64"
          data-testid="catalog-search"
        />
      </div>
      <main className="flex-1 overflow-auto p-6">
        {tab === "tools" && <ToolsTab tools={tools} search={search} />}
        {tab === "skills" && <SkillsTab />}
        {tab === "events" && (
          <EventsTab
            jobs={jobs}
            loading={isLoading}
            search={search}
            onCancel={handleCancel}
          />
        )}
      </main>
    </div>
  );
}
