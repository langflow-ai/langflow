import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useFlowAssistantStore } from "@/stores/flowAssistantStore";
import { cn } from "@/utils/utils";

const AssistantIcon = () => (
  <ForwardedIconComponent name="MessageSquareText" className="h-4 w-4" />
);

export default function AssistantButton(): JSX.Element {
  const isOpen = useFlowAssistantStore((s) => s.isOpen);
  const toggle = useFlowAssistantStore((s) => s.toggle);

  return (
    <ShadTooltip content="Assistant (workflow editor)">
      <button
        type="button"
        onClick={toggle}
        className={cn(
          "playground-btn-flow-toolbar hover:bg-accent",
          isOpen && "bg-accent",
        )}
        aria-pressed={isOpen}
      >
        <AssistantIcon />
        <span className="hidden md:block">Assistant</span>
      </button>
    </ShadTooltip>
  );
}
