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
  sideBar,
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
            className={
              sideBar ? "w-full bg-muted px-[0.75rem] py-[0.5rem]" : "ml-3"
            }
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
