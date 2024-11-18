import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { AccordionComponentType } from "@/types/components";
import { cn } from "@/utils/utils";
import { useState } from "react";

export default function AccordionComponent({
  trigger,
  children,
  disabled,
  open = [],
  keyValue,
  sideBar,
}: AccordionComponentType): JSX.Element {
  const [value, setValue] = useState(
    open.length === 0 ? "" : getOpenAccordion(),
  );

  function getOpenAccordion(): string {
    let value = "";
    open.forEach((el) => {
      if (el == keyValue) {
        value = keyValue;
      }
    });
    return value;
  }

  function handleClick(): void {
    if (!disabled) {
      value === "" ? setValue(keyValue!) : setValue("");
    }
  }

  return (
    <>
      <Accordion
        type="single"
        className="w-full"
        value={value}
        onValueChange={!disabled ? setValue : () => {}}
      >
        <AccordionItem value={keyValue!} className="border-b">
          <AccordionTrigger
            onClick={() => {
              handleClick();
            }}
            disabled={disabled}
            className={cn(
              sideBar ? "w-full bg-muted px-[0.75rem] py-[0.5rem]" : "ml-3",
              disabled ? "cursor-not-allowed" : "cursor-pointer",
            )}
          >
            {trigger}
          </AccordionTrigger>
          <AccordionContent>
            <div className="AccordionContent flex flex-col">{children}</div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </>
  );
}
