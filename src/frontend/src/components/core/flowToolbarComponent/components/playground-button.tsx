import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { SimpleSidebarTrigger } from "@/components/ui/simple-sidebar";
import { PLAYGROUND_BUTTON_NAME } from "@/constants/constants";

interface PlaygroundButtonProps {
  hasIO: boolean;
}

const ButtonLabel = () => (
  <span className="font-normal text-mmd">{PLAYGROUND_BUTTON_NAME}</span>
);

const DisabledButton = () => (
  <div
    className="relative inline-flex h-8 w-[7.2rem] items-center justify-start gap-1.5 rounded px-2 text-sm font-normal cursor-not-allowed text-muted-foreground"
    data-testid="playground-btn-flow"
  >
    <ForwardedIconComponent name="PanelRightOpen" className="h-4 w-4" />
    <ButtonLabel />
  </div>
);

const PlaygroundButton = ({ hasIO }: PlaygroundButtonProps) => {
  return hasIO ? (
    <SimpleSidebarTrigger>
      <ButtonLabel />
    </SimpleSidebarTrigger>
  ) : (
    <ShadTooltip content="Add a Chat Input or Chat Output to use the playground">
      <div>
        <DisabledButton />
      </div>
    </ShadTooltip>
  );
};

export default PlaygroundButton;
