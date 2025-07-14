import LoadingComponent from "@/components/common/loadingComponent";
import { cn } from "@/utils/utils";

export function LoadingPage({ overlay = false }: { overlay?: boolean }) {
  return (
    <div
      className={cn(
        "bg-background flex h-screen w-screen items-center justify-center",
        overlay && "fixed top-0 left-0 z-999",
      )}
    >
      <LoadingComponent remSize={50} />
    </div>
  );
}
