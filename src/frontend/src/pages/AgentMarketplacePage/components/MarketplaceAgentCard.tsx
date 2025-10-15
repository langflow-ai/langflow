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
import { cn } from "@/utils/utils";
import type { AgentSpecItem } from "@/controllers/API/queries/agent-marketplace/use-get-agent-marketplace";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useMemo } from "react";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

interface MarketplaceAgentCardProps {
  item: AgentSpecItem;
  viewMode?: "grid" | "list";
}

export default function MarketplaceAgentCard({ item, viewMode = "grid" }: MarketplaceAgentCardProps) {
  const name = item.spec?.name ?? item.file_name.replace(/\.ya?ml$/i, "");
  const description = item.spec?.description ?? "No description provided";
  const tags: string[] = Array.isArray(item.spec?.tags) ? item.spec?.tags : [];
  const status = (item.spec?.status ?? "").toString();
  const domain = item.spec?.subDomain ?? item.spec?.domain ?? "";
  const version = item.spec?.version ?? "";

  const navigate = useCustomNavigate();

  // Lightweight JSON → YAML conversion implemented locally
  const jsonToYaml = (value: any, indent = 0): string => {
    const spacer = " ".repeat(indent);
    const nextIndent = indent + 2;

    const formatScalar = (v: any): string => {
      if (v === null || v === undefined) return "null";
      const t = typeof v;
      if (t === "string") return JSON.stringify(v); // safe quoting
      if (t === "number") return Number.isFinite(v) ? String(v) : JSON.stringify(v);
      if (t === "boolean") return v ? "true" : "false";
      return JSON.stringify(v);
    };

    if (Array.isArray(value)) {
      if (value.length === 0) return "[]";
      return value
        .map((item) => {
          if (item && typeof item === "object") {
            const nested = jsonToYaml(item, nextIndent);
            return `${spacer}- ${nested.startsWith("\n") ? nested.substring(1) : `\n${nested}`}`;
          }
          return `${spacer}- ${formatScalar(item)}`;
        })
        .join("\n");
    }

    if (value && typeof value === "object") {
      const keys = Object.keys(value);
      if (keys.length === 0) return "{}";
      return keys
        .map((key) => {
          const val = (value as any)[key];
          if (val && typeof val === "object") {
            const nested = jsonToYaml(val, nextIndent);
            if (Array.isArray(val)) {
              // arrays inline if empty, otherwise block
              return `${spacer}${key}: ${nested.includes("\n") ? `\n${nested}` : nested}`;
            }
            return `${spacer}${key}:\n${nested}`;
          }
          return `${spacer}${key}: ${formatScalar(val)}`;
        })
        .join("\n");
    }

    // scalars
    return `${spacer}${formatScalar(value)}`;
  };

  const specYaml = useMemo(() => jsonToYaml(item.spec ?? {}), [item.spec]);

  const handleCardClick = () => {
    navigate("/agent-marketplace/detail", {
      state: {
        name,
        description,
        domain,
        version,
        specYaml,
        spec: item.spec ?? {},
        fileName: item.file_name,
        folderName: item.folder_name,
        status,
      },
    });
  };

  return (
    <div
      className={cn(
        "group relative flex h-full flex-col rounded-lg border border-[#EBE8FF] bg-white dark:bg-card px-4 py-3 transition-shadow hover:shadow-md",
        viewMode === "list" ? "cursor-pointer" : "cursor-pointer",
      )}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleCardClick();
        }
      }}
    >
      {/* Header */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex-1">
          <h3 className="mb-1 truncate text-base font-semibold text-foreground" title={name}>
            {name}
          </h3>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {domain && <span className="truncate" title={domain}>{domain}</span>}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {version && (
            <span className="text-xs text-muted-foreground">ver {version}</span>
          )}
          <Badge variant="successStatic" size="xq" className="px-2 opacity-80">
            Published
          </Badge>
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
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); /* TODO: wire Edit */ }} className="gap-2">
                <Pencil className="h-4 w-4" />
                Edit
              </DropdownMenuItem>
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
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); /* TODO: wire Delete */ }} className="gap-2 text-destructive">
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
                className="gap-1"
                style={{ backgroundColor: "#F5F2FF" }}
              >
                {label && <span className="text-muted-foreground">{label}:</span>}
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
                      className="text-[11px]"
                      style={{ backgroundColor: "#F5F2FF" }}
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
                  className="cursor-pointer"
                  style={{ backgroundColor: "#F5F2FF" }}
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