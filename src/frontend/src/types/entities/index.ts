import { HomeIcon } from "@heroicons/react/24/outline";

export type sidebarNavigationItemType = {
  name: string;
  href: string;
  icon: React.ForwardRefExoticComponent<React.SVGProps<SVGSVGElement>>;
  current: boolean;
};
