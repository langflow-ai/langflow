import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { PLAYGROUND_BUTTON_NAME } from "@/constants/constants";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { useSlidingContainerStore } from "@/customization/stores/sliding-container-store";

interface PlaygroundButtonSlidingProps {
  hasIO: boolean;
}

const STROKE_WIDTH = ENABLE_PUBLISH ? 2 : 1.5;
const ICON_CLASS = "h-4 w-4 transition-all flex-shrink-0";

const ButtonLabel = () => (
  <span className="hidden md:block">{PLAYGROUND_BUTTON_NAME}</span>
);

export function PlaygroundButtonSliding({
  hasIO,
}: PlaygroundButtonSlidingProps) {
  const toggle = useSlidingContainerStore((state) => state.toggle);
  const isOpen = useSlidingContainerStore((state) => state.isOpen);
  const iconName = isOpen ? "PanelRightClose" : "Play";

  if (!hasIO) {
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
          <ButtonLabel />
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
      <ButtonLabel />
    </div>
  );
}
