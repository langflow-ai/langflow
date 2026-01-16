import ForwardedIconComponent from "@/components/common/genericIconComponent";

export const LoadingIndicator = () => {
  return (
    <div className="flex items-center gap-2 py-1 font-mono text-sm text-muted-foreground">
      <ForwardedIconComponent
        name="Loader2"
        className="h-3.5 w-3.5 animate-spin"
      />
      <span>Processing...</span>
    </div>
  );
};
