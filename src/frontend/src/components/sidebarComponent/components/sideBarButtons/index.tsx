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
    <>
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
              "w-full justify-start gap-2",
            )}
          >
            {item.title}
          </div>
        </Link>
      ))}
    </>
  );
};
export default SideBarButtonsComponent;
