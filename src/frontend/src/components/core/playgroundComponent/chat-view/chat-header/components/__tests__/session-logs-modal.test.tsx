import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type RefObject, useRef, useState } from "react";
import { axe } from "@/utils/a11y-test";
import { SessionLogsModal } from "../session-logs-modal";

jest.mock("@/modals/IOModal/components/session-view", () => ({
  __esModule: true,
  default: () => <div data-testid="session-view">messages</div>,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name?: string }) => (
    <div data-testid={name ? `icon-${name}` : "icon"} />
  ),
}));

const SESSION_ID = "session-1";

// The caller (chat-header.tsx) captures whichever trigger actually opened
// the modal into a ref and hands it to SessionLogsModal — there is more
// than one possible trigger in the real tree (one per session row, plus
// the header's own "current session" menu), so this harness's trigger
// testid is deliberately unrelated to the session id, unlike the old
// convention-guessing implementation this replaced.
function Harness({ triggerTestId }: { triggerTestId: string }) {
  const [open, setOpen] = useState(true);
  const triggerRef = useRef<HTMLElement | null>(
    null,
  ) as RefObject<HTMLElement | null>;
  return (
    <>
      <button
        type="button"
        data-testid={triggerTestId}
        aria-label="More options"
        ref={(el) => {
          triggerRef.current = el;
        }}
      >
        More options
      </button>
      <SessionLogsModal
        sessionId={SESSION_ID}
        flowId="flow-1"
        open={open}
        setOpen={setOpen}
        triggerElementRef={triggerRef}
      />
    </>
  );
}

describe("SessionLogsModal", () => {
  it("has no detectable axe violations while open", async () => {
    const { container } = render(<Harness triggerTestId="some-trigger" />);

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  // Regression guard: this dialog previously had no onCloseAutoFocus at
  // all, so BaseModal/Radix's default left focus on <body> when it closed.
  // That broke more than WCAG 2.4.3 — with nothing inside the Playground
  // panel focused, a second Escape press (meant to close the panel itself)
  // had no element inside the panel to match against, so it silently did
  // nothing instead of closing the panel.
  it("returns focus to the captured trigger when closed via Escape", async () => {
    const user = userEvent.setup();
    render(<Harness triggerTestId="some-trigger" />);

    expect(screen.getByTestId("session-view")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(screen.queryByTestId("session-view")).not.toBeInTheDocument();
    const trigger = screen.getByTestId("some-trigger");
    expect(trigger).toHaveFocus();
    expect(document.body).not.toHaveFocus();
  });

  // Regression guard: an earlier version of this fix guessed the trigger
  // via `document.querySelector('[data-testid="session-${sessionId}-more-menu"]')`,
  // which only matched the per-row trigger. The real app also opens this
  // modal from the header's own "current session" menu, whose testid has
  // no relationship to the session id — that path would have silently
  // found nothing and fallen back to the exact <body>-focus bug this fix
  // exists to prevent. Assert focus restoration works for an arbitrarily
  // named trigger, not just one matching that old naming convention.
  it("works regardless of the trigger's testid naming, proving it isn't guessed by convention", async () => {
    const user = userEvent.setup();
    render(<Harness triggerTestId="chat-header-more-menu" />);

    await user.keyboard("{Escape}");

    expect(screen.getByTestId("chat-header-more-menu")).toHaveFocus();
    expect(document.body).not.toHaveFocus();
  });
});
