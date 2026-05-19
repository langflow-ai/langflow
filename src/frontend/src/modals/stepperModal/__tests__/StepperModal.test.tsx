import { TooltipProvider } from "@radix-ui/react-tooltip";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { StepperModal } from "../StepperModal";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <TooltipProvider>{children}</TooltipProvider>
);

const baseProps = {
  open: true,
  onOpenChange: jest.fn(),
  currentStep: 1,
  totalSteps: 1,
  title: "Test Modal Title",
  children: <></>,
};

beforeEach(() => jest.clearAllMocks());

describe("StepperModal", () => {
  describe("Rendering", () => {
    it("renders the modal title when open", () => {
      render(<StepperModal {...baseProps} />, { wrapper: Wrapper });
      expect(
        screen.getByRole("heading", { name: /Test Modal Title/i }),
      ).toBeInTheDocument();
    });

    it("does not render modal content when open=false", () => {
      render(<StepperModal {...baseProps} open={false} />, {
        wrapper: Wrapper,
      });
      expect(
        screen.queryByRole("heading", { name: /Test Modal Title/i }),
      ).not.toBeInTheDocument();
    });

    it("renders description when provided", () => {
      render(
        <StepperModal {...baseProps} description="Step description text" />,
        { wrapper: Wrapper },
      );
      expect(screen.getByText("Step description text")).toBeInTheDocument();
    });

    it("does not render description element when not provided", () => {
      render(<StepperModal {...baseProps} />, { wrapper: Wrapper });
      expect(
        screen.queryByText("Step description text"),
      ).not.toBeInTheDocument();
    });

    it("renders children inside the content area", () => {
      render(
        <StepperModal {...baseProps}>
          <div data-testid="inner-content">Modal body</div>
        </StepperModal>,
        { wrapper: Wrapper },
      );
      expect(screen.getByTestId("inner-content")).toBeInTheDocument();
      expect(screen.getByText("Modal body")).toBeInTheDocument();
    });

    it("renders footer when provided", () => {
      render(
        <StepperModal
          {...baseProps}
          footer={<button data-testid="footer-action">Submit</button>}
        />,
        { wrapper: Wrapper },
      );
      expect(screen.getByTestId("footer-action")).toBeInTheDocument();
    });

    it("does not render footer when not provided", () => {
      render(<StepperModal {...baseProps} />, { wrapper: Wrapper });
      expect(screen.queryByTestId("footer-action")).not.toBeInTheDocument();
    });
  });

  describe("Progress indicator", () => {
    it("shows step count when showProgress=true and totalSteps > 1", () => {
      render(
        <StepperModal
          {...baseProps}
          showProgress
          currentStep={1}
          totalSteps={3}
        />,
        { wrapper: Wrapper },
      );
      expect(screen.getByText(/1/)).toBeInTheDocument();
      expect(screen.getByText(/3/)).toBeInTheDocument();
    });
  });

  describe("Interaction", () => {
    it("calls onOpenChange when the close button is clicked", async () => {
      const onOpenChange = jest.fn();
      const user = userEvent.setup();
      render(<StepperModal {...baseProps} onOpenChange={onOpenChange} />, {
        wrapper: Wrapper,
      });
      await user.click(screen.getByRole("button", { name: /close/i }));
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe("Side panel", () => {
    it("renders side panel content when sidePanel and sidePanelOpen are provided", () => {
      render(
        <StepperModal
          {...baseProps}
          sidePanel={<div data-testid="side-panel-content">Panel</div>}
          sidePanelOpen
        />,
        { wrapper: Wrapper },
      );
      expect(screen.getByTestId("side-panel-content")).toBeInTheDocument();
    });

    it("applies translate offset when side panel is open", () => {
      render(
        <StepperModal
          {...baseProps}
          sidePanel={<div>Panel</div>}
          sidePanelOpen
        />,
        { wrapper: Wrapper },
      );
      // Find DialogContent - it's the element that contains "Test Modal Title"
      const titleElement = screen.getByRole("heading", {
        name: /Test Modal Title/i,
      });
      const dialogContent = titleElement.closest(
        ".flex.max-h-\\[85vh\\]",
      ) as HTMLElement;
      expect(dialogContent).toHaveStyle({ translate: "-150px 0" });
    });

    it("applies no translate offset when side panel is closed", () => {
      render(
        <StepperModal
          {...baseProps}
          sidePanel={<div>Panel</div>}
          sidePanelOpen={false}
        />,
        { wrapper: Wrapper },
      );
      const titleElement = screen.getByRole("heading", {
        name: /Test Modal Title/i,
      });
      const dialogContent = titleElement.closest(
        ".flex.max-h-\\[85vh\\]",
      ) as HTMLElement;
      expect(dialogContent).toHaveStyle({ translate: "0 0" });
    });

    it("applies no translate offset when sidePanel prop is omitted", () => {
      render(<StepperModal {...baseProps} sidePanelOpen />, {
        wrapper: Wrapper,
      });
      const titleElement = screen.getByRole("heading", {
        name: /Test Modal Title/i,
      });
      const dialogContent = titleElement.closest(
        ".flex.max-h-\\[85vh\\]",
      ) as HTMLElement;
      expect(dialogContent).toHaveStyle({ translate: "0 0" });
    });

    it("applies rounded-l-xl and border-r-0 classes when side panel is open", () => {
      render(
        <StepperModal
          {...baseProps}
          sidePanel={<div>Panel</div>}
          sidePanelOpen
        />,
        { wrapper: Wrapper },
      );
      const titleElement = screen.getByRole("heading", {
        name: /Test Modal Title/i,
      });
      const dialogContent = titleElement.closest(
        ".flex.max-h-\\[85vh\\]",
      ) as HTMLElement;
      expect(dialogContent).toHaveClass("rounded-l-xl");
      expect(dialogContent).toHaveClass("rounded-r-none");
      expect(dialogContent).toHaveClass("border-r-0");
      // rounded-xl is still in the class string but rounded-l-xl and rounded-r-none take precedence
    });

    it("applies rounded-xl class when side panel is closed", () => {
      render(
        <StepperModal
          {...baseProps}
          sidePanel={<div>Panel</div>}
          sidePanelOpen={false}
        />,
        { wrapper: Wrapper },
      );
      const titleElement = screen.getByRole("heading", {
        name: /Test Modal Title/i,
      });
      const dialogContent = titleElement.closest(
        ".flex.max-h-\\[85vh\\]",
      ) as HTMLElement;
      expect(dialogContent).toHaveClass("rounded-xl");
      expect(dialogContent).not.toHaveClass("rounded-l-xl");
      expect(dialogContent).not.toHaveClass("rounded-r-none");
      expect(dialogContent).not.toHaveClass("border-r-0");
    });

    it("applies rounded-xl class when sidePanel prop is omitted", () => {
      render(<StepperModal {...baseProps} sidePanelOpen />, {
        wrapper: Wrapper,
      });
      const titleElement = screen.getByRole("heading", {
        name: /Test Modal Title/i,
      });
      const dialogContent = titleElement.closest(
        ".flex.max-h-\\[85vh\\]",
      ) as HTMLElement;
      expect(dialogContent).toHaveClass("rounded-xl");
      expect(dialogContent).not.toHaveClass("rounded-l-xl");
    });
  });
});
