import { render, screen, waitFor } from "@testing-library/react";
import { useClosedTriggerAriaControls } from "../use-closed-trigger-aria-controls";

const Trigger = ({
  controls,
  expanded,
  triggerKey,
}: {
  controls: string;
  expanded: boolean;
  triggerKey: string;
}) => {
  const ref = useClosedTriggerAriaControls<HTMLButtonElement>(null);

  return (
    <button
      aria-controls={controls}
      aria-expanded={expanded}
      key={triggerKey}
      ref={ref}
      type="button"
    >
      Trigger
    </button>
  );
};

describe("useClosedTriggerAriaControls", () => {
  it("should_restore_controls_when_trigger_opens", async () => {
    const { rerender } = render(
      <Trigger controls="content-one" expanded={false} triggerKey="one" />,
    );

    const trigger = screen.getByRole("button", { name: "Trigger" });
    await waitFor(() => expect(trigger).not.toHaveAttribute("aria-controls"));

    rerender(
      <Trigger controls="content-one" expanded={true} triggerKey="one" />,
    );

    await waitFor(() =>
      expect(trigger).toHaveAttribute("aria-controls", "content-one"),
    );
  });

  it("should_rebind_when_trigger_node_changes", async () => {
    const { rerender } = render(
      <Trigger controls="content-one" expanded={false} triggerKey="one" />,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Trigger" }),
      ).not.toHaveAttribute("aria-controls"),
    );

    rerender(
      <Trigger controls="content-two" expanded={false} triggerKey="two" />,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Trigger" }),
      ).not.toHaveAttribute("aria-controls"),
    );
  });
});
