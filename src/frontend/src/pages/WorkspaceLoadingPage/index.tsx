import { ProgressBar as LoadingComponent } from "@/components/common/progressBar";
import { cn } from "@/utils/utils";

export function WorkspaceLoadingPage({ overlay = false }: { overlay?: boolean }) {
  return (
    <div
      className={cn(
        "flex h-screen w-screen flex-col items-center justify-center gap-6 bg-background text-center",
        overlay && "fixed left-0 top-0 z-[999]",
      )}
    >
      <p className="max-w-md text-lg font-medium text-muted-foreground">
        Hang in tight. Setting up things for you...
      </p>
      <LoadingComponent remSize={50} />
    </div>
  );
}
