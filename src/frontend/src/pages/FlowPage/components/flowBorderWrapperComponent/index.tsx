import { useSimpleSidebar } from "@/components/ui/simple-sidebar";
import { cn } from "@/utils/utils";
import Page from "../PageComponent";
import { PlaygroundSidebar } from "../PlaygroundSidebar";

export default function FlowBorderWrapperComponent({
  setIsLoading,
}: {
  setIsLoading: (isLoading: boolean) => void;
}) {
  const { open } = useSimpleSidebar();
  return (
    <div
      className={cn(
        "transition-all duration-300 flex h-full w-full",
        open && "p-2"
      )}
    >
      <main
        className={cn(
          "flex w-full overflow-hidden transition-all duration-300",
          open && "rounded-xl"
        )}
      >
        <div className="h-full w-full relative">
          <Page setIsLoading={setIsLoading} />
        </div>
      </main>
      <PlaygroundSidebar />
    </div>
  );
}
