import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import ModelProviderModal from "@/modals/modelProviderModal";
import ForwardedIconComponent from "../genericIconComponent";

export const ModelProviderCount = () => {
  const [open, setOpen] = useState(false);
  const { data: enabledModelsData } = useGetEnabledModels();

  const enabledCount = useMemo(() => {
    if (!enabledModelsData?.enabled_models) return 0;
    return Object.values(enabledModelsData.enabled_models).reduce(
      (total, providerModels) =>
        total + Object.values(providerModels).filter(Boolean).length,
      0,
    );
  }, [enabledModelsData]);

  return (
    <>
      <Button
        unstyled
        size="sm"
        className="hit-area-hover flex items-center gap-2 rounded-md p-1 text-muted-foreground group"
        onClick={() => setOpen((cur) => !cur)}
        data-testid="model-provider-count-button"
      >
        <ForwardedIconComponent name="BrainCog" className="w-4 h-4" />
        <div className="text-xs">Models</div>
        <Badge
          variant="secondaryStatic"
          size="sq"
          className="text-xs group-hover:text-primary group-hover:bg-secondary"
          data-testid="model-provider-count-badge"
        >
          {enabledCount}
        </Badge>
      </Button>
      {open && (
        <ModelProviderModal
          open={open}
          onClose={() => setOpen(false)}
          modelType="all"
        />
      )}
    </>
  );
};

export default ModelProviderCount;
