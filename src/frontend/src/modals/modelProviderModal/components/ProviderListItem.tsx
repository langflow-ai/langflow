import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/utils";
import { Provider } from "./types";

export interface ProviderListItemProps {
  provider: Provider;
  isSelected?: boolean;
  onSelect: (provider: Provider) => void;
  showIcon?: boolean;
}

const ProviderListItem = ({
  provider,
  isSelected,
  onSelect,
  showIcon,
}: ProviderListItemProps) => {
  const hasModels = provider.model_count && provider.model_count > 0;
  const isEnabled = provider.is_enabled;

  return (
    <div
      data-testid={`provider-item-${provider.provider}`}
      className={cn(
        "flex items-center justify-between rounded-lg px-2 py-3 transition-colors hover:bg-muted/50",
        hasModels ? "cursor-pointer" : "cursor-not-allowed opacity-60",
        isSelected && "bg-muted/50",
      )}
      onClick={() => onSelect(provider)}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <ForwardedIconComponent
          name={provider.icon || "Bot"}
          className={cn(
            "h-5 w-5 flex-shrink-0 transition-all",
            !isEnabled && "opacity-50 grayscale",
          )}
        />
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span
            className={cn(
              "truncate text-sm font-medium",
              !isEnabled && "text-muted-foreground",
            )}
          >
            {provider.provider}
          </span>
          {provider.model_count !== undefined && isEnabled && (
            <Badge
              variant={isSelected ? "secondary" : "secondaryStatic"}
              className="text-xs whitespace-nowrap mr-2"
              size="sq"
            >
              {provider.model_count}{" "}
              {provider.model_count === 1 ? "model" : "models"}
            </Badge>
          )}
        </div>
      </div>
      {!showIcon && (
        <ForwardedIconComponent
          name={isEnabled ? "check" : "Plus"}
          className={cn(
            "h-4 w-4",
            !isEnabled ? "text-muted-foreground" : "text-status-green",
          )}
        />
      )}
    </div>
  );
};

export default ProviderListItem;
