import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";
import { ChevronsUpDown } from "lucide-react";
import React from "react";

export const HeaderMenu = ({ children }) => (
  <DropdownMenu>{children}</DropdownMenu>
);

export const HeaderMenuToggle = ({ children }) => (
  <DropdownMenuTrigger className="group inline-flex w-full items-center justify-center gap-1 rounded-md pr-0">
    <div className="flex items-center gap-1 rounded-lg px-2 py-1.5 group-hover:bg-muted">
      {children}
      <ChevronsUpDown
        className="text-muted-foreground group-hover:text-foreground"
        size={"15px"}
        strokeWidth={"2px"}
      />
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
          className="side-bar-button-size mr-3 h-[18px] w-[18px] opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100 group-focus-visible:translate-x-3 group-focus-visible:opacity-100"
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
}: React.PropsWithChildren<{ position?: "left" | "right" }>) => {
  const positionClass = position === "left" ? "left-0" : "right-0";
  return (
    <DropdownMenuContent className={cn("w-[20rem]", positionClass)}>
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
