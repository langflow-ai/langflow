import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import { Input } from "../input";
import { Label } from "../label";

const renderLabelledInput = () =>
  render(
    <div>
      <Label htmlFor="flow-name">Flow name</Label>
      <Input id="flow-name" />
    </div>,
  );

describe("Label accessibility", () => {
  it("should_have_no_axe_violations_when_associated_with_a_control", async () => {
    const { container } = renderLabelledInput();

    // `region` is a page-level landmark rule that a bare unit render of a
    // form control pair cannot satisfy.
    expect(
      await axe(container, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("should_name_the_associated_control", () => {
    renderLabelledInput();

    expect(screen.getByLabelText("Flow name")).toBe(
      screen.getByRole("textbox"),
    );
  });

  it("should_move_focus_to_the_control_when_clicked", async () => {
    const user = userEvent.setup();
    renderLabelledInput();

    await user.click(screen.getByText("Flow name"));

    expect(screen.getByRole("textbox")).toHaveFocus();
  });

  it("should_flag_a_label_pointing_at_a_missing_control", async () => {
    // Guards the failure mode this component is most often misused for: a
    // visually correct label whose htmlFor targets nothing, which leaves the
    // control unnamed for screen readers.
    const { container } = render(
      <div>
        <Label htmlFor="does-not-exist">Orphan label</Label>
        <Input id="another-id" />
      </div>,
    );

    const results = await axe(container, {
      rules: { region: { enabled: false } },
    });
    const violationIds = results.violations.map((violation) => violation.id);
    expect(violationIds).toContain("label");
  });
});
