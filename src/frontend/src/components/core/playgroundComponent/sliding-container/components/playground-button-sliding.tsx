import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  SimpleSidebarTrigger,
  useSimpleSidebar,
} from "@/components/ui/simple-sidebar";
import { PLAYGROUND_BUTTON_NAME } from "@/constants/constants";

interface PlaygroundButtonSlidingProps {
  hasIO: boolean;
}

export function PlaygroundButtonSliding({
  hasIO,
}: PlaygroundButtonSlidingProps) {
  const { open, width } = useSimpleSidebar();
  const iconName = open ? "PanelRightClose" : "Play";

  // Show label when slide container is closed (width === 0px or not open)
  const showLabel = !open || width === 0;

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
            className="playground-slide-icon"
          />
          <span className="hidden md:block">{PLAYGROUND_BUTTON_NAME}</span>
        </div>
      </ShadTooltip>
    );
  }

  return (
    <SimpleSidebarTrigger
      data-testid="playground-btn-flow-io-sliding"
      className="playground-btn-flow-toolbar hover:bg-accent cursor-pointer"
    >
      <ForwardedIconComponent
        name={iconName}
        className="playground-slide-icon"
      />
      {showLabel && (
        <span className="hidden md:block">{PLAYGROUND_BUTTON_NAME}</span>
      )}
    </SimpleSidebarTrigger>
  );
}
