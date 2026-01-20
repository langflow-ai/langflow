import ForwardedIconComponent from "@/components/common/genericIconComponent";

type LoadingIndicatorProps = {
  text: string;
};

export const LoadingIndicator = ({ text }: LoadingIndicatorProps) => {
  return (
    <div className="flex items-center gap-2 font-mono text-sm text-muted-foreground">
      <ForwardedIconComponent
        name="Loader2"
        className="h-4 w-4 animate-spin"
      />
      <span>{text}</span>
    </div>
  );
};
