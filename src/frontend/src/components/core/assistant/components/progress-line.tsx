import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import type { ProgressMetadata } from "../assistant.types";

type ProgressLineProps = {
  content: string;
  progress: ProgressMetadata;
};

export const ProgressLine = ({ content, progress }: ProgressLineProps) => {
  return (
    <div className={cn("flex items-center gap-2 py-1 font-mono text-sm", progress.color)}>
      <ForwardedIconComponent
        name={progress.icon}
        className={cn("h-3.5 w-3.5 shrink-0", progress.spin && "animate-spin")}
      />
      <span>{content}</span>
    </div>
  );
};
