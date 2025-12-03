import { useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { cn } from "@/utils/utils";
import { Provider } from "./types";

type ProviderListItemProps = {
  provider: Provider;
  defaultModelName?: string | null;
  defaultEmbeddingModelName?: string | null;
  isSelected?: boolean;
  onCardClick: (provider: Provider) => void;
  onEnableProvider: (providerName: string) => void;
  onDeleteProvider: (providerName: string) => void;
  deleteDialogOpen: boolean;
  setDeleteDialogOpen: (open: boolean) => void;
  providerToDelete: string | null;
  setProviderToDelete: (provider: string | null) => void;
};

const ProviderListItem = ({
  provider,
  defaultModelName,
  defaultEmbeddingModelName,
  isSelected,
  onCardClick,
  onEnableProvider,
  onDeleteProvider,
  deleteDialogOpen,
  setDeleteDialogOpen,
  providerToDelete,
  setProviderToDelete,
}: ProviderListItemProps) => {
  const [type, setType] = useState<"enabled" | "available">(
    provider.is_enabled ? "enabled" : "available",
  );
  const hasModels = provider.model_count && provider.model_count > 0;

  return (
    <>
      <div
        key={provider.provider}
        className={cn(
          "flex items-center justify-between py-3 px-2 rounded-lg hover:bg-muted/50 transition-colors",
          hasModels ? "cursor-pointer" : "opacity-60 cursor-not-allowed",
          isSelected && "bg-muted/50",
        )}
        onClick={() => onCardClick(provider)}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <ForwardedIconComponent
            name={provider.icon || "Bot"}
            className={cn(
              "w-5 h-5 flex-shrink-0 transition-all",
              !provider.is_enabled && "grayscale opacity-50",
            )}
          />
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <span className="text-sm font-medium truncate">
              {provider.provider}
            </span>
            {provider.model_count !== undefined && provider.is_enabled && (
              <span
                className={cn(
                  "text-xs",
                  type === "enabled"
                    ? "text-accent-emerald-foreground"
                    : "text-muted-foreground",
                )}
              >
                {provider.model_count}{" "}
                {provider.model_count === 1 ? "model" : "models"}
              </span>
            )}
            {/* {defaultModelName && (
              <>
                <ForwardedIconComponent
                  name="Sparkle"
                  className="w-3 h-3 inline-block text-yellow-500 fill-yellow-500"
                />
                <span className="flex text-yellow-500 text-sm truncate">
                  {defaultModelName}
                </span>
              </>
            )}
            {defaultEmbeddingModelName && (
              <>
                <ForwardedIconComponent
                  name="Zap"
                  className="w-3 h-3 inline-block text-purple-500 fill-purple-500"
                />
                <span className="flex text-purple-500 text-sm truncate">
                  {defaultEmbeddingModelName}
                </span>
              </>
            )} */}
          </div>
        </div>

        <ForwardedIconComponent
          name={type === "enabled" ? "MoreVertical" : "Plus"}
          className="h-4 w-4"
          onClick={() => onCardClick(provider)}
        />
      </div>
    </>
  );
};

export default ProviderListItem;
