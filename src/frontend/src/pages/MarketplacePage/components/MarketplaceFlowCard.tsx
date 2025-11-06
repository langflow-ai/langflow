import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal, Pencil, Archive, Trash2, Circle } from "lucide-react";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useUnpublishFlow, useDeletePublishedFlow } from "@/controllers/API/queries/published-flows";
import useAlertStore from "@/stores/alertStore";
import { AgentLogo } from "@/components/AgentLogo";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";
import { LiveIcon } from "@/assets/icons/LiveIcon";

interface MarketplaceFlowCardProps {
  item: any;
  viewMode?: "grid" | "list";
  expand?: boolean;
}

export default function MarketplaceFlowCard({
  item,
  viewMode = "grid",
  expand = false,
}: MarketplaceFlowCardProps) {
  const navigate = useCustomNavigate();
  const { mutate: unpublishFlow } = useUnpublishFlow();
  const { mutate: deletePublishedFlow } = useDeletePublishedFlow();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const name = item.flow_name || "Untitled Flow";
  const description = item.description || "No description provided";
  const tags: string[] = Array.isArray(item.tags) ? item.tags : [];
  const version = item.version || "";

  // Helper function to get tag title from tag id
  const getTagTitle = (tagId: string): string => {
    const tag = MARKETPLACE_TAGS.find(t => t.id === tagId);
    return tag ? tag.title : tagId;
  };

  const handleCardClick = () => {
    navigate(`/marketplace/detail/${item.id}`);
  };

  const handleEditOriginal = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (item.flow_cloned_from) {
      navigate(`/flow/${item.flow_cloned_from}/`);
    }
  };

  const handleUnpublish = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!item.flow_cloned_from) return;

    unpublishFlow(item.flow_cloned_from, {
      onSuccess: () => {
        setSuccessData({
          title: "Flow unpublished successfully",
        });
      },
      onError: (error: any) => {
        setErrorData({
          title: "Failed to unpublish flow",
          list: [error?.response?.data?.detail || error.message || "Unknown error"],
        });
      },
    });
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!item.id) return;

    if (confirm("Are you sure you want to delete this published flow?")) {
      deletePublishedFlow(item.id, {
        onSuccess: () => {
          setSuccessData({
            title: "Published flow deleted successfully",
          });
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to delete published flow",
            list: [error?.response?.data?.detail || error.message || "Unknown error"],
          });
        },
      });
    }
  };

  return (
    <div
      className={`group relative flex ${expand ? "" : ""} flex-col rounded-lg border border-[#EBE8FF] bg-white dark:bg-card px-4 py-3 transition-shadow h-[152px] w-full hover:shadow-md ${item.flow_id ? "cursor-pointer" : "cursor-default"} ${!expand ? " max-h-[260px] md:max-h-[280px] xl:max-h-[300px] overflow-hidden" : ""}`}
      onClick={handleCardClick}
    >
      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="grid grid-cols-[1fr_auto] gap-3 items-center mb-1">
          <h3 className="truncate text-base font-semibold text-foreground" title={name}>
            {name}
          </h3>
          {item.status === "PUBLISHED" && (
            <LiveIcon className="w-[14px] h-[14px]"/>
          )}
        </div>

        <div className="flex items-center gap-2">
          {version && (
            <span className="text-xs text-muted-foreground">Ver. {version}</span>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                aria-label="More options"
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[12rem]">
              {item.flow_cloned_from && (
                <DropdownMenuItem onClick={handleEditOriginal} className="gap-2">
                  <Pencil className="h-4 w-4" />
                  Edit
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={handleUnpublish} className="gap-2">
                <Archive className="h-4 w-4" />
                Unpublish
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleDelete} className="gap-2 text-destructive">
                <Trash2 className="h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Description */}
      <p className="mb-4 line-clamp-2 text-sm text-muted-foreground">
        {description}
      </p>
      <div className="flex justify-between items-center mt-auto">
        {/* Tags - Show all tags */}
        {tags.length > 0 && (
          <div className="mt-auto flex flex-wrap items-center gap-2">
            {tags.map((tag, index) => (
              <Badge
                key={index}
                variant="secondary"
                size="xq"
                className="gap-1 bg-[#F5F2FF] dark:bg-white/10 dark:text-white"
              >
                {getTagTitle(tag)}
              </Badge>
            ))}
          </div>
        )}

          {/* Agent Logo */}
          <AgentLogo
            blobPath={item.flow_icon}
            updatedAt={item.flow_icon_updated_at}
            altText={`${name} logo`}
            className="max-h-[48px] max-w-[85px]"
          />
      </div>
    </div>
  );
}