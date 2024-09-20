import { Button } from "@/components/ui/button";
import IconComponent from "@/components/genericIconComponent";
import { ButtonHTMLAttributes } from "react";

export function EditMessageButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {

    return(
        <Button variant="ghost" size="icon" {...props}>
            <IconComponent name="pencil" className="w-4 h-4" />
        </Button>
    )
}
