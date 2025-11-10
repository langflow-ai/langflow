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
  type: "enabled" | "available";
  defaultModelName?: string | null;
  defaultEmbeddingModelName?: string | null;
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
  type,
  defaultModelName,
  defaultEmbeddingModelName,
  onCardClick,
  onEnableProvider,
  onDeleteProvider,
  deleteDialogOpen,
  setDeleteDialogOpen,
  providerToDelete,
  setProviderToDelete,
}: ProviderListItemProps) => {
  const hasModels = provider.model_count && provider.model_count > 0;
  const isDeleteDialogForThisProvider =
    deleteDialogOpen && providerToDelete === provider.provider;

  const handleEnableClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onEnableProvider(provider.provider);
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setProviderToDelete(provider.provider);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (providerToDelete) {
      onDeleteProvider(providerToDelete);
    }
  };

  const handleDeleteDialogChange = (open: boolean) => {
    setDeleteDialogOpen(open);
    if (!open) setProviderToDelete(null);
  };

  return (
    <>
      <div
        key={provider.provider}
        className={cn(
          "flex items-center justify-between py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors",
          hasModels ? "cursor-pointer" : "opacity-60 cursor-not-allowed",
        )}
        onClick={() => onCardClick(provider)}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <ForwardedIconComponent
            name={provider.icon || "Bot"}
            className="w-5 h-5 flex-shrink-0"
          />
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <span className="text-sm font-medium truncate">
              {provider.provider}
            </span>
            {provider.model_count !== undefined && (
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
            {defaultModelName && (
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
            )}
          </div>
        </div>
        <div
          className="flex items-center gap-2"
          onClick={(e) => e.stopPropagation()}
        >
          {type === "enabled" ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={(e) => e.stopPropagation()}
                  className="h-8 w-8 text-muted-foreground hover:text-primary hover:bg-transparent"
                >
                  <ForwardedIconComponent
                    name="MoreVertical"
                    className="h-4 w-4"
                  />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleEnableClick}>
                  <ForwardedIconComponent
                    name="Pencil"
                    className="h-4 w-4 mr-2"
                  />
                  Update API Key
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={handleDeleteClick}
                  className="text-destructive focus:text-destructive"
                >
                  <ForwardedIconComponent
                    name="Trash"
                    className="h-4 w-4 mr-2"
                  />
                  Remove Provider
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button
              size="icon"
              variant="ghost"
              onClick={handleEnableClick}
              className="h-8 w-8 text-muted-foreground hover:text-primary hover:bg-transparent"
            >
              <ForwardedIconComponent name="Plus" className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <DeleteConfirmationModal
        open={isDeleteDialogForThisProvider}
        setOpen={handleDeleteDialogChange}
        onConfirm={handleDeleteConfirm}
        description={`access to ${provider.provider}`}
        note="You can re-enable this provider at any time by adding your API key again"
      />
    </>
  );
};

export default ProviderListItem;
