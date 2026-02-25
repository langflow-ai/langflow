import { Checkbox } from "@/components/ui/checkbox";

type FlowAttachItem = {
  id: string;
  name: string;
  updatedDate: string;
};

type StepAttachProps = {
  selectedItems: Set<string>;
  toggleItem: (id: string) => void;
  flows: FlowAttachItem[];
};

export const StepAttach = ({
  selectedItems,
  toggleItem,
  flows,
}: StepAttachProps) => (
  <div className="flex h-full flex-col gap-4">
    <div>
      <h3 className="text-base font-semibold">Attach Flows</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Select one or more flows to include in this deployment
      </p>
    </div>
    <div className="flex flex-col gap-2 overflow-y-auto">
      {flows.map((item) => (
        <button
          key={item.id}
          onClick={() => toggleItem(item.id)}
          className={`flex items-start gap-3 rounded-lg border p-3 text-left transition-colors ${
            selectedItems.has(item.id)
              ? "border-2 border-primary"
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
                Flow
              </span>
            </div>
            <span className="text-xs text-muted-foreground">
              Last updated: {item.updatedDate}
            </span>
          </div>
        </button>
      ))}
      {flows.length === 0 && (
        <p className="text-sm text-muted-foreground">No flows available.</p>
      )}
    </div>
    {selectedItems.size === 0 && (
      <p className="mt-auto text-center text-sm text-muted-foreground">
        Select at least one flow to continue
      </p>
    )}
  </div>
);
