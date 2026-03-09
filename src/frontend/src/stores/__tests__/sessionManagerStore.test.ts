import { act } from "@testing-library/react";
import { useSessionManagerStore } from "../sessionManagerStore";

const FLOW_ID = "flow-1";
const STORAGE_KEY = `langflow_local_sessions_${FLOW_ID}`;

describe("useSessionManagerStore", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    act(() => {
      useSessionManagerStore.getState().reset();
    });
  });

  it("initializes from sessionStorage", () => {
    window.sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(["local-1", "local-2"]),
    );

    act(() => {
      useSessionManagerStore.getState().initialize(FLOW_ID);
    });

    expect(useSessionManagerStore.getState()).toMatchObject({
      flowId: FLOW_ID,
      activeSessionId: FLOW_ID,
      sessions: [
        { id: "local-1", isLocal: true },
        { id: "local-2", isLocal: true },
      ],
    });
  });

  it("adds sessions and persists only local ids", () => {
    act(() => {
      useSessionManagerStore.getState().initialize(FLOW_ID);
      useSessionManagerStore.getState().addSession({
        id: "local-1",
        isLocal: true,
      });
      useSessionManagerStore.getState().addSession({
        id: "server-1",
        isLocal: false,
      });
    });

    expect(useSessionManagerStore.getState().sessions).toEqual([
      { id: "local-1", isLocal: true },
      { id: "server-1", isLocal: false },
    ]);
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBe(
      JSON.stringify(["local-1"]),
    );
  });

  it("removes a session, resets the active session, and updates persisted locals", () => {
    act(() => {
      useSessionManagerStore.getState().initialize(FLOW_ID);
      useSessionManagerStore.getState().addSession({
        id: "local-1",
        isLocal: true,
      });
      useSessionManagerStore.getState().addSession({
        id: "local-2",
        isLocal: true,
      });
      useSessionManagerStore.getState().setActiveSessionId("local-1");
      useSessionManagerStore.getState().removeSession("local-1");
    });

    expect(useSessionManagerStore.getState()).toMatchObject({
      activeSessionId: FLOW_ID,
      sessions: [{ id: "local-2", isLocal: true }],
    });
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBe(
      JSON.stringify(["local-2"]),
    );
  });

  it("renames a session and keeps the active selection in sync", () => {
    act(() => {
      useSessionManagerStore.getState().initialize(FLOW_ID);
      useSessionManagerStore.getState().addSession({
        id: "draft-session",
        isLocal: true,
      });
      useSessionManagerStore.getState().setActiveSessionId("draft-session");
      useSessionManagerStore
        .getState()
        .renameSession("draft-session", "final-session");
    });

    expect(useSessionManagerStore.getState()).toMatchObject({
      activeSessionId: "final-session",
      sessions: [{ id: "final-session", isLocal: true }],
    });
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBe(
      JSON.stringify(["final-session"]),
    );
  });

  it("syncs server sessions by promoting locals, cleaning up removed server sessions, and appending new ones", () => {
    act(() => {
      useSessionManagerStore.getState().initialize(FLOW_ID);
      useSessionManagerStore.getState().addSession({
        id: "promoted-session",
        isLocal: true,
      });
      useSessionManagerStore.getState().addSession({
        id: "local-only-session",
        isLocal: true,
      });
      useSessionManagerStore.getState().addSession({
        id: "removed-on-server",
        isLocal: false,
      });
      useSessionManagerStore
        .getState()
        .syncFromServer(["promoted-session", "new-server-session", FLOW_ID]);
    });

    expect(useSessionManagerStore.getState().sessions).toEqual([
      { id: "promoted-session", isLocal: false },
      { id: "local-only-session", isLocal: true },
      { id: "new-server-session", isLocal: false },
    ]);
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBe(
      JSON.stringify(["local-only-session"]),
    );
  });

  it("returns ordered session ids with the flow id first", () => {
    act(() => {
      useSessionManagerStore.getState().initialize(FLOW_ID);
      useSessionManagerStore.setState({
        sessions: [
          { id: FLOW_ID, isLocal: false },
          { id: "session-1", isLocal: false },
          { id: "session-2", isLocal: true },
        ],
      });
    });

    expect(useSessionManagerStore.getState().getOrderedSessionIds()).toEqual([
      FLOW_ID,
      "session-1",
      "session-2",
    ]);
  });
});
