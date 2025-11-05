import { categoryIcons } from "@/utils/styleUtils";

export const checkLucideIcons =async (iconName: string):Promise<boolean> => {
   const [lucideIcons, dynamicIconImports] = await Promise.all([
    import("lucide-react"),
    import("lucide-react/dynamicIconImports").then((mod) => mod.default),
  ]);
  return (
    !!lucideIcons[iconName] ||
    !!dynamicIconImports[iconName] ||
    !!categoryIcons[iconName]
  );
};