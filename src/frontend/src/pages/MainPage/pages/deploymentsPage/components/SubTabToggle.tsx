import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

type SubTabToggleProps = {
  activeSubTab: "deployments" | "providers";
  onChangeSubTab: (tab: "deployments" | "providers") => void;
  showCreateButtons?: boolean;
};

export const SubTabToggle = ({
  activeSubTab,
  onChangeSubTab,
  showCreateButtons = true,
}: SubTabToggleProps) => {
  return (
    <div className="flex items-center justify-between gap-4 pb-3">
      <div className="inline-flex items-center rounded-md border border-border bg-background p-1">
        <button
          type="button"
          onClick={() => onChangeSubTab("deployments")}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            activeSubTab === "deployments"
              ? "bg-muted text-primary shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Deployments
        </button>
        <button
          type="button"
          onClick={() => onChangeSubTab("providers")}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            activeSubTab === "providers"
              ? "bg-muted text-primary shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Deployment Providers
        </button>
      </div>
      {showCreateButtons && (
        <Button size="sm">
          <ForwardedIconComponent name="plus" />
          New {activeSubTab === "deployments" ? "Deployment" : "Provider"}
        </Button>
      )}
    </div>
  );
};
