import { Separator } from "@/components/ui/separator";
import { HeaderButton } from "../playgroundHeader/components/header-button";

export default function SessionSidebar() {
  return (
    <>
      <div className="flex flex-col h-full w-[200px] p-4">
        <div className="flex w-full items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground">
            Sessions
          </span>
          <HeaderButton icon="Plus" />
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground">
              Session 1
            </span>
          </div>
        </div>
      </div>
      <Separator orientation="vertical" className="shrink-0" />
    </>
  );
}
