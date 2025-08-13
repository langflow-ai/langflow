import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

export function HeaderButton({
  icon,
  onClick,
}: {
  icon: string;
  onClick: () => void;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      className="flex h-8 items-center gap-2 text-muted-foreground"
      onClick={onClick}
    >
      <ForwardedIconComponent name={icon} className="h-4 w-4" />
    </Button>
  );
}
