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

    it("should render New session and Close buttons", () => {
      render(<AssistantHeader {...defaultProps} />);

      expect(
        screen.getByRole("button", { name: /new session/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /close/i }),
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

  describe("Close button", () => {
    it("should call onClose when clicked", async () => {
      const onClose = jest.fn();
      render(<AssistantHeader {...defaultProps} onClose={onClose} />);

      await userEvent.click(screen.getByRole("button", { name: /close/i }));

      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
