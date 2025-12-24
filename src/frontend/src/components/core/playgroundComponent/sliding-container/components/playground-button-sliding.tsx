import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { PLAYGROUND_BUTTON_NAME } from "@/constants/constants";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { useSlidingContainerStore } from "../stores/sliding-container-store";

interface PlaygroundButtonSlidingProps {
  hasIO: boolean;
}

const STROKE_WIDTH = ENABLE_PUBLISH ? 2 : 1.5;
const ICON_CLASS = "h-4 w-4 transition-all flex-shrink-0";

export function PlaygroundButtonSliding({
  hasIO,
}: PlaygroundButtonSlidingProps) {
  const toggle = useSlidingContainerStore((state) => state.toggle);
  const isOpen = useSlidingContainerStore((state) => state.isOpen);
  const width = useSlidingContainerStore((state) => state.width);
  const iconName = isOpen ? "PanelRightClose" : "Play";

  // Show label when slide container is closed (width === 0px or not open)
  const showLabel = !isOpen || width === 0;

  if (!hasIO) {
    // For disabled state, always show label since container can't be opened
    return (
      <ShadTooltip content="Add a Chat Input or Chat Output to use the playground">
        <div
          className="playground-btn-flow-toolbar cursor-not-allowed text-muted-foreground duration-150"
          data-testid="playground-btn-flow-sliding"
        >
          <ForwardedIconComponent
            name="Play"
            className={ICON_CLASS}
            strokeWidth={STROKE_WIDTH}
          />
          <span className="hidden md:block">{PLAYGROUND_BUTTON_NAME}</span>
        </div>
      </ShadTooltip>
    );
  }

  return (
    <div
      onClick={toggle}
      data-testid="playground-btn-flow-io-sliding"
      className="playground-btn-flow-toolbar hover:bg-accent cursor-pointer"
    >
      <ForwardedIconComponent
        name={iconName}
        className={ICON_CLASS}
        strokeWidth={STROKE_WIDTH}
      />
      {showLabel && (
        <span className="hidden md:block">{PLAYGROUND_BUTTON_NAME}</span>
      )}
    </div>
  );
}
