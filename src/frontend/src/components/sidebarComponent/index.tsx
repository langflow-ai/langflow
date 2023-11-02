import { Link, useLocation } from "react-router-dom";
import { cn } from "../../utils/utils";
import { buttonVariants } from "../ui/button";

interface SidebarNavProps extends React.HTMLAttributes<HTMLElement> {
  items: {
    href: string;
    title: string;
  }[];
  secondaryItems?: {
    href: string;
    title: string;
  }[];
}

export default function SidebarNav({
  className,
  items,
  secondaryItems,
  ...props
}: SidebarNavProps) {
  const location = useLocation();
  const pathname = location.pathname;

  return (
    <nav
      className={cn(
        "flex space-x-2 lg:flex-col lg:space-x-0 lg:space-y-1",
        className
      )}
      {...props}
    >
      {items.map((item) => (
        <Link
          key={item.href}
          to={item.href}
          className={cn(
            buttonVariants({ variant: "ghost" }),
            pathname === item.href
              ? "border border-border bg-background hover:bg-background"
              : "hover:bg-transparent hover:underline",
            "justify-start"
          )}
        >
          {item.title}
        </Link>
      ))}
      {/* {secondaryItems && (
        <>
          <div className="py-2">
            <Separator />
          </div>
          <div className="flex justify-center">
            <button className="flex h-8 w-fit items-center justify-between rounded-md border border-ring/60 px-4 py-2 text-sm text-primary hover:bg-muted">
              <IconComponent name="FolderPlus" className="mr-2 h-4 w-4 " />
              New Folder
            </button>
          </div>
        </>
      )} */}
    </nav>
  );
}
