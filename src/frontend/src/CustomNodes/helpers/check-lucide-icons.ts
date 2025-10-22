import { categoryIcons } from "@/utils/styleUtils";
const lucideIconsPromise=import("lucide-react");
const dynamicIconImportsPromise = import("lucide-react/dynamicIconImports").then((mod)=>mod.default);

export const checkLucideIcons =async (iconName: string):Promise<boolean> => {
  const [lucideIcons, dynamicIconImports] = await Promise.all([lucideIconsPromise, dynamicIconImportsPromise]);
  return (
    !!lucideIcons[iconName] ||
    !!dynamicIconImports[iconName] ||
    !!categoryIcons[iconName]
  );
};
