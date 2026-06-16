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

  // Known gap (a11y-action-plan 4.2): the alert display area has no
  // aria-live region, so success/error/notice messages are never announced
  // to screen readers. Fails until the fix lands.
  it("should_announce_alerts_via_live_region", () => {
    const { container } = render(<AlertDisplayArea />);

    const wrapper = container.firstElementChild;
    expect(wrapper).not.toBeNull();
    expect(wrapper).toHaveAttribute("aria-live");
  });
});
