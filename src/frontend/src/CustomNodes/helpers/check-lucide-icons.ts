import { isFontAwesomeIcon } from "@/icons/fontAwesomeIcons";
import { categoryIcons } from "@/utils/styleUtils";
import * as lucideIcons from "lucide-react";
import dynamicIconImports from "lucide-react/dynamicIconImports";

export const checkLucideIcons = (iconName: string): boolean => {
  if (isFontAwesomeIcon(iconName)) {
    return false;
  }

  return (
    lucideIcons[iconName] ||
    dynamicIconImports[iconName] ||
    categoryIcons[iconName]
  );
};
