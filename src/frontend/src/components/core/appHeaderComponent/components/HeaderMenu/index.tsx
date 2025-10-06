import { ChevronsUpDown } from "lucide-react";
import type React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";

export const HeaderMenu = ({ children }) => (
  <DropdownMenu>{children}</DropdownMenu>
);

export const HeaderMenuToggle = ({ children }) => (
  <DropdownMenuTrigger
    className="inline-flex w-full items-center justify-center rounded-md pl-1 pr-1"
    data-testid="user_menu_button"
    id="user_menu_button"
  >
    <div className="group flex items-center self-center rounded-md">
      <div className="flex h-6 w-10 items-center justify-center rounded-full bg-background transition-colors hover:bg-muted group-hover:bg-muted">
        <div className="relative right-1 z-10">{children}</div>
        <ChevronsUpDown className="relative h-[14px] w-[14px] text-muted-foreground group-hover:text-primary" />
      </div>
    </div>
  </DropdownMenuTrigger>
);

export const HeaderMenuItemLink = ({
  href = "#",
  children,
  newPage = false,
  icon = "external-link",
}) => (
  <DropdownMenuItem className="cursor-pointer rounded-none p-3 px-4" asChild>
    <a
      href={href}
      className="group flex w-full items-center justify-between"
      {...(newPage ? { rel: "noreferrer", target: "_blank" } : {})}
    >
      {children}
      {icon && (
        <ForwardedIconComponent
          name={icon}
          className="side-bar-button-size h-[18px] w-[18px] opacity-0 group-hover:opacity-100  group-focus-visible:opacity-100"
        />
      )}
    </a>
  </DropdownMenuItem>
);

export const HeaderMenuItemButton = ({ icon = "", onClick, children }) => (
  <DropdownMenuItem
    className="group flex cursor-pointer items-center justify-between p-3 px-4"
    onClick={onClick}
  >
    {children}
    {icon && (
      <ForwardedIconComponent
        name={icon}
        className="side-bar-button-size mr-3 h-[18px] w-[18px] opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100 group-focus-visible:translate-x-3 group-focus-visible:opacity-100"
      />
    )}
  </DropdownMenuItem>
);

export const HeaderMenuItems = ({
  position = "left",
  children,
  classNameSize = "w-[20rem]",
}: React.PropsWithChildren<{
  position?: "left" | "right";
  classNameSize?: string;
}>) => {
  const positionClass = position === "left" ? "left-0" : "right-0";
  return (
    <DropdownMenuContent className={cn(classNameSize, positionClass)}>
      {children}
    </DropdownMenuContent>
  );
};

export const HeaderMenuItemsSection = ({ children }) => (
  <>
    {children}
    <DropdownMenuSeparator className="last:hidden" />
  </>
);

export const HeaderMenuItemsTitle = ({
  subTitle,
  children,
}: React.PropsWithChildren<{ subTitle?: React.ReactNode }>) => (
  <header className="group flex w-full flex-col items-start rounded-md rounded-b-none border px-4 py-3">
    <h3 className="text-base font-semibold">{children}</h3>
    {subTitle ? <h4 className="text-sm font-normal">{subTitle}</h4> : null}
  </header>
);
