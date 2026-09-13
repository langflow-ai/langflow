import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthorizationAdminRoute } from "../authorization-admin-route";

const mockCapabilities = jest.fn();
jest.mock("@/controllers/API/queries/authorization", () => ({
  useGetAuthorizationCapabilities: () => mockCapabilities(),
}));

function mount(requiresCollaboration = false) {
  render(
    <MemoryRouter initialEntries={["/admin"]}>
      <Routes>
        <Route
          path="admin"
          element={
            <AuthorizationAdminRoute
              requiresCollaboration={requiresCollaboration}
            >
              <h1>User management</h1>
            </AuthorizationAdminRoute>
          }
        />
        <Route path="teams" element={<h1>Teams</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

it("allows verified platform admins to manage accounts when collaboration is disabled", () => {
  mockCapabilities.mockReturnValue({
    data: {
      enforcement_active: false,
      service_ready: false,
      can_administer_platform: true,
    },
  });
  mount();
  expect(
    screen.getByRole("heading", { name: "User management" }),
  ).toBeVisible();
});

it("rejects direct navigation by ordinary users", () => {
  mockCapabilities.mockReturnValue({
    data: {
      enforcement_active: true,
      service_ready: true,
      can_administer_platform: false,
    },
  });
  mount();
  expect(screen.queryByText("User management")).toBeNull();
  expect(screen.getByRole("heading", { name: "Teams" })).toBeVisible();
});

it("fails closed when capability discovery fails even with stale admin data", () => {
  mockCapabilities.mockReturnValue({
    isError: true,
    data: { can_administer_platform: true },
  });
  mount();
  expect(screen.queryByText("User management")).toBeNull();
  expect(screen.getByRole("alert")).toBeVisible();
});

it("retains the readiness requirement for team administration", () => {
  mockCapabilities.mockReturnValue({
    data: {
      enforcement_active: false,
      service_ready: false,
      can_administer_platform: true,
    },
  });
  mount(true);
  expect(screen.queryByText("User management")).toBeNull();
  expect(screen.getByRole("alert")).toBeVisible();
});
