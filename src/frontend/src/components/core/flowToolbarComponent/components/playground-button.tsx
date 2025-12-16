import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";

// import { CustomIOModal } from "@/customization/components/custom-new-modal";

import { PLAYGROUND_BUTTON_NAME } from "@/constants/constants";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { usePlaygroundStore } from "@/stores/playgroundStore";

interface PlaygroundButtonProps {
  hasIO: boolean;
}

const PlayIcon = ({
  icon,
  className,
}: {
  icon: string;
  className?: string;
}) => (
  <ForwardedIconComponent
    name={icon}
    className={className}
    strokeWidth={ENABLE_PUBLISH ? 2 : 1.5}
  />
);

const ButtonLabel = () => (
  <span className="hidden md:block">{PLAYGROUND_BUTTON_NAME}</span>
);

const ActiveButton = ({
  icon,
  showLabel,
  iconClass,
}: {
  icon: string;
  showLabel: boolean;
  iconClass: string;
}) => (
  <div
    data-testid="playground-btn-flow-io"
    className="playground-btn-flow-toolbar hover:bg-accent !px-2 !py-1 !gap-1"
  >
    <PlayIcon icon={icon} className={iconClass} />
    {showLabel && <ButtonLabel />}
  </div>
);

const DisabledButton = () => (
  <div
    className="playground-btn-flow-toolbar cursor-not-allowed text-muted-foreground duration-150 !px-2 !py-1 !gap-1"
    data-testid="playground-btn-flow"
  >
    <PlayIcon icon="Play" className="h-4 w-4 transition-all" />
    <ButtonLabel />
  </div>
);

const PlaygroundButton = ({ hasIO }: PlaygroundButtonProps) => {
  const setIsOpen = usePlaygroundStore((state) => state.setIsOpen);
  const setIsFullscreen = usePlaygroundStore((state) => state.setIsFullscreen);
  const isOpen = usePlaygroundStore((state) => state.isOpen);

  const handleToggle = () => {
    // TODO: will be revert - bypass legacy modal and open sliding container
    const next = !isOpen;
    setIsFullscreen(false);
    setIsOpen(next);
  };

  // Match mini_playground: keep the close icon in both states; hide label when open.
  const iconName = "PanelRightClose";
  const iconClass = isOpen
    ? "h-3.5 w-3.5 transition-all"
    : "h-4 w-4 transition-all";
  const showLabel = !isOpen;

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
        onClick={handleToggle}
        data-testid="playground-btn-flow-io-sliding"
        className={`playground-btn-flow-toolbar hover:bg-accent cursor-pointer ${
          isOpen ? "!p-0 !w-auto" : "!px-2 !py-1 !gap-1"
        }`}
        style={{
          width: isOpen ? "auto" : "fit-content",
          minWidth: 32,
          height: 32,
        }}
      >
        <ActiveButton
          icon={iconName}
          showLabel={showLabel}
          iconClass={iconClass}
        />
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
