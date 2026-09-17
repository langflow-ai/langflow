import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ConnectionRead } from "@/controllers/API/queries/connections/use-get-connections";
import { useGetConnections } from "@/controllers/API/queries/connections/use-get-connections";
import ConnectionRefComponent from "../index";

// cmdk scrolls the highlighted item into view; jsdom has no layout.
Element.prototype.scrollIntoView = jest.fn();

jest.mock("@/controllers/API/queries/connections/use-get-connections", () => ({
  useGetConnections: jest.fn(),
}));

const CALENDAR_READ =
  "https://www.googleapis.com/auth/calendar.events.readonly";
const GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send";

const mockUseGetConnections = useGetConnections as unknown as jest.Mock;
const mockRefetch = jest.fn();

function connection(overrides: Partial<ConnectionRead> = {}): ConnectionRead {
  return {
    id: "c1",
    owner_id: "u1",
    ownership_mode: "user",
    provider_key: "google",
    name: "work",
    display_name: "Work Google",
    status: "ready",
    health: "healthy",
    granted_scopes: [CALENDAR_READ],
    executing_identity: { identity: "user_delegated" },
    allow_non_interactive: false,
    has_credentials: true,
    health_checked_at: null,
    created_at: "2026-09-16T10:00:00",
    updated_at: "2026-09-16T10:00:00",
    ...overrides,
  };
}

function setConnections(
  connections: ConnectionRead[],
  state: Record<string, unknown> = {},
) {
  mockUseGetConnections.mockReturnValue({
    data: connections,
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: mockRefetch,
    ...state,
  });
}

function renderPicker(props: Record<string, unknown> = {}) {
  const handleOnNewValue = jest.fn();
  render(
    <ConnectionRefComponent
      id="connectionref_connection"
      value=""
      editNode={false}
      disabled={false}
      handleOnNewValue={handleOnNewValue}
      provider="google"
      requiredScopes={[CALENDAR_READ]}
      {...props}
    />,
  );
  return { handleOnNewValue };
}

describe("ConnectionRefComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setConnections([connection()]);
  });

  it("asks the API only for the field's provider", () => {
    renderPicker();
    expect(mockUseGetConnections).toHaveBeenCalledWith(
      { provider: "google" },
      { enabled: true },
    );
  });

  it("prompts for a selection when the field is empty", () => {
    renderPicker();
    expect(screen.getByTestId("connectionref_connection")).toHaveTextContent(
      "Select a google connection",
    );
  });

  it("stores the handle, not the connection id, when one is picked", async () => {
    const { handleOnNewValue } = renderPicker();
    await userEvent.click(screen.getByTestId("connectionref_connection"));
    await userEvent.click(
      await screen.findByTestId("connection-option-google/work"),
    );
    await waitFor(() =>
      expect(handleOnNewValue).toHaveBeenCalledWith({ value: "google/work" }),
    );
  });

  it("shows the selected handle on the trigger", () => {
    renderPicker({ value: "google/work" });
    expect(
      screen.getByTestId("value-connection-connectionref_connection"),
    ).toHaveTextContent("google/work");
  });

  it("names the missing scope on a connection that cannot run the action", async () => {
    renderPicker({ requiredScopes: [CALENDAR_READ, GMAIL_SEND] });
    await userEvent.click(screen.getByTestId("connectionref_connection"));
    expect(
      await screen.findByTestId("connection-option-google/work"),
    ).toHaveTextContent("Missing gmail.send");
  });

  it("flags a stored handle whose connection no longer exists", () => {
    setConnections([]);
    renderPicker({ value: "google/deleted" });
    const trigger = screen.getByTestId("connectionref_connection");
    expect(trigger).toHaveTextContent("google/deleted");
    expect(trigger).toHaveTextContent("not found");
  });

  it("explains the empty state instead of showing a blank list", async () => {
    setConnections([]);
    renderPicker();
    await userEvent.click(screen.getByTestId("connectionref_connection"));
    expect(
      await screen.findByText(/No google connections yet/i),
    ).toBeInTheDocument();
  });

  it("survives a response that is not a list", async () => {
    mockUseGetConnections.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: mockRefetch,
    });
    renderPicker();
    await userEvent.click(screen.getByTestId("connectionref_connection"));
    expect(
      await screen.findByText(/No google connections yet/i),
    ).toBeInTheDocument();
  });

  it("reports a failed load rather than an empty list", async () => {
    setConnections([], { isError: true });
    renderPicker();
    await userEvent.click(screen.getByTestId("connectionref_connection"));
    expect(
      await screen.findByText(/Could not load connections/i),
    ).toBeInTheDocument();
  });

  it("clears the field back to an empty handle", async () => {
    const { handleOnNewValue } = renderPicker({ value: "google/work" });
    await userEvent.click(screen.getByTestId("connectionref_connection"));
    await userEvent.click(
      await screen.findByTestId("clear-connection-connectionref_connection"),
    );
    expect(handleOnNewValue).toHaveBeenCalledWith({ value: "" });
  });

  it("refetches on demand so a connection made in another tab shows up", async () => {
    renderPicker();
    await userEvent.click(screen.getByTestId("connectionref_connection"));
    await userEvent.click(
      await screen.findByTestId("refresh-connections-connectionref_connection"),
    );
    expect(mockRefetch).toHaveBeenCalled();
  });

  it("lists the scopes the action requires", async () => {
    renderPicker();
    await userEvent.click(screen.getByTestId("connectionref_connection"));
    expect(
      await screen.findByText(/Requires calendar.events.readonly/i),
    ).toBeInTheDocument();
  });
});
