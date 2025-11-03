import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

interface ModelProvidersHeaderProps {
  showExperimental: boolean;
  onToggleExperimental: (value: boolean) => void;
}

const ModelProvidersHeader = ({
  showExperimental,
  onToggleExperimental,
}: ModelProvidersHeaderProps) => {
  return (
    <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
      <div className="flex w-full flex-col">
        <h2 className="flex items-center text-lg font-semibold tracking-tight">
          Model Providers
          <ForwardedIconComponent
            name="BrainCircuit"
            className="ml-2 h-5 w-5 text-primary"
          />
        </h2>
        <p className="text-sm text-muted-foreground">
          Configure access to Language, Embedding, and Multimodal models.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Switch
          id="show-experimental"
          checked={showExperimental}
          onCheckedChange={onToggleExperimental}
        />
        <Label
          htmlFor="show-experimental"
          className="text-sm text-muted-foreground cursor-pointer"
        >
          Show experimental
        </Label>
      </div>
    </div>
  );
};

export default ModelProvidersHeader;
