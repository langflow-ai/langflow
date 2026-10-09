import { fireEvent, render, screen } from "@testing-library/react";
import { SidebarOpenView } from "../sidebar-open-view";

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (
    selector: (state: { setNewChatOnPlayground: jest.Mock }) => unknown,
  ) => selector({ setNewChatOnPlayground: jest.fn() }),
}));
jest.mock("@/stores/voiceStore", () => ({
  useVoiceStore: (
    selector: (state: {
      setNewSessionCloseVoiceAssistant: jest.Mock;
    }) => unknown,
  ) => selector({ setNewSessionCloseVoiceAssistant: jest.fn() }),
}));
jest.mock("../IOFieldView/components/session-selector", () => ({
  __esModule: true,
  default: ({
    session,
    toggleVisibility,
  }: {
    session: string;
    toggleVisibility: () => void;
  }) => (
    <button type="button" onClick={toggleVisibility}>
      {session}
    </button>
  ),
}));

it("lets shared playground users load and select an older session", () => {
  const onLoadMoreSessions = jest.fn();
  const setvisibleSession = jest.fn();
  const props = {
    sessions: ["default", "recent"],
    setSelectedViewField: jest.fn(),
    setvisibleSession,
    handleDeleteSession: jest.fn(),
    visibleSession: "default",
    selectedViewField: undefined,
    playgroundPage: true,
    setActiveSession: jest.fn(),
    onLoadMoreSessions,
    hasMoreSessions: true,
  };
  const { rerender } = render(<SidebarOpenView {...props} />);
  expect(screen.queryByText("older")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("load-more-sessions"));
  expect(onLoadMoreSessions).toHaveBeenCalledTimes(1);
  rerender(
    <SidebarOpenView
      {...props}
      sessions={[...props.sessions, "older"]}
      hasMoreSessions={false}
    />,
  );
  fireEvent.click(screen.getByText("older"));
  expect(setvisibleSession).toHaveBeenCalledWith("older");
  expect(screen.queryByTestId("load-more-sessions")).not.toBeInTheDocument();
});
