import { useTypesStore } from "@/stores/typesStore";
import { nodeColors, nodeIconsLucide } from "@/utils/styleUtils";
import emojiRegex from "emoji-regex";
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
  const iconClassName = `generic-node-icon ${
    !showNode ? " absolute inset-x-6 h-12 w-12 " : ""
  }`;
  return icon && isEmoji ? (
    <span className="text-lg">{icon}</span>
  ) : (
    <IconComponent
      name={iconName}
      className={iconClassName}
      iconColor={iconColor}
    />
  );
}
