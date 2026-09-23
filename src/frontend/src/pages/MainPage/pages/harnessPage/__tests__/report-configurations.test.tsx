jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));

import { fireEvent, render, screen } from "@testing-library/react";
import type { AgentConfiguration } from "@/controllers/API/queries/folders/use-project-reports";
import { ReportConfigurations } from "../components/report-configurations";
import { selectOption } from "./select-option";

const mockNavigate = jest.fn();
const record: AgentConfiguration = {
  schema_version: 1,
  revision: "a".repeat(64),
  captured_at: "2026-09-15T13:00:00Z",
  flow_id: "agent-flow",
  agent_node_id: "Agent-research",
  flow_revision: "b".repeat(64),
  component_revision: "c".repeat(64),
  model: {
    name: "reviewed-model",
    implementation: "fixture.Model",
    parameters: { temperature: 0.2, api_key: "[redacted]" },
  },
  system_prompt: "Cite retrieved evidence. Keep this exact instruction.",
  runtime: { max_iterations: 8, compaction: "off", tool_policy: "ask" },
  history_messages: 4,
  loaded_history_messages: 2,
  tool_retry_count: 0,
  tools: [],
  flow_bindings: {
    system_prompt: {
      flow_id: "instructions",
      node_id: "Instructions-output",
      output_name: "text",
      revision: "d".repeat(64),
      version_id: "reviewed-snapshot",
    },
  },
};

beforeEach(() => jest.clearAllMocks());

it("shows recorded values and preserves the draft before opening a configured flow", () => {
  const onOpen = jest.fn();
  render(<ReportConfigurations configurations={[record]} onOpen={onOpen} />);
  expect(
    screen.getByText("reviewed-model", { exact: true }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByText("Inspect configuration"));
  expect(screen.getByText(record.system_prompt)).toBeInTheDocument();
  expect(screen.getByText(/reviewed-snapshot/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Open Current Flow" }));
  expect(onOpen).toHaveBeenCalledTimes(1);
  expect(mockNavigate).toHaveBeenCalledWith("/flow/instructions");
});

it("lets the reviewer inspect earlier settings after configuration changes during a run", async () => {
  const newer = {
    ...record,
    revision: "e".repeat(64),
    model: { ...record.model, name: "updated-model" },
    system_prompt: "Updated instructions.",
  };
  render(<ReportConfigurations configurations={[record, newer]} />);
  fireEvent.click(screen.getByText("Inspect configuration"));
  expect(screen.getByText("Updated instructions.")).toBeInTheDocument();
  await selectOption(
    screen.getByRole("combobox", { name: "Recorded configuration" }),
    /^Configuration 1/,
  );
  expect(screen.getByText(record.system_prompt)).toBeInTheDocument();
  expect(screen.queryByText("Updated instructions.")).not.toBeInTheDocument();
});

it("does not substitute current settings for a legacy report without provenance", () => {
  render(<ReportConfigurations configurations={[]} />);
  expect(
    screen.getByText(/This report has no recorded configuration/),
  ).toBeInTheDocument();
  expect(screen.queryByText("Inspect configuration")).not.toBeInTheDocument();
  expect(screen.queryByText("reviewed-model")).not.toBeInTheDocument();
});
