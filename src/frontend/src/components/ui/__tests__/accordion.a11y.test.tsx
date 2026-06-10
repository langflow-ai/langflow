import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../accordion";

const renderAccordion = () =>
  render(
    <TooltipProvider>
      <Accordion type="single" collapsible>
        <AccordionItem value="item-1">
          <AccordionTrigger>Section title</AccordionTrigger>
          <AccordionContent>Section content</AccordionContent>
        </AccordionItem>
      </Accordion>
    </TooltipProvider>,
  );

describe("AccordionTrigger accessibility", () => {
  it("should_render_trigger_text", () => {
    renderAccordion();

    expect(screen.getByText("Section title")).toBeInTheDocument();
  });

  // Known gap (a11y-action-plan 1.4): the trigger renders through asChild
  // onto a <div>, so it has no button role and is not keyboard-focusable.
  it("should_expose_trigger_as_button", () => {
    renderAccordion();

    expect(
      screen.getByRole("button", { name: /section title/i }),
    ).toBeInTheDocument();
  });

  it("should_make_trigger_keyboard_focusable", () => {
    renderAccordion();

    const trigger = screen.getByText("Section title");
    trigger.focus();
    expect(trigger).toHaveFocus();
  });
});
