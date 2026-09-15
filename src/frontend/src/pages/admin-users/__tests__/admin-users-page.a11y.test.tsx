import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api } from "@/controllers/API/api";
import { axe } from "@/utils/a11y-test";
import AdminUsersPage from "../admin-users-page";

jest.mock("@/controllers/API/api", () => ({
  api: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() },
}));
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: { userData: { id: string } }) => unknown) =>
    selector({ userData: { id: "admin-id" } }),
}));

const users = [
  { id: "admin-id", username: "admin", is_active: true, is_superuser: true },
  { id: "user-id", username: "alice", is_active: true, is_superuser: false },
];

function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <main>
        <h2>Administration</h2>
        <AdminUsersPage />
      </main>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(api.get).mockResolvedValue({ data: { users, total_count: 2 } });
});

it("exposes named table controls and disabled self-account actions", async () => {
  const { baseElement } = mount();
  const table = within(await screen.findByRole("table", { name: "Users" }));
  expect(table.getAllByRole("columnheader")).toHaveLength(4);
  expect(table.getByRole("checkbox", { name: "Active: admin" })).toBeDisabled();
  expect(
    table.getByRole("checkbox", { name: "Superuser: admin" }),
  ).toBeDisabled();
  expect(table.getByRole("button", { name: "Delete admin" })).toBeDisabled();
  expect(await axe(baseElement)).toHaveNoViolations();
});

it("announces the loading state", async () => {
  jest.mocked(api.get).mockReturnValue(new Promise(() => {}));
  const { baseElement } = mount();
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
  expect(await axe(baseElement)).toHaveNoViolations();
});

it("keeps an empty result table accessible", async () => {
  jest
    .mocked(api.get)
    .mockResolvedValue({ data: { users: [], total_count: 0 } });
  const { baseElement } = mount();
  await screen.findByText("No users found.");
  expect(await axe(baseElement)).toHaveNoViolations();
});

it("announces a load failure with a keyboard-accessible retry", async () => {
  jest.mocked(api.get).mockRejectedValue({
    isAxiosError: true,
    response: { status: 403, data: { detail: "Access denied" } },
  });
  const { baseElement } = mount();
  expect(await screen.findByRole("alert")).not.toBeEmptyDOMElement();
  expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
  expect(await axe(baseElement)).toHaveNoViolations();
});

it.each(["Add User", "Edit alice", "Delete alice"])(
  "%s dialog has an accessible name and returns keyboard focus on Escape",
  async (action) => {
    const user = userEvent.setup();
    const { baseElement } = mount();
    const trigger = await screen.findByRole("button", { name: action });
    trigger.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("dialog")).toHaveAccessibleName();
    expect(screen.getByRole("dialog")).toHaveAccessibleDescription();
    expect(await axe(baseElement)).toHaveNoViolations();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(trigger).toHaveFocus());
  },
);

it("announces a failed create while preserving the named form fields", async () => {
  jest.mocked(api.post).mockRejectedValue({
    response: { status: 503, data: { detail: "Service unavailable" } },
  });
  const user = userEvent.setup();
  const { baseElement } = mount();
  await user.click(await screen.findByRole("button", { name: "Add User" }));
  const dialog = within(screen.getByRole("dialog"));
  await user.type(dialog.getByLabelText("Username"), "new-user");
  await user.type(dialog.getByLabelText("Password"), "test-only-password");
  await user.click(dialog.getByRole("button", { name: "Save" }));
  expect(await dialog.findByRole("alert")).toHaveTextContent(
    "Service unavailable",
  );
  expect(dialog.getByLabelText("Username")).toHaveValue("new-user");
  expect(await axe(baseElement)).toHaveNoViolations();
});
