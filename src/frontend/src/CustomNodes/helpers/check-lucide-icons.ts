import * as lucideIcons from "lucide-react";
import dynamicIconImports from "lucide-react/dynamicIconImports";
import { categoryIcons } from "@/utils/styleUtils";

export const checkLucideIcons = (iconName: string): boolean => {
  return (
    !!lucideIcons[iconName] ||
    !!dynamicIconImports[iconName] ||
    !!categoryIcons[iconName]
  );
};
