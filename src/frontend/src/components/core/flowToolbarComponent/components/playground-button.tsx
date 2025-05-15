import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { PLAYGROUND_BUTTON_NAME } from "@/constants/constants";
import { CustomIOModal } from "@/customization/components/custom-new-modal";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";

interface PlaygroundButtonProps {
  hasIO: boolean;
  open: boolean;
  setOpen: (open: boolean) => void;
  canvasOpen: boolean;
}

const PlayIcon = () => (
  <ForwardedIconComponent
    name="Play"
    className="h-4 w-4 transition-all"
    strokeWidth={ENABLE_PUBLISH ? 2 : 1.5}
  />
);

const ButtonLabel = () => (
  <span className="hidden md:block">{PLAYGROUND_BUTTON_NAME}</span>
);

const ActiveButton = () => (
  <div
    data-testid="playground-btn-flow-io"
    className="playground-btn-flow-toolbar hover:bg-accent"
  >
    <PlayIcon />
    <ButtonLabel />
  </div>
);

const DisabledButton = () => (
  <div
    className="playground-btn-flow-toolbar cursor-not-allowed text-muted-foreground duration-150"
    data-testid="playground-btn-flow"
  >
    <PlayIcon />
    <ButtonLabel />
  </div>
);

const PlaygroundButton = ({
  hasIO,
  open,
  setOpen,
  canvasOpen,
}: PlaygroundButtonProps) => {
  return hasIO ? (
    <CustomIOModal
      open={open}
      setOpen={setOpen}
      disable={!hasIO}
      canvasOpen={canvasOpen}
    >
      <ActiveButton />
    </CustomIOModal>
  ) : (
    <ShadTooltip content="Add a Chat Input or Chat Output to use the playground">
      <div>
        <DisabledButton />
      </div>
    </ShadTooltip>
  );
};

export default PlaygroundButton;
