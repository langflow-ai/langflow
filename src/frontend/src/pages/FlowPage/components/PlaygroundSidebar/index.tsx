import {
  SimpleSidebar,
  SimpleSidebarContent,
  SimpleSidebarHeader,
  useSimpleSidebar,
} from "@/components/ui/simple-sidebar";
import { PlaygroundComponent } from "@/components/core/playgroundComponent/playground-component";
import { PlaygroundHeader } from "@/components/core/playgroundComponent/components/playgroundHeader/playground-header";

export function PlaygroundSidebar(): JSX.Element {
  const { setOpen } = useSimpleSidebar();

  const handleClose = () => {
    setOpen(false);
  };

  return (
    <SimpleSidebar side="right" className="noflow select-none border-l">
      <SimpleSidebarHeader className="px-4 py-2 overflow-hidden w-full">
        <PlaygroundHeader onClose={handleClose} />
      </SimpleSidebarHeader>

      <SimpleSidebarContent className="p-0 flex h-full w-full bg-background">
        <PlaygroundComponent />
      </SimpleSidebarContent>
    </SimpleSidebar>
  );
}
