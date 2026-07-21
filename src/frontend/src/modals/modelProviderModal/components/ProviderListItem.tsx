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
  const isEnabled = provider.is_enabled;
  const isConfigured = provider.is_configured;
  const isActive = isEnabled || isConfigured;

  return (
    <button
      type="button"
      data-testid={`provider-item-${provider.provider}`}
      aria-pressed={isSelected}
      className={cn(
        "flex w-full items-center justify-between rounded-lg px-2 py-3 text-left transition-colors hover:bg-muted/50 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        isSelected && "bg-muted/50",
      )}
      onClick={() => onSelect(provider)}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <ForwardedIconComponent
          name={provider.icon || "Bot"}
          className={cn(
            "h-5 w-5 flex-shrink-0 transition-all",
            !isActive && "opacity-50 grayscale",
          )}
        />
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span
            className={cn(
              "truncate text-sm font-medium",
              !isActive && "text-muted-foreground",
            )}
          >
            {provider.provider}
          </span>
          {provider.model_count !== undefined && isActive && (
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
          name={isActive ? "check" : "Plus"}
          className={cn(
            "h-4 w-4",
            !isActive ? "text-muted-foreground" : "text-status-green",
          )}
        />
      )}
    </button>
  );
};

export default ProviderListItem;
