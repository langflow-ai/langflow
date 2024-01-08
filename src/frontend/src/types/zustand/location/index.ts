export type LocationStoreType = {
  current: Array<string>;
  setCurrent: (newState: Array<string>) => void;
  isStackedOpen: boolean;
  setIsStackedOpen: (newState: boolean) => void;
  showSideBar: boolean;
  setShowSideBar: (newState: boolean) => void;
  extraNavigation: {
    title: string;
    options?: Array<{
      name: string;
      href: string;
      icon: React.ElementType;
      children?: Array<JSX.Element>;
    }>;
  };
  setExtraNavigation: (newState: {
    title: string;
    options?: Array<{
      name: string;
      href: string;
      icon: React.ElementType;
      children?: Array<JSX.Element>;
    }>;
  }) => void;
  extraComponent: any;
  setExtraComponent: (newState: JSX.Element) => void;
};
