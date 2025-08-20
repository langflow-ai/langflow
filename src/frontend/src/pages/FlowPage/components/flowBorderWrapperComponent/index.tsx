import { useSimpleSidebar } from "@/components/ui/simple-sidebar";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { cn } from "@/utils/utils";
import Page from "../PageComponent";
import { PlaygroundSidebar } from "../PlaygroundSidebar";

export default function FlowBorderWrapperComponent({
  setIsLoading,
}: {
  setIsLoading: (isLoading: boolean) => void;
}) {
  const { open } = useSimpleSidebar();
  const isFullscreen = usePlaygroundStore((state) => state.isFullscreen);
  return (
    <>
      <main
        className={cn(
          "flex flex-1 min-w-0 overflow-hidden transition-all duration-300",
          open && !isFullscreen && "rounded-xl m-2 mr-0"
        )}
      >
        <div className="h-full w-full relative">
          <Page setIsLoading={setIsLoading} />
        </div>
      </main>
      <PlaygroundSidebar />
    </>
  );
}
