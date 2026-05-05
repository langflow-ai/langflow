import IconComponent from "@/components/common/genericIconComponent";

export const NoMemorySelected = () => (
  <div className="flex h-full w-full flex-col items-center justify-center text-center">
    <IconComponent
      name="Brain"
      className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
    />
    <p className="text-sm text-muted-foreground">No memory selected</p>
    <p className="mt-1 text-xs text-muted-foreground">
      Select a memory from the sidebar to view details
    </p>
  </div>
);
