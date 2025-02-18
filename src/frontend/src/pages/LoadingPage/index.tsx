import LoadingComponent from "@/components/common/loadingComponent";
import { cn } from "@/utils/utils";

export function LoadingPage({ overlay = false }: { overlay?: boolean }) {
  return (
    <div
      className={cn(
        "flex h-screen w-screen items-center justify-center bg-background",
        overlay && "fixed left-0 top-0 z-999",
      )}
    >
      <LoadingComponent remSize={50} />
    </div>
  );
}
