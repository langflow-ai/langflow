import IconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ButtonHTMLAttributes } from "react";

export function EditMessageButton(
  props: ButtonHTMLAttributes<HTMLButtonElement>,
) {
  return (
    <Button variant="ghost" size="icon" {...props}>
      <IconComponent name="pencil" className="h-4 w-4" />
    </Button>
  );
}
