import { fireEvent, render, screen } from "@testing-library/react";

// react-markdown / remark-gfm are ESM and break Jest's CJS transformer.
// Mirror the mocks the other assistantPanel tests use.
jest.mock("react-markdown", () => {
  return function MockMarkdown({ children }: { children: string }) {
    return <div data-testid="markdown-content">{children}</div>;
  };
});
jest.mock("remark-gfm", () => () => {});

import { AssistantPlanCard } from "../assistant-plan-card";

describe("AssistantPlanCard", () => {
  describe("pending status", () => {
    it("should_render_markdown_when_status_is_pending", () => {
      render(
        <AssistantPlanCard
          markdown="## Plan\n\nBuild a chatbot."
          status="pending"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      // The mocked Markdown renderer renders the raw string inside its
      // testid container — we only need to know the body reached the
      // Markdown component intact.
      expect(screen.getByTestId("markdown-content")).toHaveTextContent(
        "## Plan",
      );
      expect(screen.getByTestId("markdown-content")).toHaveTextContent(
        "Build a chatbot.",
      );
    });

    it("should_render_continue_button_when_status_is_pending", () => {
      render(
        <AssistantPlanCard
          markdown="x"
          status="pending"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.getByTestId("assistant-plan-continue-button"),
      ).toBeInTheDocument();
    });

    it("should_render_dismiss_button_when_status_is_pending", () => {
      render(
        <AssistantPlanCard
          markdown="x"
          status="pending"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.getByTestId("assistant-plan-dismiss-button"),
      ).toBeInTheDocument();
    });

    it("should_call_onApprove_when_continue_button_clicked", () => {
      const onApprove = jest.fn();
      render(
        <AssistantPlanCard
          markdown="x"
          status="pending"
          onApprove={onApprove}
          onDismiss={jest.fn()}
        />,
      );

      fireEvent.click(screen.getByTestId("assistant-plan-continue-button"));
      expect(onApprove).toHaveBeenCalledTimes(1);
    });

    it("should_call_onDismiss_when_dismiss_button_clicked", () => {
      const onDismiss = jest.fn();
      render(
        <AssistantPlanCard
          markdown="x"
          status="pending"
          onApprove={jest.fn()}
          onDismiss={onDismiss}
        />,
      );

      fireEvent.click(screen.getByTestId("assistant-plan-dismiss-button"));
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });
  });

  describe("approved status", () => {
    it("should_show_approved_label_when_status_is_approved", () => {
      render(
        <AssistantPlanCard
          markdown="x"
          status="approved"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(screen.getByText(/approved/i)).toBeInTheDocument();
    });

    it("should_not_render_action_buttons_when_status_is_approved", () => {
      render(
        <AssistantPlanCard
          markdown="x"
          status="approved"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.queryByTestId("assistant-plan-continue-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("assistant-plan-dismiss-button"),
      ).not.toBeInTheDocument();
    });
  });

  describe("refining status", () => {
    it("should_render_markdown_when_status_is_refining", () => {
      // The card must stay visible during refining so the user can re-read
      // what they're refining.
      render(
        <AssistantPlanCard
          markdown="## Original plan"
          status="refining"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
          onReset={jest.fn()}
        />,
      );
      expect(screen.getByTestId("markdown-content")).toHaveTextContent(
        "## Original plan",
      );
    });

    it("should_render_continue_button_when_status_is_refining", () => {
      // A refined plan can still be approved if the user changes their mind.
      render(
        <AssistantPlanCard
          markdown="x"
          status="refining"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
          onReset={jest.fn()}
        />,
      );
      expect(
        screen.getByTestId("assistant-plan-continue-button"),
      ).toBeInTheDocument();
    });

    it("should_render_reset_button_when_status_is_refining", () => {
      render(
        <AssistantPlanCard
          markdown="x"
          status="refining"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
          onReset={jest.fn()}
        />,
      );
      expect(
        screen.getByTestId("assistant-plan-reset-button"),
      ).toBeInTheDocument();
    });

    it("should_not_render_dismiss_button_when_status_is_refining", () => {
      // Dismiss is the pending→refining trigger. Once refining, the user
      // refines via the input or fully resets via the Reset button.
      render(
        <AssistantPlanCard
          markdown="x"
          status="refining"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
          onReset={jest.fn()}
        />,
      );
      expect(
        screen.queryByTestId("assistant-plan-dismiss-button"),
      ).not.toBeInTheDocument();
    });

    it("should_call_onReset_when_reset_button_clicked", () => {
      const onReset = jest.fn();
      render(
        <AssistantPlanCard
          markdown="x"
          status="refining"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
          onReset={onReset}
        />,
      );
      fireEvent.click(screen.getByTestId("assistant-plan-reset-button"));
      expect(onReset).toHaveBeenCalledTimes(1);
    });

    it("should_show_refining_label_when_status_is_refining", () => {
      render(
        <AssistantPlanCard
          markdown="x"
          status="refining"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
          onReset={jest.fn()}
        />,
      );
      // Loose match so we can iterate copy without breaking tests.
      expect(screen.getByText(/refining/i)).toBeInTheDocument();
    });
  });

  describe("dismissed status", () => {
    it("should_show_dismissed_label_when_status_is_dismissed", () => {
      render(
        <AssistantPlanCard
          markdown="x"
          status="dismissed"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(screen.getByText(/dismissed/i)).toBeInTheDocument();
    });

    it("should_not_render_action_buttons_when_status_is_dismissed", () => {
      render(
        <AssistantPlanCard
          markdown="x"
          status="dismissed"
          onApprove={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.queryByTestId("assistant-plan-continue-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("assistant-plan-dismiss-button"),
      ).not.toBeInTheDocument();
    });
  });
});
