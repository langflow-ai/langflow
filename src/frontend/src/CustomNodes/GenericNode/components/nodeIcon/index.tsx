import emojiRegex from "emoji-regex";
import { useEffect, useState } from "react";
import { checkLucideIcons } from "@/CustomNodes/helpers/check-lucide-icons";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { useTypesStore } from "@/stores/typesStore";
import { iconExists } from "@/utils/styleUtils";
import IconComponent from "../../../../components/common/genericIconComponent";

export function NodeIcon({
  icon,
  dataType,
  isGroup,
}: {
  icon?: string;
  dataType: string;
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
  const iconName = icon || (isGroup ? "group_components" : name);

  const isLucideIcon = checkLucideIcons(iconName);

  const renderIcon = () => {
    if (icon && isEmoji) {
      return <span className="text-lg">{icon}</span>;
    }

    return (
      <div className="flex h-4 w-4 items-center justify-center">
        <IconComponent
          strokeWidth={isLucideIcon ? ICON_STROKE_WIDTH : undefined}
          name={iconName}
          className="h-4 w-4"
        />
      </div>
    );
  };

  return <>{renderIcon()}</>;
}
