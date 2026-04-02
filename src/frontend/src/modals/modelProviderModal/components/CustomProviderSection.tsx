import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { useGetCustomProviders } from "@/controllers/API/queries/custom-providers";
import type { CustomProviderRead } from "@/types/custom-providers";
import { cn } from "@/utils/utils";

export interface CustomProviderSectionProps {
  selectedCustomProviderId: string | null;
  onSelect: (provider: CustomProviderRead | "new") => void;
}

const CustomProviderSection = ({
  selectedCustomProviderId,
  onSelect,
}: CustomProviderSectionProps) => {
  const { data: customProviders = [] } = useGetCustomProviders();

  return (
    <div className="flex flex-col gap-1">
      <div className="px-2 pt-3 pb-1">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Custom Providers
        </span>
      </div>
      {customProviders.map((provider) => (
        <button
          type="button"
          key={provider.id}
          data-testid={`custom-provider-item-${provider.name}`}
          className={cn(
            "flex w-full items-center justify-between rounded-lg px-2 py-3 transition-colors hover:bg-muted/50 cursor-pointer text-left",
            selectedCustomProviderId === provider.id && "bg-muted/50",
          )}
          aria-pressed={selectedCustomProviderId === provider.id}
          onClick={() => onSelect(provider)}
        >
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <ForwardedIconComponent
              name="Blocks"
              className="h-5 w-5 flex-shrink-0"
            />
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <span className="truncate text-sm font-medium">
                {provider.name}
              </span>
              {provider.models.length > 0 && (
                <Badge
                  variant={
                    selectedCustomProviderId === provider.id
                      ? "secondary"
                      : "secondaryStatic"
                  }
                  className="text-xs whitespace-nowrap mr-2"
                  size="sq"
                >
                  {provider.models.length}{" "}
                  {provider.models.length === 1 ? "model" : "models"}
                </Badge>
              )}
            </div>
          </div>
        </button>
      ))}
      <button
        type="button"
        data-testid="add-custom-provider-button"
        className={cn(
          "flex w-full items-center justify-center gap-2 rounded-lg border border-dashed px-2 py-3 transition-colors hover:bg-muted/50 cursor-pointer text-muted-foreground hover:text-foreground",
          selectedCustomProviderId === "new" && "bg-muted/50 text-foreground",
        )}
        aria-pressed={selectedCustomProviderId === "new"}
        onClick={() => onSelect("new")}
      >
        <ForwardedIconComponent name="Plus" className="h-4 w-4" />
        <span className="text-sm">Add Custom Provider</span>
      </button>
    </div>
  );
};

export default CustomProviderSection;
