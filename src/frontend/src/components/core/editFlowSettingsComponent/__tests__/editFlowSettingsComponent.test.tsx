import * as Form from "@radix-ui/react-form";
import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { EditFlowSettings } from "../index";

const renderWithForm = (ui: React.ReactElement) =>
  render(<Form.Root>{ui}</Form.Root>);

describe("EditFlowSettings lock switch", () => {
  const defaultProps = {
    name: "My Flow",
    description: "",
    setName: jest.fn(),
    setDescription: jest.fn(),
  };

  it("should_have_no_axe_violations", async () => {
    const { container } = renderWithForm(
      <EditFlowSettings {...defaultProps} />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("exposes a descriptive accessible name on the lock switch", () => {
    renderWithForm(<EditFlowSettings {...defaultProps} />);

    expect(
      screen.getByRole("switch", {
        name: "Lock flow switch",
      }),
    ).toBeInTheDocument();
  });

  it("reflects the locked/unlocked state on the correctly named switch", () => {
    renderWithForm(<EditFlowSettings {...defaultProps} locked={true} />);

    expect(
      screen.getByRole("switch", {
        name: "Lock flow switch",
      }),
    ).toHaveAttribute("aria-checked", "true");
  });
});
