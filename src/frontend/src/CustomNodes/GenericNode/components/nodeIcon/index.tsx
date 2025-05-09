import { useTypesStore } from "@/stores/typesStore";
import { iconExists, nodeColors } from "@/utils/styleUtils";
import emojiRegex from "emoji-regex";
import { useEffect, useState } from "react";

import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { checkLucideIcons } from "@/CustomNodes/helpers/check-lucide-icons";
import { cn } from "@/utils/utils";
import IconComponent from "../../../../components/common/genericIconComponent";

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
  const [name, setName] = useState(types[dataType]);

  useEffect(() => {
    iconExists(dataType).then((exists) => {
      setName(exists ? dataType : types[dataType]);
    });
  }, [dataType, types]);

  const isEmoji = emojiRegex().test(icon ?? "");
  const iconColor = nodeColors[types[dataType]];
  const iconName = icon || (isGroup ? "group_components" : name);

  const isLucideIcon = checkLucideIcons(iconName);

  const iconClassName = cn(
    "generic-node-icon",
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
            "text-foreground",
            !showNode && "flex min-h-8 min-w-8 items-center justify-center",
            "bg-lucide-icon",
          )}
        >
          <IconComponent
            strokeWidth={ICON_STROKE_WIDTH}
            name={iconName}
            className={cn(iconClassName)}
          />
        </div>
      );
    }

    return (
      <div className={cn(!showNode && "min-h-8 min-w-8")}>
        <IconComponent
          name={iconName}
          className={iconClassName}
          iconColor={iconColor}
        />
      </div>
    );
  };

  return <>{renderIcon()}</>;
}
