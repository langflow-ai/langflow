import {
  SimpleSidebar,
  SimpleSidebarContent,
  useSimpleSidebar,
} from "@/components/ui/simple-sidebar";
import { PlaygroundComponent } from "@/components/core/playgroundComponent/playground-component";

export function PlaygroundSidebar(): JSX.Element {
  const { setOpen } = useSimpleSidebar();

  const handleClose = () => {
    setOpen(false);
  };

  return (
    <SimpleSidebar side="right" className="noflow select-none border-l">
      <SimpleSidebarContent className="p-0 flex h-full w-full bg-background">
        <PlaygroundComponent onClose={handleClose} />
      </SimpleSidebarContent>
    </SimpleSidebar>
  );
}
