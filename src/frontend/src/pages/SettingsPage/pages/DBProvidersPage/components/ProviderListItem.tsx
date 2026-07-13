import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { DBProviderOption } from "@/constants/dbProviderConstants";
import { cn } from "@/utils/utils";

export function ProviderListItem({
  provider,
  isActive,
  isSelected,
  isConfigured,
  onSelect,
}: {
  provider: DBProviderOption;
  isActive: boolean;
  isSelected: boolean;
  isConfigured: boolean;
  onSelect: () => void;
}) {
  const { t } = useTranslation();
  const isComingSoon = provider.status === "coming_soon";
  const isMuted = (!isConfigured || isComingSoon) && !provider.defaultEnabled;

  return (
    <button
      type="button"
      data-testid={`db-provider-item-${provider.id}`}
      className={cn(
        "flex w-full cursor-pointer items-center justify-between rounded-lg px-2 py-3 text-left transition-colors hover:bg-muted/50",
        isSelected && "bg-muted/50",
        isComingSoon && "cursor-default opacity-70",
      )}
      onClick={onSelect}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <ForwardedIconComponent
          name={provider.icon}
          className={cn(
            "h-5 w-5 flex-shrink-0",
            isMuted && "opacity-50 grayscale",
          )}
        />
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span
            className={cn(
              "truncate text-sm font-medium",
              isMuted && "text-muted-foreground",
            )}
          >
            {provider.label}
          </span>
          {isComingSoon && (
            <Badge variant="secondaryStatic" size="sq" className="text-xs">
              {t("settings.dbProviders.comingSoon")}
            </Badge>
          )}
          {isActive && !isComingSoon && (
            <Badge variant="secondary" size="sq" className="text-xs">
              {t("settings.dbProviders.active")}
            </Badge>
          )}
        </div>
      </div>
      {!isComingSoon && (
        <ForwardedIconComponent
          name={isActive ? "Check" : "Plus"}
          className={cn(
            "h-4 w-4",
            isActive ? "text-status-green" : "text-muted-foreground",
          )}
        />
      )}
    </button>
  );
}
