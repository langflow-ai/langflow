import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
// import { CustomIOModal } from "@/customization/components/custom-new-modal";
import { useSlidingContainerStore } from "@/components/core/playgroundComponent/sliding-container/stores/sliding-container-store";
import { PLAYGROUND_BUTTON_NAME } from "@/constants/constants";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";

interface PlaygroundButtonProps {
  hasIO: boolean;
  open?: boolean;
  setOpen?: (open: boolean) => void;
  canvasOpen?: boolean;
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

const PlaygroundButton = ({ hasIO }: PlaygroundButtonProps) => {
  const setIsOpen = useSlidingContainerStore((state) => state.setIsOpen);
  const setIsFullscreen = useSlidingContainerStore(
    (state) => state.setIsFullscreen,
  );

  const handleOpen = () => {
    // TODO: will be revert - bypass legacy modal and open sliding container
    setIsFullscreen(false);
    setIsOpen(true);
  };

  return hasIO ? (
    <>
      {/* TODO: will be revert - legacy modal implementation kept for reference
      <CustomIOModal
        open={open}
        setOpen={setOpen}
        disable={!hasIO}
        canvasOpen={canvasOpen}
      >
        <ActiveButton />
      </CustomIOModal>
      */}
      <div
        onClick={handleOpen}
        data-testid="playground-btn-flow-io-sliding"
        className="playground-btn-flow-toolbar hover:bg-accent cursor-pointer"
      >
        <ActiveButton />
      </div>
    </>
  ) : (
    <ShadTooltip content="Add a Chat Input or Chat Output to use the playground">
      <div>
        <DisabledButton />
      </div>
    </ShadTooltip>
  );
};

export default PlaygroundButton;
