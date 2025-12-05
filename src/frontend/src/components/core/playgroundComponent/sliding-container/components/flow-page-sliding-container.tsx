import { useSlidingContainerStore } from "../stores/sliding-container-store";

// Placeholder content for sliding container
// This will be replaced with ChatHeader in the next PR
function SlidingContainerPlaceholder() {
  return (
    <div className="h-full w-full bg-background border-l border-transparent shadow-lg flex items-center justify-center">
      <p className="text-muted-foreground">
        Sliding container - content coming soon
      </p>
    </div>
  );
}

export function FlowPageSlidingContainerContent() {
  return <SlidingContainerPlaceholder />;
}
