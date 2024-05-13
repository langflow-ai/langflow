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
  handleOpenNewFolderModal: () => void;
};
const SideBarButtonsComponent = ({
  items,
  pathname,
  handleOpenNewFolderModal,
}: SideBarButtonsComponentProps) => {
  return (
    <>
      {items.map((item) =>
        item.href ? (
          <Link
            data-testid={`sidebar-nav-${item.title}`}
            key={item.href}
            to={item.href}
            className={cn(
              buttonVariants({ variant: "ghost" }),
              "border border-transparent hover:border-border hover:bg-transparent",
              "justify-start gap-2",
            )}
          >
            {item.icon}
            {item.title}
          </Link>
        ) : (
          <>
            <div
              key={item.title}
              data-testid={`sidebar-nav-${item.title}`}
              className={cn(
                buttonVariants({ variant: "ghost" }),
                pathname === item.href
                  ? "border border-border bg-muted hover:bg-muted"
                  : "border border-transparent hover:border-border hover:bg-transparent",
                "cursor-pointer justify-start gap-2",
              )}
              onClick={handleOpenNewFolderModal}
            >
              {item.icon}
              {item.title}
            </div>
          </>
        ),
      )}
    </>
  );
};
export default SideBarButtonsComponent;
