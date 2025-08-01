import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useSidebar } from "@/components/ui/sidebar";
import { PLAYGROUND_BUTTON_NAME } from "@/constants/constants";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { useCallback } from "react";

interface PlaygroundButtonProps {
  hasIO: boolean;
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

const ActiveButton = ({ onClick }: { onClick: (e: React.MouseEvent<HTMLDivElement> ) => void }) => (
  <div
    data-testid="playground-btn-flow-io"
    className="playground-btn-flow-toolbar hover:bg-accent cursor-pointer" role="button" onClick={onClick}
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
}: PlaygroundButtonProps) => {
  const { toggleSidebar } = useSidebar();

  const handleClick = useCallback(
    (_: React.MouseEvent<HTMLDivElement>) => {
      toggleSidebar();
    },
    [toggleSidebar],
  );
  return hasIO ? (
    <ActiveButton onClick={handleClick} />
  ) : (
    <ShadTooltip content="Add a Chat Input or Chat Output to use the playground">
      <div>
        <DisabledButton />
      </div>
    </ShadTooltip>
  );
};

export default PlaygroundButton;
