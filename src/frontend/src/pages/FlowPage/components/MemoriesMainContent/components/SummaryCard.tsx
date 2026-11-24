import IconComponent from "@/components/common/genericIconComponent";
import { SummaryCardProps } from "../types";

export const SummaryCard = ({ label, value, icon }: SummaryCardProps) => (
  <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-3">
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted">
      <IconComponent name={icon} className="h-4 w-4 text-muted-foreground" />
    </div>
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  </div>
);
