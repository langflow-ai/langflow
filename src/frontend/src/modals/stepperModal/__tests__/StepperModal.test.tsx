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
  });
});
