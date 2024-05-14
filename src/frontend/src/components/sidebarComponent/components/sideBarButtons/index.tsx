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
  console.log(items);

  return (
    <>
      {items.map((item) => (
        <div
          key={item.title}
          data-testid={`sidebar-nav-${item.title}`}
          className={cn(
            buttonVariants({ variant: "ghost" }),
            "cursor-pointer justify-start gap-2 border border-transparent hover:border-border hover:bg-transparent"
          )}
          onClick={handleOpenNewFolderModal}
        >
          {item.icon}
          {item.title}
        </div>
      ))}
    </>
  );
};
export default SideBarButtonsComponent;
