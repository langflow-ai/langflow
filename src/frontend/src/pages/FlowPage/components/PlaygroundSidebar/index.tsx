import { PlaygroundComponent } from "@/components/core/playgroundComponent/playground-component";
import {
  SimpleSidebar,
  SimpleSidebarContent,
} from "@/components/ui/simple-sidebar";

export function PlaygroundSidebar(): JSX.Element {
  return (
    <SimpleSidebar side="right" className="noflow select-none">
      <SimpleSidebarContent className={"flex h-full w-full bg-background"}>
        <PlaygroundComponent />
      </SimpleSidebarContent>
    </SimpleSidebar>
  );
}
