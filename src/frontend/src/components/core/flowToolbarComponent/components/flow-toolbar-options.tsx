import useFlowStore from "@/stores/flowStore";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";

export default function FlowToolbarOptions() {
  const hasIO = useFlowStore((state) => state.hasIO);

  return (
    <div className="flex items-center gap-1">
      <PlaygroundButton hasIO={hasIO} />
      <PublishDropdown />
    </div>
  );
}
