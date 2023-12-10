import { FlowType } from "../flow";

export type sidebarNavigationItemType = {
  name: string;
  href: string;
  icon: React.ForwardRefExoticComponent<React.SVGProps<SVGSVGElement>>;
  current: boolean;
};

export type localStorageUserType = {
  components: { [key: string]: FlowType };
};
