import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SidebarProvider } from "@/components/ui/sidebar";

const restoreMock = jest.fn().mockResolvedValue(undefined);
const restoreHookMock = jest.fn();
jest.mock("@/hooks/flows/use-restore-version", () => ({
  __esModule: true,
  default: (...args: unknown[]) => {
    restoreHookMock(...args);
    return { restore: restoreMock, isRestoring: false };
  },
}));

let currentFlowMock: { id: string; version_token?: string | null };
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ currentFlow: currentFlowMock }),
}));

import RestoreVersionButton from "../RestoreVersionButton";

describe("RestoreVersionButton", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    currentFlowMock = { id: "flow-1", version_token: "persisted-token" };
  });

  function renderRestore() {
    return render(
      <SidebarProvider>
        <RestoreVersionButton
          flowId="flow-1"
          versionId="historical-entry"
          versionTag="Before repair"
        />
      </SidebarProvider>,
    );
  }

  it("should restore a historical preview using the current persisted token", async () => {
    const user = userEvent.setup();
    renderRestore();
    await user.click(
      screen.getByRole("button", { name: "Restore", exact: true }),
    );
    await user.click(
      screen.getAllByRole("button", { name: "Restore", exact: true })[1],
    );

    expect(restoreHookMock).toHaveBeenCalledWith("flow-1", "persisted-token");
    expect(restoreMock).toHaveBeenCalledWith("historical-entry", {
      saveDraft: true,
      onSuccess: expect.any(Function),
    });
  });

  it("should not pass a token for a different persisted flow", () => {
    currentFlowMock = { id: "different-flow", version_token: "other-token" };
    renderRestore();

    expect(restoreHookMock).toHaveBeenCalledWith("flow-1", undefined);
  });
});
