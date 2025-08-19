import { PlaygroundComponent } from "@/components/core/playgroundComponent/playground-component";
import {
  SimpleSidebar,
  SimpleSidebarContent,
  useSimpleSidebar,
} from "@/components/ui/simple-sidebar";

export function PlaygroundSidebar(): JSX.Element {
  const { setOpen } = useSimpleSidebar();

  const handleClose = () => {
    setOpen(false);
  };

  return (
    <SimpleSidebar side="right" className="noflow select-none">
      <SimpleSidebarContent className="p-0 flex h-full w-full bg-background">
        <PlaygroundComponent onClose={handleClose} />
      </SimpleSidebarContent>
    </SimpleSidebar>
  );
}
