import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SafetySummary } from "@/controllers/API/queries/evals/types";
import { axe } from "@/utils/a11y-test";
import SafetyKpis from "../components/SafetyKpis";

const SUMMARY: SafetySummary = {
  checks: ["off_topic", "jailbreak"],
  judged: 10,
  skipped: 0,
  safe: 0.8,
  rates: { off_topic: 0.1, jailbreak: 0.1 },
  attacks: { total: 4, resisted: 3 },
};

describe("SafetyKpis", () => {
  it("should show the safe rate, each check and the resisted attacks", () => {
    render(<SafetyKpis summary={SUMMARY} active={null} onSelect={jest.fn()} />);
    expect(screen.getByTestId("run-safety-off_topic")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("run-safety")).toHaveTextContent("3");
  });

  it("should select a check and clear it on a second press", async () => {
    const onSelect = jest.fn();
    const { rerender } = render(
      <SafetyKpis summary={SUMMARY} active={null} onSelect={onSelect} />,
    );
    await userEvent.click(screen.getByTestId("run-safety-jailbreak"));
    expect(onSelect).toHaveBeenLastCalledWith("jailbreak");
    rerender(
      <SafetyKpis summary={SUMMARY} active="jailbreak" onSelect={onSelect} />,
    );
    await userEvent.click(screen.getByTestId("run-safety-jailbreak"));
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });

  it("should have no accessibility violations", async () => {
    const { container } = render(
      <SafetyKpis summary={SUMMARY} active="off_topic" onSelect={jest.fn()} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
