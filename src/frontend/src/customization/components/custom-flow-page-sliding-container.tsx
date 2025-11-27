import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useSlidingContainerStore } from "../stores/sliding-container-store";

export function FlowPageSlidingContainerContent() {
  const isFullscreen = useSlidingContainerStore((state) => state.isFullscreen);
  const toggleFullscreen = useSlidingContainerStore(
    (state) => state.toggleFullscreen,
  );

  return (
    <div className="h-full w-full bg-background border-l shadow-lg flex flex-col">
      <div className="flex items-center justify-end p-4 border-b">
        <button
          onClick={toggleFullscreen}
          className="p-2 hover:bg-accent rounded transition-colors"
          title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
        >
          <ForwardedIconComponent
            name={isFullscreen ? "Shrink" : "Expand"}
            className="h-4 w-4"
          />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-6">
        {/* Content will be added here */}
      </div>
    </div>
  );
}
