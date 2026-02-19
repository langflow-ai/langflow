import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ViewType } from "../types";

interface ViewToggleProps {
  view: ViewType;
  setView: (view: ViewType) => void;
}

const VIEW_OPTIONS: { type: ViewType; icon: string }[] = [
  { type: "list", icon: "Menu" },
  { type: "grid", icon: "LayoutGrid" },
];

const ViewToggle = ({ view, setView }: ViewToggleProps) => (
  <div className="relative mr-2 flex h-fit rounded-lg border border-border bg-background">
    <div
      className={`absolute top-[2px] h-[32px] w-8 transform rounded-md bg-muted shadow-sm transition-transform duration-300 ${
        view === "list"
          ? "left-[2px] translate-x-0"
          : "left-[6px] translate-x-full"
      }`}
    />
    {VIEW_OPTIONS.map(({ type, icon }) => (
      <Button
        key={type}
        unstyled
        size="icon"
        className={`group relative z-10 m-[2px] flex-1 rounded-lg p-2 ${
          view === type
            ? "text-foreground"
            : "text-muted-foreground hover:bg-muted"
        }`}
        onClick={() => setView(type)}
      >
        <ForwardedIconComponent
          name={icon}
          aria-hidden="true"
          className="h-4 w-4 group-hover:text-foreground"
        />
      </Button>
    ))}
  </div>
);

export default ViewToggle;
