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
}: AccordionComponentType) {
  const [value, setValue] = useState(
    open.length === 0 ? "" : getOpenAccordion()
  );

  function getOpenAccordion() {
    let value = "";
    open.forEach((el) => {
      if (el == trigger) {
        value = trigger;
      }
    });

    return value;
  }

  function handleClick() {
    value === "" ? setValue(keyValue) : setValue("");
  }

  const handleKeyDown = (event) => {
    if (event.key === "Backspace") {
      event.preventDefault();
      event.stopPropagation();
    }
  };

  return (
    <>
      <Accordion
        type="single"
        className="w-full"
        value={value}
        onValueChange={setValue}
        onKeyDown={handleKeyDown}
      >
        <AccordionItem value={keyValue} className="border-b">
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
