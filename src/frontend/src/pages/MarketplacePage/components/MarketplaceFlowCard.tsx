import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import IconComponent from "@/components/common/genericIconComponent";
import moment from "moment";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

interface MarketplaceFlowCardProps {
  item: any;
  viewMode: "grid" | "list";
}

export default function MarketplaceFlowCard({
  item,
  viewMode,
}: MarketplaceFlowCardProps) {
  const navigate = useCustomNavigate();

  const handleClick = () => {
    navigate(`/marketplace/detail/${item.id}`);
  };

  return (
    <Card
      className="p-4 hover:shadow-lg transition-shadow cursor-pointer"
      onClick={handleClick}
    >
      <div className="flex flex-col gap-3">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            {item.flow_icon && (
              <div className="flex h-10 w-10 items-center justify-center rounded bg-muted">
                <IconComponent name={item.flow_icon} className="h-5 w-5" />
              </div>
            )}
            <div>
              <h3 className="font-semibold">{item.flow_name}</h3>
              {item.version && (
                <span className="text-xs text-muted-foreground">
                  v{item.version}
                </span>
              )}
            </div>
          </div>
          <Badge
            variant="secondary"
            className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100"
          >
            Published
          </Badge>
        </div>

        {/* Description */}
        {item.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {item.description}
          </p>
        )}

        {/* Tags */}
        {item.tags && item.tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {item.tags.map((tag: string) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {/* Category */}
        {item.category && (
          <div className="text-xs text-muted-foreground">
            Category: {item.category}
          </div>
        )}

        {/* Footer - Publisher Info */}
        <div className="flex items-center gap-2 pt-2 border-t dark:border-gray-800">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold">
            {item.published_by_username?.[0]?.toUpperCase() || "?"}
          </div>
          <span className="text-xs text-muted-foreground">
            by {item.published_by_username || "Unknown"}
          </span>
          <span className="text-xs text-muted-foreground">•</span>
          <span className="text-xs text-muted-foreground">
            {moment(item.published_at).fromNow()}
          </span>
        </div>
      </div>
    </Card>
  );
}
