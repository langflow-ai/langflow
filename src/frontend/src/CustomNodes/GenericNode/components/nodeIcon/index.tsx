import { useTypesStore } from "@/stores/typesStore";
import { nodeColors, nodeIconsLucide } from "@/utils/styleUtils";
import emojiRegex from "emoji-regex";

import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { checkLucideIcons } from "@/CustomNodes/helpers/check-lucide-icons";
import { cn } from "@/utils/utils";
import IconComponent from "../../../../components/genericIconComponent";

export function NodeIcon({
  icon,
  dataType,
  showNode,
  isGroup,
}: {
  icon?: string;
  dataType: string;
  showNode: boolean;
  isGroup?: boolean;
}) {
  const types = useTypesStore((state) => state.types);
  const name = nodeIconsLucide[dataType] ? dataType : types[dataType];
  const isEmoji = emojiRegex().test(icon ?? "");
  const iconColor = nodeColors[types[dataType]];
  const iconName = icon || (isGroup ? "group_components" : name);

  const isLucideIcon = checkLucideIcons(iconName);

  const iconClassName = cn(
    "generic-node-icon",
    !showNode ? " show-node-icon " : "",
    isLucideIcon ? "lucide-icon" : "integration-icon",
  );

  const renderIcon = () => {
    if (icon && isEmoji) {
      return <span className="text-lg">{icon}</span>;
    }

    if (isLucideIcon) {
      return (
        <div
          className={cn(
            "bg-lucide-icon text-foreground",
            !showNode && "min-h-8 min-w-8",
          )}
        >
          <IconComponent
            strokeWidth={ICON_STROKE_WIDTH}
            name={iconName}
            className={cn(
              iconClassName,
              !showNode && "absolute -translate-x-0.5",
            )}
          />
        </div>
      );
    }

    return (
      <IconComponent
        name={iconName}
        className={iconClassName}
        iconColor={iconColor}
      />
    );
  };

  return <>{renderIcon()}</>;
}
