import { Link, useLocation } from "react-router-dom";
import { cn } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { buttonVariants } from "../ui/button";
const folderArray = [
  {
    title: "Getting Started",
    icon: "folder",
    id: "77290480-66a0-4562-8550-811d54e8ccf8",
  },
  {
    title: "Folder 1",
    icon: "folder",
    id: "d165c958-3a89-4710-b898-a0e2bfe06164",
  },
];

interface SidebarNavProps extends React.HTMLAttributes<HTMLElement> {
  items: {
    href?: string;
    title: string;
    icon: React.ReactNode;
  }[];
  handleOpenNewFolderModal: () => void;
  handleChangeFolder: (id: string) => void;
}

export default function SidebarNav({
  className,
  items,
  handleOpenNewFolderModal,
  handleChangeFolder,
  ...props
}: SidebarNavProps) {
  const location = useLocation();
  const pathname = location.pathname;

  return (
    <nav
      className={cn(
        "flex space-x-2 lg:flex-col lg:space-x-0 lg:space-y-1",
        className,
      )}
      {...props}
    >
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

      {folderArray.map((item) => (
        <div
          key={item.title}
          data-testid={`sidebar-nav-${item.title}`}
          className={cn(
            buttonVariants({ variant: "ghost" }),
            pathname === item.id
              ? "border border-border bg-muted hover:bg-muted"
              : "border border-transparent hover:border-border hover:bg-transparent",
            "cursor-pointer justify-start gap-2",
          )}
          onClick={() => handleChangeFolder(item.id)}
        >
          <IconComponent name={item.icon} className="w-4 stroke-[1.5]" />
          {item.title}
        </div>
      ))}
    </nav>
  );
}
