import { ReactElement, useContext, useEffect, useRef, useState } from "react";
import { AccordionComponentType, ProgressBarType } from "../../types/components";
import { Progress } from "../../components/ui/progress";
import { setInterval } from "timers/promises";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../components/ui/accordion"

export default function AccordionComponent({
  trigger,
  children,
}: AccordionComponentType) {


  return <>
                            <Accordion type="single" collapsible>
                          <AccordionItem value="item-1" className="border-none">
                            <AccordionTrigger  className="ml-3">{trigger}</AccordionTrigger>
                            <AccordionContent>
                              {children}
                            </AccordionContent>
                          </AccordionItem>
                        </Accordion>
  </>
}
