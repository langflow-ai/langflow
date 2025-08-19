import { useSimpleSidebar } from "@/components/ui/simple-sidebar";
import { cn } from "@/utils/utils";
import Page from "../PageComponent";

export default function FlowBorderWrapperComponent({
  setIsLoading,
}: {
  setIsLoading: (isLoading: boolean) => void;
}) {
  const { open } = useSimpleSidebar();
  return (
    <main
      className={cn(
        "flex w-full overflow-hidden transition-all duration-300",
        open && "m-2 mr-0 rounded-xl"
      )}
    >
      <div className="h-full w-full relative">
        <Page setIsLoading={setIsLoading} />
      </div>
    </main>
  );
}
