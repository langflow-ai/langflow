import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { StepperModalFooter } from "../StepperModalFooter";

const baseProps = {
  currentStep: 1,
  totalSteps: 2,
  onBack: jest.fn(),
  onNext: jest.fn(),
  onSubmit: jest.fn(),
};

beforeEach(() => jest.clearAllMocks());

describe("StepperModalFooter", () => {
  describe("Navigation buttons", () => {
    it("shows Next Step button on step 1 of 2", () => {
      render(<StepperModalFooter {...baseProps} />);
      expect(
        screen.getByRole("button", { name: /Next Step/i }),
      ).toBeInTheDocument();
    });

    it("shows Submit button on the final step", () => {
      render(
        <StepperModalFooter
          {...baseProps}
          currentStep={2}
          totalSteps={2}
          submitTestId="submit-btn"
        />,
      );
      expect(screen.getByTestId("submit-btn")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Next Step/i }),
      ).not.toBeInTheDocument();
    });

    it("does not show Back button on step 1", () => {
      render(<StepperModalFooter {...baseProps} currentStep={1} />);
      expect(
        screen.queryByRole("button", { name: /^Back$/i }),
      ).not.toBeInTheDocument();
    });

    it("shows Back button on step > 1", () => {
      render(
        <StepperModalFooter {...baseProps} currentStep={2} totalSteps={2} />,
      );
      expect(
        screen.getByRole("button", { name: /^Back$/i }),
      ).toBeInTheDocument();
    });

    it("fires onNext when Next Step is clicked", async () => {
      const onNext = jest.fn();
      const user = userEvent.setup();
      render(<StepperModalFooter {...baseProps} onNext={onNext} />);
      await user.click(screen.getByRole("button", { name: /Next Step/i }));
      expect(onNext).toHaveBeenCalledTimes(1);
    });

    it("fires onBack when Back is clicked", async () => {
      const onBack = jest.fn();
      const user = userEvent.setup();
      render(
        <StepperModalFooter
          {...baseProps}
          currentStep={2}
          totalSteps={2}
          onBack={onBack}
          submitTestId="submit-btn"
        />,
      );
      await user.click(screen.getByRole("button", { name: /^Back$/i }));
      expect(onBack).toHaveBeenCalledTimes(1);
    });

    it("fires onSubmit when submit button is clicked", async () => {
      const onSubmit = jest.fn();
      const user = userEvent.setup();
      render(
        <StepperModalFooter
          {...baseProps}
          currentStep={1}
          totalSteps={1}
          onSubmit={onSubmit}
          submitTestId="submit-btn"
        />,
      );
      await user.click(screen.getByTestId("submit-btn"));
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
  });

  describe("Disabled states", () => {
    it("disables Next Step when nextDisabled=true", () => {
      render(<StepperModalFooter {...baseProps} nextDisabled />);
      expect(screen.getByRole("button", { name: /Next Step/i })).toBeDisabled();
    });

    it("disables Submit when submitDisabled=true", () => {
      render(
        <StepperModalFooter
          {...baseProps}
          currentStep={1}
          totalSteps={1}
          submitDisabled
          submitTestId="submit-btn"
        />,
      );
      expect(screen.getByTestId("submit-btn")).toBeDisabled();
    });

    it("disables Submit when isSubmitting=true", () => {
      render(
        <StepperModalFooter
          {...baseProps}
          currentStep={1}
          totalSteps={1}
          isSubmitting
          submitTestId="submit-btn"
        />,
      );
      expect(screen.getByTestId("submit-btn")).toBeDisabled();
    });

    it("enables Next Step when nextDisabled=false", () => {
      render(<StepperModalFooter {...baseProps} nextDisabled={false} />);
      expect(
        screen.getByRole("button", { name: /Next Step/i }),
      ).not.toBeDisabled();
    });
  });

  describe("Help section", () => {
    it("renders a link when helpHref is provided", () => {
      render(
        <StepperModalFooter
          {...baseProps}
          helpHref="https://docs.example.com"
          helpLabel="Docs"
        />,
      );
      const link = screen.getByRole("link", { name: /Docs/i });
      expect(link).toHaveAttribute("href", "https://docs.example.com");
      expect(link).toHaveAttribute("target", "_blank");
    });

    it("renders a button when onHelp is provided and fires onHelp when clicked", async () => {
      const onHelp = jest.fn();
      const user = userEvent.setup();
      render(
        <StepperModalFooter
          {...baseProps}
          onHelp={onHelp}
          helpLabel="Configure Sources"
        />,
      );
      await user.click(
        screen.getByRole("button", { name: /Configure Sources/i }),
      );
      expect(onHelp).toHaveBeenCalledTimes(1);
    });

    it("does not render help element when neither helpHref nor onHelp is provided", () => {
      render(<StepperModalFooter {...baseProps} />);
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });
  });

  describe("Custom labels", () => {
    it("uses custom submitLabel on the final step", () => {
      render(
        <StepperModalFooter
          {...baseProps}
          currentStep={1}
          totalSteps={1}
          submitLabel="Add Sources"
          submitTestId="submit-btn"
        />,
      );
      expect(screen.getByTestId("submit-btn")).toHaveTextContent("Add Sources");
    });

    it("uses custom nextLabel on intermediate steps", () => {
      render(<StepperModalFooter {...baseProps} nextLabel="Continue" />);
      expect(
        screen.getByRole("button", { name: /Continue/i }),
      ).toBeInTheDocument();
    });

    it("uses custom backLabel", () => {
      render(
        <StepperModalFooter
          {...baseProps}
          currentStep={2}
          totalSteps={2}
          backLabel="Previous"
        />,
      );
      expect(
        screen.getByRole("button", { name: /Previous/i }),
      ).toBeInTheDocument();
    });
  });

  describe("Single-step modal", () => {
    it("shows Submit immediately when totalSteps=1", () => {
      render(
        <StepperModalFooter
          {...baseProps}
          currentStep={1}
          totalSteps={1}
          submitTestId="submit-btn"
        />,
      );
      expect(screen.getByTestId("submit-btn")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Next Step/i }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /^Back$/i }),
      ).not.toBeInTheDocument();
    });
  });
});
