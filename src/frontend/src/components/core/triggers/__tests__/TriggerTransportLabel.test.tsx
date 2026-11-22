import { render, screen } from "@testing-library/react";
import type { TriggerState } from "@/controllers/API/queries/triggers";
import TriggerTransportLabel from "../TriggerTransportLabel";
import { makeTrigger } from "./fixtures";

const IN_ONE_HOUR = new Date(Date.now() + 60 * 60 * 1000).toISOString();
const AN_HOUR_AGO = new Date(Date.now() - 60 * 60 * 1000).toISOString();

const schedule = (state: TriggerState, nextFireAt: string | null) =>
  makeTrigger({
    kind: "schedule",
    provider: null,
    connection_id: null,
    config: { cron_expression: "0 3 * * *", timezone: "UTC" },
    state,
    next_fire_at: nextFireAt,
  });

describe("TriggerTransportLabel", () => {
  it("names the next run of an active schedule", () => {
    render(<TriggerTransportLabel trigger={schedule("active", IN_ONE_HOUR)} />);

    expect(screen.getByText(/^Next run in/)).toBeInTheDocument();
  });

  it.each<TriggerState>(["paused", "pending", "error", "expired", "dead"])(
    "promises no run for a %s schedule that kept its stored next fire time",
    (state) => {
      render(<TriggerTransportLabel trigger={schedule(state, IN_ONE_HOUR)} />);

      expect(screen.getByText("Not scheduled")).toBeInTheDocument();
      expect(screen.queryByText(/^Next run/)).not.toBeInTheDocument();
    },
  );

  it("does not report a paused schedule's stale fire time as a past run", () => {
    render(<TriggerTransportLabel trigger={schedule("paused", AN_HOUR_AGO)} />);

    expect(screen.getByText("Not scheduled")).toBeInTheDocument();
  });

  it("says an active schedule without a fire time is not scheduled yet", () => {
    render(<TriggerTransportLabel trigger={schedule("active", null)} />);

    expect(screen.getByText("Not scheduled")).toBeInTheDocument();
  });
});
