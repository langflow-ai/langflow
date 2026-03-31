import IconComponent from "@/components/common/genericIconComponent";

export const NoMemorySelected = () => (
  <div
    className="flex h-full w-full flex-col items-center justify-center text-center"
    role="status"
    aria-live="polite"
    aria-atomic="true"
    aria-labelledby="no-memory-selected-title"
    aria-describedby="no-memory-selected-description"
  >
    <span aria-hidden="true">
      <IconComponent
        name="Brain"
        className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
      />
    </span>
    <p id="no-memory-selected-title" className="text-sm text-muted-foreground">
      No memory selected
    </p>
    <p
      id="no-memory-selected-description"
      className="mt-1 text-xs text-muted-foreground"
    >
      Select a memory from the sidebar to view details
    </p>
  </div>
);
