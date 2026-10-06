import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import type { ReactElement } from "react";
import { api } from "@/controllers/API/api";
import type {
  MigrationState,
  MigrationStepState,
} from "@/controllers/API/queries/migration";
import { DestinationsStep } from "../DestinationsStep";

// No request leaves these tests. A test that submits first makes the connection fail, as it does when the server is gone.
const show = (ui: ReactElement) =>
  render(
    <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>,
  );
const unreachable = () =>
  new AxiosError("Network Error", AxiosError.ERR_NETWORK);

afterEach(() => jest.restoreAllMocks());

const migration = (
  instance: Partial<MigrationState["instance"]> = {},
  record: Partial<MigrationState["record"]> = {},
): MigrationState => ({
  instance: {
    version: "1.13.0",
    database: { type: "sqlite" },
    knowledge_bases: { local: false },
    files: { storage: "local", local: false },
    ...instance,
  },
  record: { target: {}, steps: {}, accepted_findings: [], ...record },
  steps: [],
  blocking_findings: [],
  acceptable_checks: [],
});

const step = (
  id: MigrationStepState["id"],
  state: MigrationStepState["state"],
  reason?: string,
): MigrationStepState => ({ id, state, reason });

describe("Where your data goes", () => {
  it("asks a SQLite instance with nothing else on its server for a database only", () => {
    show(
      <DestinationsStep
        migration={migration()}
        state={step("connect_target", "current")}
      />,
    );

    // The address holds a password.
    const address = screen.getByLabelText("Connection address");
    expect(address).toHaveAttribute("type", "password");
    expect(address).toBeRequired();
    // How to write it is read out with the field.
    expect(address).toHaveAccessibleDescription(
      /^A new, empty PostgreSQL database/,
    );
    expect(screen.queryByText("Knowledge bases")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Bucket")).not.toBeInTheDocument();
  });

  it("asks a PostgreSQL instance only for what it keeps on its own server", () => {
    show(
      <DestinationsStep
        migration={migration({
          database: {
            type: "postgresql",
            location: "db.internal:5432/langflow",
          },
          knowledge_bases: { local: true },
          files: { storage: "local", local: true },
        })}
        state={step("connect_target", "current")}
      />,
    );

    expect(
      screen.queryByLabelText("Connection address"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/db\.internal:5432\/langflow/)).toBeInTheDocument();
    expect(screen.getByText(/needs the pgvector extension/)).toBeVisible();
    for (const label of [
      "Bucket",
      "Folder in the bucket",
      "Access key ID",
      "Secret access key",
    ]) {
      expect(screen.getByLabelText(label)).toBeRequired();
    }
    // Amazon S3 needs no endpoint.
    expect(screen.getByLabelText("Endpoint")).not.toBeRequired();
    expect(screen.getByLabelText("Folder in the bucket")).toHaveValue("files");
    expect(screen.getByLabelText("Access key ID")).not.toHaveAttribute(
      "type",
      "password",
    );
    expect(screen.getByLabelText("Secret access key")).toHaveAttribute(
      "type",
      "password",
    );
  });

  it("shows a done step as facts, and asks again without the secrets it never got back", async () => {
    show(
      <DestinationsStep
        migration={migration(
          { files: { storage: "local", local: true } },
          {
            destinations: {
              database: { location: "db.internal:5432/target" },
              files: {
                bucket: "acme",
                prefix: "moved",
                endpoint_url: "https://s3.internal",
              },
              results: { database: { ok: true }, files: { ok: true } },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "done")}
      />,
    );

    expect(screen.getByText(/^Saved .* by alice\.$/)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Connection address"),
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Change or enter again" }),
    );

    expect(screen.getByLabelText("Bucket")).toHaveValue("acme");
    expect(screen.getByLabelText("Folder in the bucket")).toHaveValue("moved");
    expect(screen.getByLabelText("Endpoint")).toHaveValue(
      "https://s3.internal",
    );
    expect(screen.getByLabelText("Connection address")).toHaveValue("");
    expect(screen.getByLabelText("Secret access key")).toHaveValue("");
    // The last test was of what is saved, and says nothing about what the admin types now.
    expect(screen.queryByText("Ready.")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByLabelText("Bucket")).not.toBeInTheDocument();
  });

  it("puts what the server found next to each destination, after a reload too", () => {
    show(
      <DestinationsStep
        migration={migration(
          { files: { storage: "local", local: true } },
          {
            destinations: {
              database: { location: "db.internal:5432/target" },
              files: { bucket: "acme", prefix: "files" },
              results: {
                database: { ok: true },
                files: {
                  ok: false,
                  code: "bucket_denied",
                  reason: "An error occurred (403) when calling HeadBucket",
                },
              },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "blocked", "bucket_denied")}
      />,
    );

    expect(screen.getByText("Ready.")).toBeInTheDocument();
    const refusal = screen.getByRole("alert");
    expect(refusal).toHaveTextContent(
      "Access denied. Check the keys and the bucket's permissions.",
    );
    // The server's own words say what it ran into. They are English in every language.
    expect(refusal).toHaveTextContent(
      "An error occurred (403) when calling HeadBucket",
    );
    expect(
      screen.getByText("An error occurred (403) when calling HeadBucket"),
    ).toHaveAttribute("lang", "en");
    // Either key can be the wrong one.
    for (const label of ["Access key ID", "Secret access key"]) {
      const key = screen.getByLabelText(label);
      expect(key).toHaveAttribute("aria-invalid", "true");
      expect(key).toHaveAccessibleDescription(/^Access denied\./);
    }
    expect(screen.getByLabelText("Bucket")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
    expect(screen.getByLabelText("Connection address")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
  });

  it("marks the bucket when it is the bucket that is missing, and gives the server's code when it has no line for it", () => {
    show(
      <DestinationsStep
        migration={migration(
          { files: { storage: "local", local: true } },
          {
            destinations: {
              results: {
                database: { ok: false, code: "address_too_new" },
                files: { ok: false, code: "bucket_missing" },
              },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "blocked", "address_too_new")}
      />,
    );

    const [database, files] = screen.getAllByRole("alert");
    expect(database).toHaveTextContent(/^address_too_new$/);
    expect(files).toHaveTextContent(/^Can't find this bucket\.$/);
    for (const label of ["Connection address", "Bucket"]) {
      expect(screen.getByLabelText(label)).toHaveAttribute(
        "aria-invalid",
        "true",
      );
    }
    expect(screen.getByLabelText("Secret access key")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
  });

  it("marks the endpoint when the bucket's storage does not answer", () => {
    show(
      <DestinationsStep
        migration={migration(
          { files: { storage: "local", local: true } },
          {
            destinations: {
              results: { files: { ok: false, code: "bucket_unreachable" } },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "blocked", "bucket_unreachable")}
      />,
    );

    const endpoint = screen.getByLabelText("Endpoint");
    expect(endpoint).toHaveAttribute("aria-invalid", "true");
    expect(endpoint).toHaveAccessibleDescription(
      /^Can't reach this bucket\. Check the endpoint\./,
    );
    expect(screen.getByLabelText("Bucket")).toHaveAttribute(
      "aria-invalid",
      "false",
    );
  });

  it("shows a save that never reached the server as failed, and leaves out what the last test found", async () => {
    jest.spyOn(api, "put").mockRejectedValue(unreachable());
    show(
      <DestinationsStep
        migration={migration(
          {},
          {
            destinations: {
              results: { database: { ok: false, code: "db_unreachable" } },
              saved_by: "alice",
              saved_at: "2026-10-06T12:00:00Z",
            },
          },
        )}
        state={step("connect_target", "blocked", "db_unreachable")}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Can't connect to this database.",
    );

    await userEvent.type(
      screen.getByLabelText("Connection address"),
      "postgresql://db.internal/langflow",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Test and save" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /^Something went wrong\. Try again\.$/,
    );
  });
});
