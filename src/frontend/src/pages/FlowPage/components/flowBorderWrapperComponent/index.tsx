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
    <>
      <main
        className={cn(
          "flex flex-1 min-w-0 overflow-hidden transition-all duration-300",
          open && "rounded-xl m-2 mr-0"
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
