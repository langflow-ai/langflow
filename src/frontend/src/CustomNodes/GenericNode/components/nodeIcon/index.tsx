import { useTypesStore } from "@/stores/typesStore";
import { NodeDataType } from "@/types/flow";
import { iconExists, nodeColors } from "@/utils/styleUtils";
import emojiRegex from "emoji-regex";
import { useEffect, useState } from "react";

import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { checkLucideIcons } from "@/CustomNodes/helpers/check-lucide-icons";
import IconComponent from "../../../../components/common/genericIconComponent";

export function NodeIcon({ data }: { data: NodeDataType }) {
  const types = useTypesStore((state) => state.types);
  const [name, setName] = useState(types[data.type]);

  useEffect(() => {
    iconExists(data.type).then((exists) => {
      setName(exists ? data.type : types[data.type]);
    });
  }, [data.type, types]);

  const isEmoji = emojiRegex().test(data.node?.icon ?? "");
  const iconColor = nodeColors[types[data.type]];
  const iconName =
    data.node?.icon || (data.node?.flow ? "group_components" : name);

  const isLucideIcon = checkLucideIcons(iconName);

  const renderIcon = () => {
    if (data.node?.icon && isEmoji) {
      return <span className="text-lg">{data.node?.icon}</span>;
    }

    return (
      <div className="flex h-4 w-4 items-center justify-center">
        {isLucideIcon ? (
          <IconComponent strokeWidth={ICON_STROKE_WIDTH} name={iconName} />
        ) : (
          <IconComponent name={iconName} iconColor={iconColor} />
        )}
      </div>
    );
  };

  return <>{renderIcon()}</>;
}
