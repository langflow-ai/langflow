import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { InspectButton } from "../index";

const baseProps = {
  displayOutputPreview: true,
  unknownOutput: false,
  errorOutput: false,
  isToolMode: false,
  title: "Output",
  onClick: jest.fn(),
  id: "ChatOutput",
};

describe("InspectButton accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <InspectButton
        {...baseProps}
        disabled={false}
        ariaLabel="Inspect output"
      />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_inspect_output_as_accessible_name", () => {
    render(
      <InspectButton
        {...baseProps}
        disabled={false}
        ariaLabel="Inspect output"
      />,
    );

    expect(
      screen.getByRole("button", { name: "Inspect output" }),
    ).toBeInTheDocument();
  });

  it("should_expose_build_component_first_as_accessible_name_when_not_built", () => {
    render(
      <InspectButton
        {...baseProps}
        displayOutputPreview={false}
        disabled={true}
        ariaLabel="Please build the component first"
      />,
    );

    expect(
      screen.getByRole("button", { name: "Please build the component first" }),
    ).toBeInTheDocument();
  });

  it("should_expose_output_cant_be_displayed_as_accessible_name_when_unknown", () => {
    render(
      <InspectButton
        {...baseProps}
        unknownOutput={true}
        disabled={false}
        ariaLabel="Output can't be displayed"
      />,
    );

    expect(
      screen.getByRole("button", { name: "Output can't be displayed" }),
    ).toBeInTheDocument();
  });

  it("should_remain_disabled_while_still_exposing_its_accessible_name", () => {
    render(
      <InspectButton
        {...baseProps}
        disabled={true}
        ariaLabel="Please build the component first"
      />,
    );

    const button = screen.getByRole("button", {
      name: "Please build the component first",
    });
    expect(button).toBeDisabled();
  });
});
