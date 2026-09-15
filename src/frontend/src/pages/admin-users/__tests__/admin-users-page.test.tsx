import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api } from "@/controllers/API/api";
import AdminUsersPage from "../admin-users-page";

jest.mock("@/controllers/API/api", () => ({
  api: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() },
}));
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: { userData: { id: string } }) => unknown) =>
    selector({ userData: { id: "admin-id" } }),
}));
jest.mock("@/components/common/pageLayout", () => ({
  __esModule: true,
  default: ({
    title,
    button,
    children,
  }: {
    title: string;
    button: React.ReactNode;
    children: React.ReactNode;
  }) => (
    <main>
      <h1>{title}</h1>
      {button}
      {children}
    </main>
  ),
}));
jest.mock("@/components/common/paginatorComponent", () => ({
  __esModule: true,
  default: ({
    paginate,
    pageIndex,
  }: {
    paginate: (page: number, size: number) => void;
    pageIndex: number;
  }) => <button onClick={() => paginate(pageIndex + 1, 10)}>Next page</button>,
}));

const initialUsers = [
  { id: "admin-id", username: "admin", is_active: true, is_superuser: true },
  { id: "user-id", username: "alice", is_active: true, is_superuser: false },
];

function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AdminUsersPage />
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  jest.clearAllMocks();
  jest
    .mocked(api.get)
    .mockResolvedValue({ data: { users: initialUsers, total_count: 2 } });
  jest
    .mocked(api.post)
    .mockResolvedValue({ data: { id: "created-id", username: "new-user" } });
  jest.mocked(api.patch).mockResolvedValue({ data: initialUsers[1] });
  jest.mocked(api.delete).mockResolvedValue({ data: {} });
});

it("lets admins change access while protecting their own account", async () => {
  const user = userEvent.setup();
  mount();
  expect(await screen.findByLabelText("Active: admin")).toBeDisabled();
  expect(screen.getByLabelText("Superuser: admin")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Delete admin" })).toBeDisabled();
  await user.click(screen.getByLabelText("Superuser: alice"));
  await waitFor(() =>
    expect(api.patch).toHaveBeenCalledWith(
      expect.stringContaining("/users/user-id"),
      { is_superuser: true },
    ),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("Active: alice")).toBeEnabled(),
  );
  await user.click(screen.getByLabelText("Active: alice"));
  await waitFor(() =>
    expect(api.patch).toHaveBeenCalledWith(
      expect.stringContaining("/users/user-id"),
      { is_active: false },
    ),
  );
});

it("creates a user once and refreshes the account list", async () => {
  const user = userEvent.setup();
  mount();
  await screen.findByText("alice");
  await user.click(screen.getByRole("button", { name: "Add User" }));
  const dialog = within(screen.getByRole("dialog"));
  expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();
  await user.type(dialog.getByLabelText("Username"), "new-user");
  await user.type(dialog.getByLabelText("Password"), "test-only-password");
  await user.click(dialog.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(api.post).toHaveBeenCalledTimes(1);
  expect(api.post).toHaveBeenCalledWith(expect.stringContaining("/users/"), {
    username: "new-user",
    password: "test-only-password",
  });
  expect(api.get).toHaveBeenCalledTimes(2);
});

it("keeps a failed create open without automatically replaying it", async () => {
  const user = userEvent.setup();
  const failure = {
    isAxiosError: true,
    request: {},
    response: { status: 503, data: { detail: "Service unavailable" } },
  };
  jest.mocked(api.post).mockRejectedValue(failure);
  mount();
  await screen.findByText("alice");
  await user.click(screen.getByRole("button", { name: "Add User" }));
  const dialog = within(screen.getByRole("dialog"));
  await user.type(dialog.getByLabelText("Username"), "new-user");
  await user.type(dialog.getByLabelText("Password"), "test-only-password");
  await user.click(dialog.getByRole("button", { name: "Save" }));
  expect(await dialog.findByRole("alert")).toHaveTextContent(
    "Service unavailable",
  );
  expect(api.post).toHaveBeenCalledTimes(1);
  expect(dialog.getByLabelText("Username")).toHaveValue("new-user");
});

it("edits a username without replacing the password when left blank", async () => {
  const user = userEvent.setup();
  mount();
  await user.click(await screen.findByRole("button", { name: "Edit alice" }));
  const dialog = within(screen.getByRole("dialog"));
  await user.clear(dialog.getByLabelText("Username"));
  await user.type(dialog.getByLabelText("Username"), "renamed");
  await user.click(dialog.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(api.patch).toHaveBeenCalledWith(
      expect.stringContaining("/users/user-id"),
      { username: "renamed" },
    ),
  );
});

it("requires deletion confirmation and explains ownership conflicts", async () => {
  const user = userEvent.setup();
  jest.mocked(api.delete).mockRejectedValue({
    response: {
      data: { detail: { code: "RESOURCE_OWNERSHIP_REQUIRES_DISPOSITION" } },
    },
  });
  mount();
  await user.click(await screen.findByRole("button", { name: "Delete alice" }));
  expect(api.delete).not.toHaveBeenCalled();
  const dialog = within(screen.getByRole("dialog"));
  await user.click(dialog.getByRole("button", { name: "Delete" }));
  expect(await dialog.findByRole("alert")).toHaveTextContent(
    "This account still owns resources",
  );
  expect(api.delete).toHaveBeenCalledTimes(1);
  expect(screen.getByText("alice")).toBeVisible();
});

it("resets pagination when submitting a server-side search", async () => {
  const user = userEvent.setup();
  mount();
  await screen.findByText("alice");
  await user.click(screen.getByRole("button", { name: "Next page" }));
  await waitFor(() =>
    expect(api.get).toHaveBeenLastCalledWith(
      expect.any(String),
      expect.objectContaining({
        params: { skip: 10, limit: 10, search: undefined },
      }),
    ),
  );
  fireEvent.change(screen.getByLabelText("Search users"), {
    target: { value: "someone-on-another-page" },
  });
  await user.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() =>
    expect(api.get).toHaveBeenLastCalledWith(
      expect.any(String),
      expect.objectContaining({
        params: { skip: 0, limit: 10, search: "someone-on-another-page" },
      }),
    ),
  );
});
