import { render, screen, fireEvent } from "@testing-library/react";
import { AssistantLoadingState } from "../assistant-loading-state";
import type { AgenticProgressState } from "@/controllers/API/queries/agentic";

function createProgress(
  overrides: Partial<AgenticProgressState> = {},
): AgenticProgressState {
  return {
    step: "generating_component",
    attempt: 0,
    maxAttempts: 3,
    message: "Generating response...",
    ...overrides,
  };
}

describe("AssistantLoadingState", () => {
  describe("header", () => {
    it("should show current status message from backend during generation", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({ message: "Generating response..." })}
        />,
      );
      expect(screen.getByText("Generating response...")).toBeInTheDocument();
    });

    it("should update status as steps change", () => {
      const { rerender } = render(
        <AssistantLoadingState
          progress={createProgress({ message: "Generating response..." })}
        />,
      );

      rerender(
        <AssistantLoadingState
          progress={createProgress({
            step: "validating",
            message: "Validating component code...",
          })}
        />,
      );

      expect(
        screen.getByText("Validating component code..."),
      ).toBeInTheDocument();
      // Old message should be gone — single status line, not accumulated
      expect(
        screen.queryByText("Generating response..."),
      ).not.toBeInTheDocument();
    });

    it("should show 'Component ready' when validated", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({
            step: "validated",
            message: "Validated!",
            componentCode: "class X(Component): pass",
          })}
        />,
      );
      expect(screen.getByText("Component ready")).toBeInTheDocument();
    });

    it("should fallback to 'Working...' when no message", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({ message: undefined })}
        />,
      );
      expect(screen.getByText("Working...")).toBeInTheDocument();
    });

    it("should show className badge", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({ className: "MyComp" })}
        />,
      );
      expect(screen.getByText("MyComp")).toBeInTheDocument();
    });
  });

  describe("live streaming code preview", () => {
    it("should show streaming content while generating", () => {
      render(
        <AssistantLoadingState
          progress={createProgress()}
          streamingContent="class MyComp(Component):"
        />,
      );
      expect(screen.getByText("class MyComp(Component):")).toBeInTheDocument();
    });

    it("should not show streaming when no content", () => {
      const { container } = render(
        <AssistantLoadingState
          progress={createProgress()}
          streamingContent=""
        />,
      );
      expect(container.querySelectorAll("pre").length).toBe(0);
    });

    it("should hide streaming once final code arrives", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({
            step: "validating",
            message: "Validating...",
            componentCode: "class X(Component): pass",
          })}
          streamingContent="raw markdown output..."
        />,
      );
      expect(screen.getByText("Code")).toBeInTheDocument();
      expect(
        screen.queryByText("raw markdown output..."),
      ).not.toBeInTheDocument();
    });
  });

  describe("final code preview", () => {
    it("should show collapsible code when componentCode available", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({
            step: "validating",
            message: "Validating...",
            componentCode: "class X(Component): pass",
          })}
        />,
      );
      expect(screen.getByText("Code")).toBeInTheDocument();
    });

    it("should toggle code", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({
            step: "validating",
            message: "Validating...",
            componentCode: "class X(Component): pass",
          })}
        />,
      );

      expect(
        screen
          .getByText("Code")
          .closest("div")
          ?.parentElement?.querySelector("pre"),
      ).toBeTruthy();

      fireEvent.click(screen.getByText("Code").closest("button")!);

      expect(
        screen
          .getByText("Code")
          .closest("div")
          ?.parentElement?.querySelector("pre"),
      ).toBeFalsy();
    });
  });

  describe("validation error", () => {
    it("should show error when present", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({
            step: "validation_failed",
            message: "Validation failed",
            error: "SyntaxError: unexpected indent",
          })}
        />,
      );
      expect(
        screen.getByText("SyntaxError: unexpected indent"),
      ).toBeInTheDocument();
    });

    it("should not show error when empty", () => {
      const { container } = render(
        <AssistantLoadingState progress={createProgress({ error: "" })} />,
      );
      expect(
        container.querySelectorAll("[class*='destructive/5']").length,
      ).toBe(0);
    });
  });

  describe("attempt counter", () => {
    it("should show on retry attempts (attempt > 1, 1-indexed from backend)", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({ attempt: 2, maxAttempts: 3 })}
        />,
      );
      expect(screen.getByText("Attempt 2 of 3")).toBeInTheDocument();
    });

    it("should not show on first attempt", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({ attempt: 1, maxAttempts: 3 })}
        />,
      );
      expect(screen.queryByText(/Attempt/)).not.toBeInTheDocument();
    });

    it("should not render empty padded body for attempt 1 (pre-retry) with no streaming, error, code, or ready state", () => {
      // Attempts are 1-indexed in the UI: attempt=1 is the first attempt, no retry yet.
      // Bug: wrapper used progress.attempt > 0 while the retry counter used > 1,
      // so attempt=1 painted px-4 pb-4 with no visible children below the header.
      // Fix: wrapper now uses > 1 to match the retry counter.
      const { container } = render(
        <AssistantLoadingState
          progress={createProgress({ attempt: 1, maxAttempts: 3 })}
        />,
      );
      expect(container.querySelector(".pb-4")).toBeNull();
    });
  });

  describe("Continue button", () => {
    it("should show when validated with code", () => {
      render(
        <AssistantLoadingState
          progress={createProgress({
            step: "validated",
            message: "Validated!",
            componentCode: "class X(Component): pass",
          })}
        />,
      );
      expect(
        screen.getByRole("button", { name: /Continue/i }),
      ).toBeInTheDocument();
    });

    it("should NOT show during generation", () => {
      render(<AssistantLoadingState progress={createProgress()} />);
      expect(
        screen.queryByRole("button", { name: /Continue/i }),
      ).not.toBeInTheDocument();
    });

    it("should call onValidationComplete on click", () => {
      const onComplete = jest.fn();
      render(
        <AssistantLoadingState
          progress={createProgress({
            step: "validated",
            message: "Validated!",
            componentCode: "class X(Component): pass",
          })}
          onValidationComplete={onComplete}
        />,
      );
      fireEvent.click(screen.getByRole("button", { name: /Continue/i }));
      expect(onComplete).toHaveBeenCalledTimes(1);
    });

    it("should NOT auto-transition", () => {
      const onComplete = jest.fn();
      render(
        <AssistantLoadingState
          progress={createProgress({
            step: "validated",
            message: "Validated!",
            componentCode: "class X(Component): pass",
          })}
          onValidationComplete={onComplete}
        />,
      );
      expect(onComplete).not.toHaveBeenCalled();
    });
  });
});
