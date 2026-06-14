import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AssistantHeader } from "../assistant-header";

jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon({ name }: { name: string }) {
    return <span data-testid={`icon-${name}`} />;
  };
});

describe("AssistantHeader", () => {
  const defaultProps = {
    onClose: jest.fn(),
    onNewSession: jest.fn(),
    hasMessages: false,
    sessions: [],
    activeSessionId: "test-session",
    onSelectSession: jest.fn(),
    onDeleteSession: jest.fn(),
    isExpanded: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("rendering", () => {
    it("should display 'Langflow Assistant' title", () => {
      render(<AssistantHeader {...defaultProps} />);

      expect(screen.getByText("Langflow Assistant")).toBeInTheDocument();
    });

    it("should render New session button", () => {
      render(<AssistantHeader {...defaultProps} />);

      expect(
        screen.getByRole("button", { name: /new session/i }),
      ).toBeInTheDocument();
    });
  });

  describe("New session button", () => {
    it("should be disabled when hasMessages is false", () => {
      render(<AssistantHeader {...defaultProps} hasMessages={false} />);

      expect(
        screen.getByRole("button", { name: /new session/i }),
      ).toBeDisabled();
    });

    it("should be enabled when hasMessages is true", () => {
      render(<AssistantHeader {...defaultProps} hasMessages={true} />);

      expect(
        screen.getByRole("button", { name: /new session/i }),
      ).toBeEnabled();
    });

    it("should call onNewSession when clicked", async () => {
      const onNewSession = jest.fn();
      render(
        <AssistantHeader
          {...defaultProps}
          hasMessages={true}
          onNewSession={onNewSession}
        />,
      );

      await userEvent.click(
        screen.getByRole("button", { name: /new session/i }),
      );

      expect(onNewSession).toHaveBeenCalledTimes(1);
    });
  });

  describe("skip-all badge", () => {
    it("should_not_render_skip_all_badge_when_skipAll_is_false", () => {
      render(<AssistantHeader {...defaultProps} skipAll={false} />);
      expect(
        screen.queryByTestId("assistant-skip-all-badge"),
      ).not.toBeInTheDocument();
    });

    it("should_render_skip_all_badge_when_skipAll_is_true", () => {
      // Badge sits next to the title to remind the user that gates are
      // being auto-approved — without it, skip-all is invisible after the
      // toggle's inline message scrolls out of view.
      render(<AssistantHeader {...defaultProps} skipAll={true} />);
      expect(
        screen.getByTestId("assistant-skip-all-badge"),
      ).toBeInTheDocument();
    });
  });
});
