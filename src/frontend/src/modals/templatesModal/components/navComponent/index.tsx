import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import { NavProps } from "../../../../types/templates/types";

export function Nav({ links, currentTab, onClick }: NavProps) {
  return (
    <div className="group flex flex-col gap-4">
      <nav className="grid">
        {links.map((link, index) => (
          <Button
            variant={link.id === currentTab ? "menu-active" : "menu"}
            size="sm"
            key={index}
            onClick={() => onClick?.(link.id)}
            className="group"
          >
            <ForwardedIconComponent
              name={link.icon}
              className={cn(
                "mr-2 h-4 w-4 stroke-2 text-muted-foreground",
                link.id === currentTab && "text-pink-400",
              )}
            />
            <span className="flex-1 text-left text-primary">{link.title}</span>
          </Button>
        ))}
      </nav>
    </div>
  );
}
