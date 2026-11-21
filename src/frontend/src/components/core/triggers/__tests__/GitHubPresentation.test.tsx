import { render, screen } from "@testing-library/react";
import TriggerSourceCell from "@/pages/SettingsPage/pages/TriggersPage/components/TriggerSourceCell";
import TriggerNodeBadge from "../TriggerNodeBadge";
import TriggerStateBadge from "../TriggerStateBadge";
import { makeTrigger } from "./fixtures";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <svg data-testid={`icon-${name}`} className={className} />
  ),
}));
jest.mock("../hooks/use-trigger-action-runner", () => ({
  useTriggerActionRunner: () => ({
    run: jest.fn(),
    busyId: null,
    dialogs: null,
  }),
}));
jest.mock("../eventsDrawer", () => ({ __esModule: true, default: () => null }));
jest.mock("@/controllers/API/queries/triggers", () => ({
  useTriggerPollingInterval: () => 5000,
}));

it("labels GitHub webhooks as GitHub and Push with the GitHub icon", () => {
  render(
    <TriggerSourceCell
      trigger={makeTrigger({
        provider: "github",
        kind: "github.issue",
        config: { mechanism_id: "github.repository_webhook" },
      })}
    />,
  );
  expect(screen.getByText("GitHub")).toBeInTheDocument();
  expect(screen.getByText("Push")).toBeInTheDocument();
  expect(screen.getByTestId("icon-Github")).toBeInTheDocument();
});

it.each(["node", "table"])(
  "shows a static attention badge for blocked configuration in the %s",
  (surface) => {
    const trigger = makeTrigger({
      state: "pending",
      reason: "config_invalid",
      allowed_actions: [],
      blocked_actions: {},
    });
    render(
      surface === "node" ? (
        <TriggerNodeBadge trigger={trigger} />
      ) : (
        <TriggerStateBadge state={trigger.state} reason={trigger.reason} />
      ),
    );
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
    expect(screen.getByTestId("icon-TriangleAlert")).not.toHaveClass(
      "motion-safe:animate-spin",
    );
    expect(screen.queryByTestId("icon-LoaderCircle")).not.toBeInTheDocument();
  },
);

it("keeps the spinner for setup that is actually pending", () => {
  render(
    <TriggerNodeBadge
      trigger={makeTrigger({ state: "pending", reason: "pending" })}
    />,
  );
  expect(screen.getByText("Pending")).toBeInTheDocument();
  expect(screen.getByTestId("icon-LoaderCircle")).toHaveClass(
    "motion-safe:animate-spin",
  );
});
