import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import CrashErrorComponent from "../index";

const renderCrashScreen = (resetErrorBoundary = jest.fn()) =>
  render(
    <CrashErrorComponent
      error={{ message: "boom", stack: "at boom" }}
      resetErrorBoundary={resetErrorBoundary}
    />,
  );

describe("CrashErrorComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = renderCrashScreen();

    expect(await axe(container)).toHaveNoViolations();
  });

  // The crash screen replaces the whole app, so it owns the page's heading
  // structure. Rendering the title as a <p> left the page with zero headings
  // (WCAG 1.3.1 / 2.4.6).
  it("should_expose_the_title_as_the_page_heading", () => {
    renderCrashScreen();

    expect(
      screen.getByRole("heading", { level: 1, name: /unexpected error/i }),
    ).toBeInTheDocument();
  });

  // Nothing announced the failure to a screen reader: the boundary swaps the
  // tree without moving focus, so the region has to assert itself (WCAG 4.1.3).
  it("should_announce_the_failure_through_an_alert_region", () => {
    renderCrashScreen();

    expect(screen.getByRole("alert")).toContainElement(
      screen.getByRole("heading", { level: 1 }),
    );
  });

  // The report action used to be a <button> nested inside an <a href>, which
  // is a nested-interactive violation and gives the anchor no reachable name
  // of its own (WCAG 4.1.2).
  it("should_render_the_report_action_as_a_single_link", () => {
    renderCrashScreen();

    const report = screen.getByRole("link", { name: /report on github/i });
    expect(report).toHaveAttribute(
      "href",
      "https://github.com/langflow-ai/langflow/issues/new",
    );
    expect(report.querySelector("button")).toBeNull();
    expect(
      screen.queryByRole("button", { name: /report on github/i }),
    ).not.toBeInTheDocument();
  });

  it("should_reset_the_error_boundary_from_the_restart_button", async () => {
    const user = userEvent.setup();
    const resetErrorBoundary = jest.fn();
    renderCrashScreen(resetErrorBoundary);

    await user.click(screen.getByRole("button", { name: /restart/i }));

    expect(resetErrorBoundary).toHaveBeenCalled();
  });
});
