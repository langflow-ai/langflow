import { useState } from "react";
import { AccordionComponentType } from "../../../../types/components";
import IconComponent from "../../../common/genericIconComponent";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../../ui/custom-accordion";

export default function FolderAccordionComponent({
  trigger,
  open = [],
  keyValue,
  options,
}: AccordionComponentType): JSX.Element {
  const [value, setValue] = useState(
    open.length === 0 ? "" : getOpenAccordion(),
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
        <AccordionItem value={keyValue!} className="">
          <AccordionTrigger
            onClick={() => {
              handleClick();
            }}
            className="px-2"
          >
            {trigger}
          </AccordionTrigger>
          <AccordionContent>
            {options!.map((option, index) => (
              <div
                key={index}
                className="flex cursor-pointer px-2 py-1 hover:bg-muted-foreground/10"
              >
                <IconComponent
                  name={option.icon}
                  className="relative top-[1.5px] mr-2 h-4 w-4"
                  aria-hidden="true"
                />
                <span className="truncate">{option.title}</span>
              </div>
            ))}
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </>
  );
}
