import useFlowStore from "@/stores/flowStore";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";

export default function FlowToolbarOptions() {
  const hasIO = useFlowStore((state) => state.hasIO);

  return (
    <div className="flex items-center gap-1.5">
      <div className="flex h-full w-full gap-1.5 rounded-sm transition-all">
        <PlaygroundButton
          hasIO={hasIO}
        />
      </div>
      <PublishDropdown />
    </div>
  );
}
