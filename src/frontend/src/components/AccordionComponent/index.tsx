import { ReactElement, useContext, useEffect, useRef, useState } from "react";
import {
  AccordionComponentType,
  ProgressBarType,
} from "../../types/components";
import { Progress } from "../../components/ui/progress";
import { setInterval } from "timers/promises";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../components/ui/accordion";

export default function AccordionComponent({
  trigger,
  children,
  open = false,
}: AccordionComponentType) {
  const [value, setValue] = useState(!open ? "" : trigger);
  function handleClick() {
    value == "" ? setValue(trigger) : setValue("");
  }

  return (
    <>
      <Accordion type="single" value={value} onValueChange={setValue}>
        <AccordionItem value={trigger} className="border-none">
          <AccordionTrigger
            onClick={() => {
              handleClick();
            }}
            className="ml-3"
          >
            {trigger}
          </AccordionTrigger>
          <AccordionContent>{children}</AccordionContent>
        </AccordionItem>
      </Accordion>
    </>
  );
}
