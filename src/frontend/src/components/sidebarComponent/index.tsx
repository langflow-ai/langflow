import { useLocation } from "react-router-dom";
import { cn } from "../../utils/utils";
import HorizontalScrollFadeComponent from "../horizontalScrollFadeComponent";
import SideBarButtonsComponent from "./components/sideBarButtons";

type SidebarNavProps = {
  items: {
    href?: string;
    title: string;
    icon: React.ReactNode;
  }[];
  className?: string;
};

export default function SidebarNav({
  className,
  items,
  ...props
}: SidebarNavProps) {
  const location = useLocation();
  const pathname = location.pathname;

  return (
    <nav className={cn(className)} {...props}>
      <HorizontalScrollFadeComponent>
        <SideBarButtonsComponent items={items} pathname={pathname} />
      </HorizontalScrollFadeComponent>
    </nav>
  );
}
