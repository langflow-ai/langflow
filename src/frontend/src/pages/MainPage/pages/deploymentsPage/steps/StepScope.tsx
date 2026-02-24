import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { VariableScope } from "../constants";

type StepScopeProps = {
  variableScope: VariableScope;
  setVariableScope: (v: VariableScope) => void;
};

export const StepScope = ({
  variableScope,
  setVariableScope,
}: StepScopeProps) => (
  <div className="flex h-full flex-col gap-4">
    <div>
      <h3 className="text-base font-semibold">Variable Scope</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Choose how configs are applied to your attached flows
      </p>
    </div>
    <div className="grid grid-cols-2 gap-3">
      {(
        [
          {
            id: "coarse" as VariableScope,
            label: "Coarse (Shared Config)",
            description:
              "One Config applies to all attached Flows/Snapshots. Simpler mental model, fewer errors.",
          },
          {
            id: "granular" as VariableScope,
            label: "Granular (Per-Flow Config)",
            description:
              "Each Flow can use its own Config. Maximum flexibility where flows need different connections.",
          },
        ] as const
      ).map(({ id, label, description }) => (
        <button
          key={id}
          onClick={() => setVariableScope(id)}
          className={`flex items-start gap-3 rounded-lg border bg-background p-4 text-left transition-colors ${
            variableScope === id
              ? "border-primary"
              : "border-border hover:border-muted-foreground"
          }`}
        >
          <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 border-muted-foreground">
            {variableScope === id && (
              <div className="h-2 w-2 rounded-full bg-foreground" />
            )}
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-sm font-semibold">{label}</span>
            <span className="text-xs text-muted-foreground">{description}</span>
          </div>
        </button>
      ))}
    </div>
    <div className="flex-1 rounded-lg border border-border bg-background p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted">
          <ForwardedIconComponent
            name="ClipboardList"
            className="h-4 w-4 text-muted-foreground"
          />
        </div>
        <span className="text-sm font-semibold">
          Single Shared Configuration
        </span>
      </div>
    </div>
  </div>
);
