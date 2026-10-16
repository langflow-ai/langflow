import { fireEvent, render, screen, within } from "@testing-library/react";
import ScopeChecklist from "../components/ScopeChecklist";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

it("lists each action for a shared scope and distinguishes conditional use", () => {
  const toggle = jest.fn();
  render(
    <ScopeChecklist
      providerId="google"
      scopes={["https://www.googleapis.com/auth/drive.file", "openid"]}
      selected={new Set()}
      onToggle={toggle}
      requirements={[
        {
          capabilityId: "search",
          displayName: "Search files",
          risk: "read",
          requiredScopes: ["drive.file"],
          conditionalScopes: [],
        },
        {
          capabilityId: "send",
          displayName: "Send attachments",
          risk: "write",
          requiredScopes: [],
          conditionalScopes: [
            {
              scope: "drive.file",
              condition: { kind: "input_truthy", input: "attachments" },
            },
          ],
        },
        {
          capabilityId: "delete",
          displayName: "Delete file",
          risk: "destructive",
          requiredScopes: ["drive.file"],
          conditionalScopes: [],
        },
      ]}
    />,
  );
  const scope = screen.getByTestId(
    "connection-scope-https://www.googleapis.com/auth/drive.file",
  );
  const row = within(scope.closest("label")!);
  expect(row.getByText("Search files")).toBeVisible();
  expect(row.getByText("Read")).toBeVisible();
  expect(row.getByText("Send attachments")).toBeVisible();
  expect(row.getByText("Write")).toBeVisible();
  expect(row.getByText("For some inputs")).toBeVisible();
  expect(row.getByText("Destructive")).toBeVisible();
  const identity = screen.getByTestId("connection-scope-openid");
  expect(
    within(identity.closest("label")!).queryByText("Write"),
  ).not.toBeInTheDocument();
  fireEvent.click(scope);
  expect(toggle).toHaveBeenCalledWith(
    "https://www.googleapis.com/auth/drive.file",
    true,
  );
});
