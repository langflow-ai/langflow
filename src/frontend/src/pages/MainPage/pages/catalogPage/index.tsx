import { useMemo, useState } from "react";
import {
  cancelMCPJob,
  type MCPJob,
  type MCPJobStatus,
  useListMCPJobs,
} from "@/controllers/API/queries/mcp-jobs/use-list-mcp-jobs";

type CatalogTab = "tools" | "skills" | "events";

interface TabButtonProps {
  active: boolean;
  label: string;
  onClick: () => void;
}

function TabButton({ active, label, onClick }: TabButtonProps) {
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
        No MCP job events. Long-running tool invocations will appear here.
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

function PlaceholderTab({ label }: { label: string }) {
  return (
    <div className="p-8 text-center text-muted-foreground">
      {label} catalog is not yet wired up. See
      <code className="mx-1 px-1 bg-muted rounded">
        docs/Agents/mcp-catalog-and-long-running.mdx
      </code>
      for the data model.
    </div>
  );
}

export default function CatalogPage() {
  const [tab, setTab] = useState<CatalogTab>("events");
  const [search, setSearch] = useState("");
  const { data, isLoading, refetch } = useListMCPJobs({ limit: 100 });
  const jobs = data ?? [];

  const handleCancel = async (jobId: string): Promise<void> => {
    try {
      await cancelMCPJob(jobId);
      await refetch();
    } catch (_error: unknown) {
      // Refetch surfaces the unchanged state; explicit toast left for follow-up
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
            onClick={() => setTab("events")}
          />
        </div>
        <input
          type="search"
          placeholder="Search…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="my-3 px-3 py-1 text-sm rounded border bg-background w-64"
        />
      </div>
      <main className="flex-1 overflow-auto p-6">
        {tab === "events" && (
          <EventsTab
            jobs={jobs}
            loading={isLoading}
            search={search}
            onCancel={handleCancel}
          />
        )}
        {tab === "tools" && <PlaceholderTab label="Tools" />}
        {tab === "skills" && <PlaceholderTab label="Skills" />}
      </main>
    </div>
  );
}
