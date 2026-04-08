import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

export type DeploymentSubTab = "deployments" | "providers";

interface SubTabToggleProps {
  activeTab: DeploymentSubTab;
  onTabChange: (tab: DeploymentSubTab) => void;
}

const tabs: { value: DeploymentSubTab; label: string }[] = [
  { value: "deployments", label: "Deployments" },
  { value: "providers", label: "Deployment Providers" },
];

export default function SubTabToggle({
  activeTab,
  onTabChange,
}: SubTabToggleProps) {
  return (
    <div className="flex gap-0.5 rounded-lg border border-border p-0.5">
      {tabs.map((tab) => (
        <Button
          key={tab.value}
          unstyled
          data-testid={`subtab-${tab.value}`}
          onClick={() => onTabChange(tab.value)}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            activeTab === tab.value
              ? "bg-muted text-foreground hover:bg-muted/80"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {tab.label}
        </Button>
      ))}
    </div>
  );
}
