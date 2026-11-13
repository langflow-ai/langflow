import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import { api } from "@/controllers/API/api";
import type { MigrationState } from "@/controllers/API/queries/migration";
import { SecretKeyStep } from "../SecretKeyStep";

const migration: MigrationState = {
  instance: {
    version: "1.13.0",
    database: { type: "sqlite" },
    knowledge_bases: { local: false },
    files: { storage: "local", local: false },
    secret_key: { source: "env" },
  },
  record: { target: {}, steps: {}, accepted_findings: [] },
  steps: [],
  blocking_findings: [],
  acceptable_checks: [],
};

const show = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SecretKeyStep
        migration={migration}
        state={{ id: "secret_key", state: "current" }}
      />
    </QueryClientProvider>,
  );

afterEach(() => jest.restoreAllMocks());

it("explains how to verify the destination key before starting the new instance", () => {
  show();

  expect(
    screen.getByText(
      /terminal environment where the new instance's LANGFLOW_SECRET_KEY is configured/,
    ),
  ).toHaveTextContent("The new instance does not need to be running yet.");
});

it.each([
  "e3b0c44298fc", // pragma: allowlist secret -- SHA-256 prefix of empty input.
  "E3B0C44298FC", // pragma: allowlist secret -- SHA-256 prefix of empty input.
])(
  "identifies the empty-input fingerprint %s before sending a verification request",
  async (fingerprint) => {
    const user = userEvent.setup();
    const post = jest.spyOn(api, "post");
    show();

    const field = screen.getByLabelText("What the command printed");
    await user.type(field, fingerprint);
    await user.click(screen.getByRole("button", { name: "Verify" }));

    expect(post).not.toHaveBeenCalled();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(
      /LANGFLOW_SECRET_KEY is unset or empty/,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Set it to this instance's secret key in the destination's terminal environment, then rerun the command and paste the new result.",
    );
  },
);

it("retries verification after the empty-key fingerprint is replaced", async () => {
  const user = userEvent.setup();
  const post = jest.spyOn(api, "post").mockRejectedValue(
    Object.assign(new AxiosError("Request failed"), {
      response: {
        status: 400,
        data: { detail: { code: "fingerprint_mismatch" } },
      },
    }),
  );
  show();
  const field = screen.getByLabelText("What the command printed");
  await user.type(field, "e3b0c44298fc"); // pragma: allowlist secret -- SHA-256 prefix of empty input.
  await user.click(screen.getByRole("button", { name: "Verify" }));

  await user.clear(field);
  await user.type(field, "0123456789ab");
  await user.click(screen.getByRole("button", { name: "Verify" }));

  expect(post).toHaveBeenCalledTimes(1);
  expect(post).toHaveBeenCalledWith(
    expect.stringContaining("secret-key/verify"),
    { fingerprint: "0123456789ab" },
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This doesn't match this instance's key.",
  );
  expect(
    screen.queryByText(/LANGFLOW_SECRET_KEY is unset or empty/),
  ).not.toBeInTheDocument();
});
