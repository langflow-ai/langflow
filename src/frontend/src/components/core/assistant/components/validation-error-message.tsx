import ForwardedIconComponent from "@/components/common/genericIconComponent";

export const ValidationErrorMessage = () => {
  return (
    <div className="flex items-center gap-2 font-mono text-sm">
      <ForwardedIconComponent
        name="XCircle"
        className="h-4 w-4 text-destructive"
      />
      <span className="text-destructive">Validation failed</span>
    </div>
  );
};
