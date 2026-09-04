import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { Alert, AlertDescription, AlertTitle } from "../alert";

const renderAlert = () =>
  render(
    <Alert>
      <AlertTitle>Flow saved</AlertTitle>
      <AlertDescription>Your changes are stored.</AlertDescription>
    </Alert>,
  );

describe("Alert accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = renderAlert();

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression lock: Alert ships role="alert" so its content is announced
  // by screen readers when it appears.
  it("should_expose_alert_role", () => {
    renderAlert();

    expect(screen.getByRole("alert")).toHaveTextContent("Flow saved");
  });
});
