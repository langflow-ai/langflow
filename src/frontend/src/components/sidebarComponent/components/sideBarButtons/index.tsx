import { Link } from "react-router-dom";
import { cn } from "../../../../utils/utils";
import { buttonVariants } from "../../../ui/button";

type SideBarButtonsComponentProps = {
  items: {
    href?: string;
    title: string;
    icon: React.ReactNode;
  }[];
  pathname: string;
  handleOpenNewFolderModal?: () => void;
};
const SideBarButtonsComponent = ({
  items,
  pathname,
}: SideBarButtonsComponentProps) => {
  return (
    <div className="flex gap-2 overflow-auto lg:h-[70vh] lg:flex-col">
      {items.map((item) => (
        <Link to={item.href!}>
          <div
            key={item.title}
            data-testid={`sidebar-nav-${item.title}`}
            className={cn(
              buttonVariants({ variant: "ghost" }),
              pathname === item.href
                ? "border border-border bg-muted hover:bg-muted"
                : "border border-transparent hover:border-border hover:bg-transparent",
              "flex w-full shrink-0 justify-start gap-4",
            )}
          >
            {item.icon}
            <span className="block max-w-full truncate opacity-100">
              {item.title}
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
};
export default SideBarButtonsComponent;
