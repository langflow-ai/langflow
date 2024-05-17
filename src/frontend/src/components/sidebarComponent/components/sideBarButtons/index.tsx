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
  handleOpenNewFolderModal,
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
              "!w-[200px] cursor-pointer justify-start gap-2 border border-transparent hover:border-border hover:bg-transparent",
            )}
            onClick={handleOpenNewFolderModal}
          >
            {item.title}
          </div>
        </Link>
      ))}
    </>
  );
};
export default SideBarButtonsComponent;
