import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import { SessionMoreMenu } from "../session-more-menu";

const baseProps = {
  onRename: jest.fn(),
  onMessageLogs: jest.fn(),
  onDelete: jest.fn(),
  dataTestid: "session-more-menu-trigger",
};

const renderMenu = () =>
  render(
    <TooltipProvider>
      <SessionMoreMenu {...baseProps} />
    </TooltipProvider>,
  );

describe("SessionMoreMenu", () => {
  beforeAll(() => {
    if (!Element.prototype.hasPointerCapture) {
      Element.prototype.hasPointerCapture = jest.fn(() => false);
    }
    if (!Element.prototype.releasePointerCapture) {
      Element.prototype.releasePointerCapture = jest.fn();
    }
    if (!Element.prototype.scrollIntoView) {
      Element.prototype.scrollIntoView = jest.fn();
    }
  });

  it("has no detectable axe violations while closed", async () => {
    const { container } = renderMenu();

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("has no detectable axe violations while open", async () => {
    const user = userEvent.setup();
    const { container } = renderMenu();

    await user.click(screen.getByTestId("session-more-menu-trigger"));

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  // Regression guard: onCloseAutoFocus used to be `(e) => e.preventDefault()`
  // with nothing to replace Radix's default focus-return, so closing the
  // dropdown (e.g. via Escape) dropped focus to <body>. That broke more than
  // WCAG 2.4.3 — with nothing inside the Playground panel focused, a second
  // Escape press (meant to close the panel itself) had no element inside the
  // panel to match against, so it silently did nothing.
  it("returns focus to the trigger when the dropdown closes via Escape", async () => {
    const user = userEvent.setup();
    renderMenu();

    const trigger = screen.getByTestId("session-more-menu-trigger");
    await user.click(trigger);

    expect(
      screen.getByRole("option", { name: /message logs/i }),
    ).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(
      screen.queryByRole("option", { name: /message logs/i }),
    ).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(document.body).not.toHaveFocus();
  });
});
