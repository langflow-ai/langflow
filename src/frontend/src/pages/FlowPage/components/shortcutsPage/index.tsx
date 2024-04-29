


import ForwardedIconComponent from "../../../../components/genericIconComponent";
import ShortcutsComponent from "../../../../components/shortcutsComponent";
import { Button } from "../../../../components/ui/button";

export default function ShortcutsPage() {
  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="text-xl font-bold tracking-tight">Shortcuts</h2>
          <p className="text-muted-foreground">
            Manage and assign global shortcuts
          </p>
        </div>
      </div>

      <div className="flex h-full w-full flex-col justify-between">
        <ShortcutsComponent />
      </div>
    </div>
  );
}
