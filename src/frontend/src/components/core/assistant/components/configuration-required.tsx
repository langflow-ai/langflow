import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

type ConfigurationRequiredProps = {
  onConfigureClick?: () => void;
};

export const ConfigLoading = () => (
  <div className="flex h-full flex-col items-center justify-center py-4">
    <div className="flex flex-col items-center gap-3">
      <ForwardedIconComponent
        name="Loader2"
        className="h-8 w-8 animate-spin text-muted-foreground"
      />
      <span className="text-sm text-muted-foreground">
        Checking configuration...
      </span>
    </div>
  </div>
);

export const ConfigurationRequired = ({
  onConfigureClick,
}: ConfigurationRequiredProps) => (
  <div className="flex h-full flex-col items-center justify-center">
    <div className="flex flex-col items-center gap-2 text-center">
      <ForwardedIconComponent
        name="Bot"
        className="h-6 w-6 text-accent-amber-foreground"
      />
      <p className="text-sm text-foreground">
        Configure a model provider to use the Assistant
      </p>
      {onConfigureClick && (
        <Button
          size="sm"
          onClick={onConfigureClick}
          className="h-7 gap-1.5 bg-accent-emerald-foreground text-xs text-background hover:bg-accent-emerald-hover"
        >
          <ForwardedIconComponent name="Settings" className="h-3 w-3" />
          Model Providers
        </Button>
      )}
    </div>
  </div>
);
