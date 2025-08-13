import { HeaderButton } from "./components/header-button";

export function PlaygroundHeader({ onClose }: { onClose?: () => void }) {
  return (
    <div className="flex items-center justify-between gap-2 px-4 py-2">
      <div className="flex items-center gap-2">
        <div className="truncate text-sm font-medium text-secondary-foreground">
          Flow run{" "}
          {new Date().toLocaleDateString("en-US", {
            month: "2-digit",
            day: "2-digit",
          })}{" "}
          {new Date().toLocaleTimeString("en-US", { hour12: false })}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <HeaderButton icon="Plus" onClick={() => {}} />
        <HeaderButton icon="History" onClick={() => {}} />
        <HeaderButton icon="ExternalLink" onClick={() => {}} />
        <HeaderButton icon="MoreHorizontal" onClick={() => {}} />
        {onClose && <HeaderButton icon="X" onClick={onClose} />}
      </div>
    </div>
  );
}
