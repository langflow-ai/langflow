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
import {
  useUnpublishFlow,
  useDeletePublishedFlow,
} from "@/controllers/API/queries/published-flows";
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
    const tag = MARKETPLACE_TAGS.find((t) => t.id === tagId);
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
          list: [
            error?.response?.data?.detail || error.message || "Unknown error",
          ],
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
            list: [
              error?.response?.data?.detail || error.message || "Unknown error",
            ],
          });
        },
      });
    }
  };

  return (
    <div
      className={`group relative border border-primary-border p-3 rounded-lg bg-background-surface flex flex-col  ${item.flow_id && item.status === "PUBLISHED"
          ? "cursor-pointer"
          : "cursor-default"
        } ${item.status !== "PUBLISHED"
          ? "opacity-60 grayscale pointer-events-none"
          : ""
        }
      `}
      onClick={item.status === "PUBLISHED" ? handleCardClick : undefined}
    >
      {/* <div */}
      {/* //   className={`group relative flex ${expand ? "" : ""} flex-col rounded-lg border border-[#EBE8FF] bg-white dark:bg-card px-4 py-3 transition-shadow h-[152px] w-full hover:shadow-md ${item.flow_id ? "cursor-pointer" : "cursor-default"} ${!expand ? " max-h-[260px] md:max-h-[280px] xl:max-h-[300px] overflow-hidden" : ""}`} */}
      {/* //   onClick={handleCardClick} */}
      {/* // > */}
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="grid grid-cols-[1fr_auto] gap-3 items-center">
          <h3
            className="truncate text-md font-medium text-primary-font"
            title={name}
          >
            {name}
          </h3>
          {item.status === "PUBLISHED" ? (
            <LiveIcon className="w-[14px] h-[14px]" />
          ) : (
            <Badge
              variant="secondary"
              className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100 text-[10px] px-1.5 py-0.5 h-5 whitespace-nowrap"
            >
              Coming Soon
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {version && (
            <span className="text-xs font-medium text-secondary-font whitespace-nowrap">
              Ver. {version}
            </span>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                aria-label="More options"
                variant="link"
                size="icon"
                className="h-5 w-5"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[8rem]">
              {item.flow_cloned_from && (
                <DropdownMenuItem
                  onClick={handleEditOriginal}
                  className="gap-2"
                >
                  <Pencil className="h-4 w-4" />
                  Edit
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={handleUnpublish} className="gap-2">
                <Archive className="h-4 w-4" />
                Unpublish
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={handleDelete}
                className="gap-2 text-error border-t border-primary-border"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Description */}
      <p className="mb-4 line-clamp-2 text-sm text-secondary-font min-h-[40px]">
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
                className="bg-accent-light text-secondary-font"
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
          className="max-h-[48px] max-w-[85px] justify-end"
        />
      </div>
    </div>
  );
}
