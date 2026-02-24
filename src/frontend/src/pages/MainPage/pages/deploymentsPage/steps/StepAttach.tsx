import { Checkbox } from "@/components/ui/checkbox";
import { ATTACH_TABS, type AttachTab } from "../constants";

type FlowAttachItem = {
  id: string;
  name: string;
  updatedDate: string;
  snapshotDate: string | null;
};

type SnapshotAttachItem = {
  id: string;
  name: string;
  updatedDate: string;
};

type StepAttachProps = {
  attachTab: AttachTab;
  setAttachTab: (v: AttachTab) => void;
  selectedItems: Set<string>;
  toggleItem: (id: string) => void;
  flows: FlowAttachItem[];
  snapshots: SnapshotAttachItem[];
};

export const StepAttach = ({
  attachTab,
  setAttachTab,
  selectedItems,
  toggleItem,
  flows,
  snapshots,
}: StepAttachProps) => (
  <div className="flex h-full flex-col gap-4">
    <div>
      <h3 className="text-base font-semibold">Attach Flows or Snapshots</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Select one or more flows or snapshots to include in this deployment
      </p>
    </div>
    <div className="flex border-b border-border">
      {ATTACH_TABS.map((tab) => (
        <button
          key={tab}
          onClick={() => setAttachTab(tab)}
          className={`px-4 pb-2 text-sm font-medium transition-colors ${
            attachTab === tab
              ? "border-b-2 border-foreground text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {tab}
        </button>
      ))}
    </div>
    <div className="flex flex-col gap-2 overflow-y-auto">
      {(attachTab === "Flows" ? flows : snapshots).map((item) => (
        <button
          key={item.id}
          onClick={() => toggleItem(item.id)}
          className={`flex items-start gap-3 rounded-lg border bg-background p-3 text-left transition-colors ${
            selectedItems.has(item.id)
              ? "border-primary"
              : "border-border hover:border-muted-foreground"
          }`}
        >
          <Checkbox
            checked={selectedItems.has(item.id)}
            className="mt-0.5 pointer-events-none"
          />
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">{item.name}</span>
              <span className="inline-flex items-center rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                {attachTab === "Flows" ? "Flow" : "Snapshot"}
              </span>
            </div>
            <span className="text-xs text-muted-foreground">
              Last updated: {item.updatedDate}
              {"snapshotDate" in item && item.snapshotDate
                ? ` • Snapshot available (${item.snapshotDate})`
                : ""}
            </span>
          </div>
        </button>
      ))}
      {attachTab === "Flows" && flows.length === 0 && (
        <p className="text-sm text-muted-foreground">No flows available.</p>
      )}
      {attachTab === "Snapshots" && snapshots.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No snapshots available for this provider.
        </p>
      )}
    </div>
    {selectedItems.size === 0 && (
      <p className="mt-auto text-center text-sm text-muted-foreground">
        Select at least one flow or snapshot to continue
      </p>
    )}
  </div>
);
