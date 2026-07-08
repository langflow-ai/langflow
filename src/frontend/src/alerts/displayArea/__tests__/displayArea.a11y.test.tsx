import { act, render, screen } from "@testing-library/react";
import useAlertStore from "@/stores/alertStore";

// ErrorAlert pulls in react-markdown (ESM-only in jest); the alert bodies
// are not under test here — only the display area wrapper semantics.
jest.mock("@/alerts/error", () => ({
  __esModule: true,
  default: ({ title }: { title: string }) => <div>{title}</div>,
}));
jest.mock("@/alerts/notice", () => ({
  __esModule: true,
  default: ({ title }: { title: string }) => <div>{title}</div>,
}));

import AlertDisplayArea from "../index";

describe("AlertDisplayArea accessibility", () => {
  beforeEach(() => {
    act(() => {
      useAlertStore.setState({ tempNotificationList: [] });
    });
  });

  it("should_render_alert_content", () => {
    render(<AlertDisplayArea />);

    act(() => {
      useAlertStore.getState().setSuccessData({ title: "Flow saved" });
    });

    expect(screen.getByText("Flow saved")).toBeInTheDocument();
  });

  it("keeps_live_regions_mounted_before_alerts_are_inserted", () => {
    const { container } = render(<AlertDisplayArea />);

    expect(
      container.querySelector('[aria-live="assertive"]'),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("announces_success_and_notice_alerts_politely", () => {
    render(<AlertDisplayArea />);

    act(() => {
      useAlertStore.getState().setSuccessData({ title: "Flow saved" });
    });

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveAttribute("aria-atomic", "true");
    expect(status).toHaveTextContent("Flow saved");
  });

  it("announces_error_alerts_assertively", () => {
    const { container } = render(<AlertDisplayArea />);

    act(() => {
      useAlertStore.getState().setErrorData({ title: "Build failed" });
    });

    const assertiveRegion = container.querySelector('[aria-live="assertive"]');
    expect(assertiveRegion).toHaveAttribute("aria-atomic", "true");
    expect(assertiveRegion).toHaveTextContent("Build failed");

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Build failed");
  });
});
