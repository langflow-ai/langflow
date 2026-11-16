import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import type { MigrationState } from "@/controllers/API/queries/migration";
import { DestinationsStep } from "../DestinationsStep";

const migration: MigrationState = {
  instance: {
    version: "1.14.0",
    database: { type: "sqlite" },
    knowledge_bases: { local: false },
    files: { storage: "local", local: true },
  },
  record: { target: {}, steps: {}, accepted_findings: [] },
  steps: [],
  blocking_findings: [],
  acceptable_checks: [],
};

const show = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <DestinationsStep
        migration={migration}
        state={{ id: "connect_target", state: "current" }}
      />
    </QueryClientProvider>,
  );

describe("Migration destination required fields", () => {
  it.each([
    "Connection address",
    "Bucket",
    "Folder in the bucket",
    "Access key ID",
    "Secret access key",
  ])("marks %s as required before submission", (label) => {
    show();

    const field = screen.getByLabelText(label);
    const labelRow = screen.getByText(label).parentElement!;
    expect(field).toBeRequired();
    expect(field).toHaveAccessibleName(label);
    expect(within(labelRow).getByText("*")).toBeVisible();
    expect(within(labelRow).getByText("*")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("leaves the endpoint optional with its Amazon S3 guidance", () => {
    show();

    const endpoint = screen.getByLabelText("Endpoint");
    const labelRow = screen.getByText("Endpoint").parentElement!;
    expect(endpoint).not.toBeRequired();
    expect(within(labelRow).queryByText("*")).not.toBeInTheDocument();
    expect(endpoint).toHaveAccessibleDescription("Leave empty for Amazon S3.");
  });
});
