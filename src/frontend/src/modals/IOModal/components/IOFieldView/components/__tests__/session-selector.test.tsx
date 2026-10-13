import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import SessionSelector from "../session-selector";

// The shared Playground stores sessions as `<flowId>:<name>`: the row shows
// and renames the name, while the API still gets the full, scoped id.

const mockUpdateSessionName = jest.fn();
jest.mock("@/controllers/API/queries/messages/use-rename-session", () => ({
  __esModule: true,
  useUpdateSessionName: () => ({ mutate: mockUpdateSessionName }),
}));

jest.mock("@/modals/IOModal/hooks/useGetFlowId", () => ({
  __esModule: true,
  useGetFlowId: () => "flow-1",
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (
    selector: (state: { setNewChatOnPlayground: () => void }) => unknown,
  ) => selector({ setNewChatOnPlayground: jest.fn() }),
}));

jest.mock("@/stores/voiceStore", () => ({
  __esModule: true,
  useVoiceStore: (
    selector: (state: {
      setNewSessionCloseVoiceAssistant: () => void;
    }) => unknown,
  ) => selector({ setNewSessionCloseVoiceAssistant: jest.fn() }),
}));

function renderSelector(session: string) {
  const updateVisibleSession = jest.fn();
  render(
    <TooltipProvider>
      <SessionSelector
        session={session}
        toggleVisibility={jest.fn()}
        isVisible
        inspectSession={jest.fn()}
        updateVisibleSession={updateVisibleSession}
        setSelectedView={jest.fn()}
        playgroundPage
        setActiveSession={jest.fn()}
        deleteSession={jest.fn()}
      />
    </TooltipProvider>,
  );
  return { updateVisibleSession };
}

async function rename(newName: string) {
  const user = userEvent.setup();
  await user.click(screen.getByRole("combobox", { name: "Options" }));
  await user.click(screen.getByRole("option", { name: /rename/i }));
  const input = screen.getByRole("textbox");
  const seeded = (input as HTMLInputElement).value;
  await user.clear(input);
  await user.type(input, `${newName}{Enter}`);
  return seeded;
}

// Runs the mutation's onSuccess, as a successful rename would.
function completeRename() {
  const [, options] = mockUpdateSessionName.mock.calls[0];
  options.onSuccess();
}

describe("SessionSelector session label", () => {
  beforeAll(() => {
    Element.prototype.hasPointerCapture ??= jest.fn(() => false);
    Element.prototype.releasePointerCapture ??= jest.fn();
    Element.prototype.scrollIntoView ??= jest.fn();
  });

  afterEach(() => mockUpdateSessionName.mockClear());

  it("shows a namespaced session by its name", () => {
    renderSelector("flow-1:Session Oct 09, 14:29:10");
    expect(screen.getByTestId("session-selector")).toHaveTextContent(
      /^Session Oct 09, 14:29:10$/,
    );
  });

  it("shows the default session by its translated name", () => {
    renderSelector("flow-1");
    expect(screen.getByTestId("session-selector")).toHaveTextContent(
      "Default Session",
    );
  });

  it("renames a namespaced session by name and keeps it in the namespace", async () => {
    const { updateVisibleSession } = renderSelector(
      "flow-1:Session Oct 09, 14:29:10",
    );

    expect(await rename("Custom Name")).toBe("Session Oct 09, 14:29:10");
    expect(mockUpdateSessionName).toHaveBeenCalledWith(
      {
        old_session_id: "flow-1:Session Oct 09, 14:29:10",
        new_session_id: "flow-1:Custom Name",
      },
      expect.anything(),
    );
    completeRename();
    expect(updateVisibleSession).toHaveBeenCalledWith("flow-1:Custom Name");
  });

  it("renames an unscoped session to exactly what was typed", async () => {
    const { updateVisibleSession } = renderSelector("session-1");

    expect(await rename("Custom Name")).toBe("session-1");
    expect(mockUpdateSessionName).toHaveBeenCalledWith(
      { old_session_id: "session-1", new_session_id: "Custom Name" },
      expect.anything(),
    );
    completeRename();
    expect(updateVisibleSession).toHaveBeenCalledWith("Custom Name");
  });
});
