import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal, Pencil, Upload, Archive, DollarSign, Trash2 } from "lucide-react";
import type { AgentSpecItem } from "@/controllers/API/queries/agent-marketplace/use-get-agent-marketplace";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

interface MarketplaceAgentCardProps {
  item: AgentSpecItem;
  viewMode?: "grid" | "list";
  expand?: boolean; // when true, card fills available space
}

export default function MarketplaceAgentCard({ item, viewMode = "grid", expand = false }: MarketplaceAgentCardProps) {
  const name = item.spec?.name ?? item.file_name.replace(/\.ya?ml$/i, "");
  const description = item.spec?.description ?? "No description provided";
  const tags: string[] = Array.isArray(item.spec?.tags) ? item.spec?.tags : [];
  const domain = item.spec?.subDomain ?? item.spec?.domain ?? "";
  const version = item.spec?.version ?? "";

  const navigate = useCustomNavigate();

  const isPublished = (item.status ?? "").toString().toUpperCase() === "PUBLISHED";
  const isClickable = item.flow_id && isPublished;

  const handleCardClick = () => {
    if (!isClickable) return;
    navigate(`/agent-marketplace/detail/${item.flow_id}`, {
      state: {
        name,
        description,
        spec: item.spec ?? {},
      },
    });
  };

  return (
    <div
      className={`group relative flex ${expand ? "h-full" : ""} flex-col rounded-lg border border-[#EBE8FF] bg-white dark:bg-card px-4 py-3 transition-shadow hover:shadow-md ${isClickable ? "cursor-pointer" : "cursor-default"
        } ${!expand ? "max-h-[260px] md:max-h-[280px] xl:max-h-[300px] overflow-hidden" : ""} ${!isPublished ? "opacity-60 grayscale pointer-events-none" : ""
        }`}
      onClick={isClickable ? handleCardClick : undefined}
    >
      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-3">
        {/* Agent Logo */}
        {item.flow_icon && (
          <div className="h-12 w-12 flex-shrink-0 rounded-lg border bg-muted overflow-hidden">
            <img
              src={item.flow_icon}
              alt={`${name} logo`}
              className="h-full w-full object-contain p-1"
            />
          </div>
        )}

        <div className="flex-1 min-w-0">
          <h3 className="mb-1 truncate text-base font-semibold text-foreground" title={name}>
            {name}
          </h3>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {domain && <span className="truncate" title={domain}>{domain}</span>}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!isPublished && (
            <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100 text-[10px] px-1.5 py-0.5 h-5 whitespace-nowrap">
              Coming Soon
            </Badge>
          )}
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
              {item.flow_id && (
                <DropdownMenuItem onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/flow/${item.flow_id}/`);
                }} className="gap-2">
                  <Pencil className="h-4 w-4" />
                  Edit
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); /* TODO: wire Publish */ }} className="gap-2">
                <Upload className="h-4 w-4" />
                Publish
              </DropdownMenuItem>
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); /* TODO: wire Archive */ }} className="gap-2">
                <Archive className="h-4 w-4" />
                Archive
              </DropdownMenuItem>
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); /* TODO: wire Pricing */ }} className="gap-2">
                <DollarSign className="h-4 w-4" />
                View Pricing
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); /* TODO: wire Delete */ }} className="gap-2 text-destructive" disabled={true}>
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

      {/* Tags */}
      {tags.length > 0 && (
        <div className="mt-auto flex flex-wrap items-center gap-2">
          {tags.slice(0, 2).map((tag) => {
            const hasColon = tag.includes(":");
            const [label, value] = hasColon
              ? tag.split(":").map((s) => s.trim())
              : [undefined, tag];
            return (
              <Badge
                key={tag}
                variant="secondary"
                size="xq"
                className="gap-1 bg-[#F5F2FF] dark:bg-white/10 dark:text-white"
              >
                {label && <span className="text-muted-foreground dark:text-white/70">{label}:</span>}
                <span>{value}</span>
              </Badge>
            );
          })}

          {tags.length > 2 && (
            <ShadTooltip
              delayDuration={300}
              side="top"
              styleClasses="z-50"
              content={
                <div className="flex max-w-[240px] flex-wrap gap-1">
                  {tags.slice(2).map((tag) => (
                    <Badge
                      key={`hidden-${tag}`}
                      variant="secondary"
                      className="text-[11px] bg-[#F5F2FF] dark:bg-white/10 dark:text-white"
                    >
                      {tag}
                    </Badge>
                  ))}
                </div>
              }
            >
              <span className="inline-flex">
                <Badge
                  variant="secondary"
                  size="xq"
                  className="cursor-pointer bg-[#F5F2FF] dark:bg-white/10 dark:text-white"
                >
                  +{tags.length - 2}
                </Badge>
              </span>
            </ShadTooltip>
          )}
        </div>
      )}
    </div>
  );
}