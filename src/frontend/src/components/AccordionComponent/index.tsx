import { useState } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../components/ui/accordion";
import { AccordionComponentType } from "../../types/components";

export default function AccordionComponent({
  trigger,
  children,
  open = [],
  keyValue,
}: AccordionComponentType): JSX.Element {
  const [value, setValue] = useState(
    open.length === 0 ? "" : getOpenAccordion()
  );

  function getOpenAccordion(): string {
    let value = "";
    open.forEach((el) => {
      if (el == trigger) {
        value = trigger;
      }
    });

    return value;
  }

  function handleClick(): void {
    value === "" ? setValue(keyValue!) : setValue("");
  }

  return (
    <>
      <Accordion
        type="single"
        className="w-full"
        value={value}
        onValueChange={setValue}
      >
        <AccordionItem value={keyValue!} className="border-b">
          <AccordionTrigger
            onClick={() => {
              handleClick();
            }}
            className="ml-3"
          >
            {trigger}
          </AccordionTrigger>
          <AccordionContent className="AccordionContent">
            {children}
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </>
  );
}
