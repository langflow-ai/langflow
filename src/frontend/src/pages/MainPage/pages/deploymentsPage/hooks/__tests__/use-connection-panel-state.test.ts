import { act, renderHook } from "@testing-library/react";
import type { ConnectionItem } from "../../types";
import { useConnectionPanelState } from "../use-connection-panel-state";

const baseParams = () => ({
  connections: [] as ConnectionItem[],
  setConnections: jest.fn(),
  effectiveFlowId: "flow-1",
  attachedConnectionByFlow: new Map<string, string[]>(),
  onAttachConnection: jest.fn(),
  commitPendingAttachment: jest.fn(),
  resetPendingAttachment: jest.fn(),
  setRightPanel: jest.fn(),
});

const makeConnection = (
  overrides: Partial<ConnectionItem> = {},
): ConnectionItem => ({
  id: "conn-1",
  connectionId: "conn-1",
  name: "My Connection",
  variableCount: 0,
  isNew: false,
  environmentVariables: {},
  ...overrides,
});

describe("useConnectionPanelState", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // handleAttachConnection
  // -------------------------------------------------------------------------
  describe("handleAttachConnection", () => {
    it("commits, updates map, switches panel, and clears selection when tab is 'available' with selections", () => {
      const params = baseParams();
      params.connections = [makeConnection({ id: "conn-1" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      // Select a connection
      act(() => {
        result.current.setSelectedConnections(new Set(["conn-1"]));
      });

      // Tab is 'available' by default
      act(() => {
        result.current.handleAttachConnection();
      });

      expect(params.commitPendingAttachment).toHaveBeenCalledTimes(1);
      expect(params.onAttachConnection).toHaveBeenCalledTimes(1);
      expect(params.setRightPanel).toHaveBeenCalledWith("versions");
      expect(result.current.selectedConnections.size).toBe(0);
    });

    it("passes the correct updater to onAttachConnection that maps flowId to selected connections", () => {
      const params = baseParams();
      params.connections = [makeConnection({ id: "conn-1" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setSelectedConnections(new Set(["conn-1", "conn-2"]));
      });

      act(() => {
        result.current.handleAttachConnection();
      });

      // Extract the updater function passed to onAttachConnection
      const updater = params.onAttachConnection.mock.calls[0][0];
      const prevMap = new Map<string, string[]>();
      const nextMap = updater(prevMap);

      expect(nextMap.get("flow-1")).toEqual(
        expect.arrayContaining(["conn-1", "conn-2"]),
      );
      expect(nextMap.get("flow-1")).toHaveLength(2);
    });

    it("does nothing when effectiveFlowId is null", () => {
      const params = baseParams();
      params.effectiveFlowId = null;
      params.connections = [makeConnection({ id: "conn-1" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setSelectedConnections(new Set(["conn-1"]));
      });

      act(() => {
        result.current.handleAttachConnection();
      });

      expect(params.commitPendingAttachment).not.toHaveBeenCalled();
      expect(params.onAttachConnection).not.toHaveBeenCalled();
      expect(params.setRightPanel).not.toHaveBeenCalled();
    });

    it("does nothing when selectedConnections is empty", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      // Tab is 'available', but no selections
      act(() => {
        result.current.handleAttachConnection();
      });

      expect(params.commitPendingAttachment).not.toHaveBeenCalled();
      expect(params.onAttachConnection).not.toHaveBeenCalled();
      expect(params.setRightPanel).not.toHaveBeenCalled();
    });

    it("does nothing when connectionTab is 'create'", () => {
      const params = baseParams();
      params.connections = [makeConnection({ id: "conn-1" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setSelectedConnections(new Set(["conn-1"]));
        result.current.setConnectionTab("create");
      });

      act(() => {
        result.current.handleAttachConnection();
      });

      expect(params.commitPendingAttachment).not.toHaveBeenCalled();
      expect(params.onAttachConnection).not.toHaveBeenCalled();
      expect(params.setRightPanel).not.toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  // handleCreateConnection
  // -------------------------------------------------------------------------
  describe("handleCreateConnection", () => {
    it("creates a connection with sanitized ID and adds it to connections and selectedConnections", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("My New Connection");
      });

      act(() => {
        result.current.handleCreateConnection();
      });

      // setConnections is called with updater
      const updater = params.setConnections.mock.calls[0][0];
      const newList = updater([]);
      expect(newList).toHaveLength(1);
      expect(newList[0].id).toBe("my_new_connection");
      expect(newList[0].connectionId).toBe("my_new_connection");
      expect(newList[0].name).toBe("My New Connection");
      expect(newList[0].isNew).toBe(true);
    });

    it("filters env vars with empty keys", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("Test");
        result.current.handleEnvVarChange(
          result.current.envVars[0].id,
          "key",
          "API_KEY",
        );
        result.current.handleEnvVarChange(
          result.current.envVars[0].id,
          "value",
          "secret123",
        );
        result.current.handleAddEnvVar();
      });

      // Second env var has empty key — should be filtered out
      act(() => {
        result.current.handleCreateConnection();
      });

      const updater = params.setConnections.mock.calls[0][0];
      const newList = updater([]);
      expect(newList[0].variableCount).toBe(1);
      expect(newList[0].environmentVariables).toEqual({
        API_KEY: "secret123",
      });
    });

    it("builds globalVarKeys set from env vars with globalVar flag", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("Test");
        result.current.handleEnvVarSelectGlobalVar(
          result.current.envVars[0].id,
          "MY_GLOBAL",
        );
      });

      act(() => {
        result.current.handleCreateConnection();
      });

      const updater = params.setConnections.mock.calls[0][0];
      const newList = updater([]);
      expect(newList[0].globalVarKeys).toBeInstanceOf(Set);
      expect(newList[0].globalVarKeys!.has("MY_GLOBAL")).toBe(true);
    });

    it("adds the new connection ID to selectedConnections", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("New Conn");
      });

      act(() => {
        result.current.handleCreateConnection();
      });

      expect(result.current.selectedConnections.has("new_conn")).toBe(true);
    });

    it("preserves existing selectedConnections when adding new one", () => {
      const params = baseParams();
      params.connections = [makeConnection({ id: "existing-1" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setSelectedConnections(new Set(["existing-1"]));
      });

      act(() => {
        result.current.setNewConnectionName("Another");
      });

      act(() => {
        result.current.handleCreateConnection();
      });

      expect(result.current.selectedConnections.has("existing-1")).toBe(true);
      expect(result.current.selectedConnections.has("another")).toBe(true);
    });

    it("resets tab to 'available' after creation", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setConnectionTab("create");
        result.current.setNewConnectionName("X");
      });

      act(() => {
        result.current.handleCreateConnection();
      });

      expect(result.current.connectionTab).toBe("available");
    });

    it("resets newConnectionName to empty string after creation", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("Something");
      });

      act(() => {
        result.current.handleCreateConnection();
      });

      expect(result.current.newConnectionName).toBe("");
    });

    it("resets envVars to single empty row after creation", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.handleAddEnvVar();
        result.current.handleAddEnvVar();
        result.current.setNewConnectionName("X");
      });

      act(() => {
        result.current.handleCreateConnection();
      });

      expect(result.current.envVars).toHaveLength(1);
      expect(result.current.envVars[0].key).toBe("");
      expect(result.current.envVars[0].value).toBe("");
    });

    describe("ID sanitization", () => {
      it("converts to lowercase", () => {
        const params = baseParams();
        const { result } = renderHook(() => useConnectionPanelState(params));

        act(() => {
          result.current.setNewConnectionName("MyConn");
        });
        act(() => {
          result.current.handleCreateConnection();
        });

        const updater = params.setConnections.mock.calls[0][0];
        expect(updater([])[0].id).toBe("myconn");
      });

      it("replaces spaces with underscores", () => {
        const params = baseParams();
        const { result } = renderHook(() => useConnectionPanelState(params));

        act(() => {
          result.current.setNewConnectionName("my new conn");
        });
        act(() => {
          result.current.handleCreateConnection();
        });

        const updater = params.setConnections.mock.calls[0][0];
        expect(updater([])[0].id).toBe("my_new_conn");
      });

      it("replaces multiple consecutive spaces with a single underscore", () => {
        const params = baseParams();
        const { result } = renderHook(() => useConnectionPanelState(params));

        act(() => {
          result.current.setNewConnectionName("my   conn");
        });
        act(() => {
          result.current.handleCreateConnection();
        });

        const updater = params.setConnections.mock.calls[0][0];
        expect(updater([])[0].id).toBe("my_conn");
      });

      it("strips non-alphanumeric/underscore characters", () => {
        const params = baseParams();
        const { result } = renderHook(() => useConnectionPanelState(params));

        act(() => {
          result.current.setNewConnectionName("my-conn!@#$%");
        });
        act(() => {
          result.current.handleCreateConnection();
        });

        const updater = params.setConnections.mock.calls[0][0];
        expect(updater([])[0].id).toBe("myconn");
      });

      it("handles mixed special characters, spaces, and uppercase", () => {
        const params = baseParams();
        const { result } = renderHook(() => useConnectionPanelState(params));

        act(() => {
          result.current.setNewConnectionName("  My Cool Connection! (v2)  ");
        });
        act(() => {
          result.current.handleCreateConnection();
        });

        const updater = params.setConnections.mock.calls[0][0];
        // trim -> "My Cool Connection! (v2)"
        // lowercase -> "my cool connection! (v2)"
        // spaces->_ -> "my_cool_connection!_(v2)"
        // strip non-alnum/_ -> "my_cool_connection_v2"
        expect(updater([])[0].id).toBe("my_cool_connection_v2");
      });

      it("trims the name used in the ConnectionItem", () => {
        const params = baseParams();
        const { result } = renderHook(() => useConnectionPanelState(params));

        act(() => {
          result.current.setNewConnectionName("  Trimmed  ");
        });
        act(() => {
          result.current.handleCreateConnection();
        });

        const updater = params.setConnections.mock.calls[0][0];
        expect(updater([])[0].name).toBe("Trimmed");
      });

      it("handles tab and newline whitespace as spaces", () => {
        const params = baseParams();
        const { result } = renderHook(() => useConnectionPanelState(params));

        act(() => {
          result.current.setNewConnectionName("hello\tworld\nfoo");
        });
        act(() => {
          result.current.handleCreateConnection();
        });

        const updater = params.setConnections.mock.calls[0][0];
        // \s+ matches tabs and newlines, replaced with _
        expect(updater([])[0].id).toBe("hello_world_foo");
      });

      it("produces empty string when name is all special characters", () => {
        const params = baseParams();
        const { result } = renderHook(() => useConnectionPanelState(params));

        act(() => {
          result.current.setNewConnectionName("!@#$%^&*()");
        });
        act(() => {
          result.current.handleCreateConnection();
        });

        const updater = params.setConnections.mock.calls[0][0];
        expect(updater([])[0].id).toBe("");
      });
    });

    it("tracks globalVar keys in the created connection", () => {
      const setConnections = jest.fn();
      const params = { ...baseParams(), setConnections };
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.updateDetectedEnvVars(["API_KEY"]);
      });
      // Add a manual (non-global) row
      act(() => {
        result.current.handleAddEnvVar();
      });
      act(() => {
        const manualId = result.current.envVars[1].id;
        result.current.handleEnvVarChange(manualId, "key", "RAW_VAL");
      });
      act(() => {
        result.current.setNewConnectionName("test-conn");
      });
      act(() => {
        result.current.handleCreateConnection();
      });

      expect(setConnections).toHaveBeenCalled();
      const updater = setConnections.mock.calls[0][0];
      const newList = updater([]);
      expect(newList).toHaveLength(1);

      const conn = newList[0];
      expect(conn.environmentVariables.API_KEY).toBe("API_KEY");
      expect(conn.environmentVariables.RAW_VAL).toBe("");
      expect(conn.globalVarKeys?.has("API_KEY")).toBe(true);
      expect(conn.globalVarKeys?.has("RAW_VAL")).toBe(false);
    });
  });

  // -------------------------------------------------------------------------
  // handleSkipConnection
  // -------------------------------------------------------------------------
  describe("handleSkipConnection", () => {
    it("commits, deletes flow from attachedConnectionByFlow map, switches panel, and clears selection", () => {
      const params = baseParams();
      params.attachedConnectionByFlow.set("flow-1", ["conn-1"]);
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setSelectedConnections(new Set(["conn-1"]));
      });

      act(() => {
        result.current.handleSkipConnection();
      });

      expect(params.commitPendingAttachment).toHaveBeenCalledTimes(1);
      expect(params.onAttachConnection).toHaveBeenCalledTimes(1);
      expect(params.setRightPanel).toHaveBeenCalledWith("versions");
      expect(result.current.selectedConnections.size).toBe(0);
    });

    it("passes updater to onAttachConnection that deletes the effectiveFlowId from map", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.handleSkipConnection();
      });

      const updater = params.onAttachConnection.mock.calls[0][0];
      const prevMap = new Map([["flow-1", ["conn-1"]]]);
      const nextMap = updater(prevMap);

      expect(nextMap.has("flow-1")).toBe(false);
    });

    it("still commits and switches panel when effectiveFlowId is null (but does not call onAttachConnection)", () => {
      const params = baseParams();
      params.effectiveFlowId = null;
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.handleSkipConnection();
      });

      expect(params.commitPendingAttachment).toHaveBeenCalledTimes(1);
      expect(params.onAttachConnection).not.toHaveBeenCalled();
      expect(params.setRightPanel).toHaveBeenCalledWith("versions");
      expect(result.current.selectedConnections.size).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // handleChangeFlow
  // -------------------------------------------------------------------------
  describe("handleChangeFlow", () => {
    it("clears selectedConnections", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setSelectedConnections(new Set(["conn-1", "conn-2"]));
      });

      act(() => {
        result.current.handleChangeFlow();
      });

      expect(result.current.selectedConnections.size).toBe(0);
    });

    it("resets detectedVarCount to 0", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      // First set some detected vars
      act(() => {
        result.current.updateDetectedEnvVars(["VAR1", "VAR2"]);
      });
      expect(result.current.detectedVarCount).toBe(2);

      act(() => {
        result.current.handleChangeFlow();
      });

      expect(result.current.detectedVarCount).toBe(0);
    });

    it("resets envVars to a single empty row", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.handleAddEnvVar();
        result.current.handleAddEnvVar();
      });
      expect(result.current.envVars.length).toBeGreaterThan(1);

      act(() => {
        result.current.handleChangeFlow();
      });

      expect(result.current.envVars).toHaveLength(1);
      expect(result.current.envVars[0].key).toBe("");
      expect(result.current.envVars[0].value).toBe("");
    });
  });

  // -------------------------------------------------------------------------
  // handleAddEnvVar
  // -------------------------------------------------------------------------
  describe("handleAddEnvVar", () => {
    it("appends a new empty env var row", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const initialLength = result.current.envVars.length;

      act(() => {
        result.current.handleAddEnvVar();
      });

      expect(result.current.envVars).toHaveLength(initialLength + 1);
      const last = result.current.envVars[result.current.envVars.length - 1];
      expect(last.key).toBe("");
      expect(last.value).toBe("");
    });

    it("generates unique IDs for each new row", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.handleAddEnvVar();
        result.current.handleAddEnvVar();
        result.current.handleAddEnvVar();
      });

      const ids = result.current.envVars.map((v) => v.id);
      const uniqueIds = new Set(ids);
      expect(uniqueIds.size).toBe(ids.length);
    });

    it("does not modify existing env var rows", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const firstId = result.current.envVars[0].id;

      act(() => {
        result.current.handleEnvVarChange(firstId, "key", "EXISTING");
      });

      act(() => {
        result.current.handleAddEnvVar();
      });

      expect(result.current.envVars[0].key).toBe("EXISTING");
      expect(result.current.envVars[0].id).toBe(firstId);
    });
  });

  // -------------------------------------------------------------------------
  // handleEnvVarChange
  // -------------------------------------------------------------------------
  describe("handleEnvVarChange", () => {
    it("updates the key field of the specified env var", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;

      act(() => {
        result.current.handleEnvVarChange(id, "key", "API_KEY");
      });

      expect(result.current.envVars[0].key).toBe("API_KEY");
    });

    it("updates the value field of the specified env var", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;

      act(() => {
        result.current.handleEnvVarChange(id, "value", "my-secret");
      });

      expect(result.current.envVars[0].value).toBe("my-secret");
    });

    it("clears the globalVar flag when changing a field", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;

      // First set globalVar via select
      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "SOME_GLOBAL");
      });
      expect(result.current.envVars[0].globalVar).toBe(true);

      // Now change the key — should clear globalVar
      act(() => {
        result.current.handleEnvVarChange(id, "key", "MANUAL_KEY");
      });

      expect(result.current.envVars[0].globalVar).toBe(false);
    });

    it("does not affect other env var rows", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.handleAddEnvVar();
      });

      const firstId = result.current.envVars[0].id;
      const secondId = result.current.envVars[1].id;

      act(() => {
        result.current.handleEnvVarChange(firstId, "key", "FIRST_KEY");
      });

      expect(result.current.envVars[0].key).toBe("FIRST_KEY");
      expect(result.current.envVars[1].key).toBe("");
      expect(result.current.envVars[1].id).toBe(secondId);
    });

    it("does nothing for a non-existent ID", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const originalVars = [...result.current.envVars];

      act(() => {
        result.current.handleEnvVarChange("non-existent", "key", "NOPE");
      });

      expect(result.current.envVars[0].key).toBe(originalVars[0].key);
    });
  });

  // -------------------------------------------------------------------------
  // handleEnvVarSelectGlobalVar
  // -------------------------------------------------------------------------
  describe("handleEnvVarSelectGlobalVar", () => {
    it("sets value to the selected global var name and sets globalVar to true", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;

      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "MY_GLOBAL");
      });

      expect(result.current.envVars[0].value).toBe("MY_GLOBAL");
      expect(result.current.envVars[0].globalVar).toBe(true);
    });

    it("auto-fills key when key is empty", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;
      // Key starts empty
      expect(result.current.envVars[0].key).toBe("");

      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "AUTO_KEY");
      });

      expect(result.current.envVars[0].key).toBe("AUTO_KEY");
    });

    it("auto-fills key when key was previously auto-filled from globalVar (key === value and globalVar is true)", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;

      // First select a global var (key auto-fills to match value)
      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "FIRST_GLOBAL");
      });

      expect(result.current.envVars[0].key).toBe("FIRST_GLOBAL");
      expect(result.current.envVars[0].value).toBe("FIRST_GLOBAL");
      expect(result.current.envVars[0].globalVar).toBe(true);

      // Select a different global var — key should auto-update since key === value and globalVar is true
      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "SECOND_GLOBAL");
      });

      expect(result.current.envVars[0].key).toBe("SECOND_GLOBAL");
      expect(result.current.envVars[0].value).toBe("SECOND_GLOBAL");
    });

    it("does NOT auto-fill key when key was manually set and differs from value", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;

      // Manually set a custom key first
      act(() => {
        result.current.handleEnvVarChange(id, "key", "CUSTOM_KEY");
      });

      // Now select a global var
      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "MY_GLOBAL");
      });

      // Key should remain CUSTOM_KEY, not be overwritten
      expect(result.current.envVars[0].key).toBe("CUSTOM_KEY");
      expect(result.current.envVars[0].value).toBe("MY_GLOBAL");
      expect(result.current.envVars[0].globalVar).toBe(true);
    });

    it("clears globalVar when empty string is selected", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;

      // First select a global var
      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "MY_GLOBAL");
      });
      expect(result.current.envVars[0].globalVar).toBe(true);

      // Deselect (empty string)
      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "");
      });

      expect(result.current.envVars[0].globalVar).toBe(false);
      expect(result.current.envVars[0].value).toBe("");
    });

    it("does not auto-fill key when clearing selection (empty string) even if key is empty", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;

      // Key is empty, select empty string — key should remain empty
      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "");
      });

      expect(result.current.envVars[0].key).toBe("");
    });

    it("does not auto-fill key when key has whitespace only but is not truly empty (trimmed empty triggers auto-fill)", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      const id = result.current.envVars[0].id;

      // Set key to whitespace only
      act(() => {
        result.current.handleEnvVarChange(id, "key", "   ");
      });
      // globalVar was cleared by handleEnvVarChange

      act(() => {
        result.current.handleEnvVarSelectGlobalVar(id, "NEW_GLOBAL");
      });

      // The condition checks item.key.trim() === "" — whitespace-only key triggers auto-fill
      expect(result.current.envVars[0].key).toBe("NEW_GLOBAL");
    });
  });

  // -------------------------------------------------------------------------
  // initConnectionsForFlow
  // -------------------------------------------------------------------------
  describe("initConnectionsForFlow", () => {
    it("loads pre-existing selections from attachedConnectionByFlow", () => {
      const params = baseParams();
      params.attachedConnectionByFlow.set("flow-1", ["conn-a", "conn-b"]);
      params.connections = [
        makeConnection({ id: "conn-a" }),
        makeConnection({ id: "conn-b" }),
      ];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.initConnectionsForFlow("flow-1");
      });

      expect(result.current.selectedConnections).toEqual(
        new Set(["conn-a", "conn-b"]),
      );
    });

    it("sets selectedConnections to empty set when flow has no pre-existing attachments", () => {
      const params = baseParams();
      params.connections = [makeConnection({ id: "conn-1" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.initConnectionsForFlow("unknown-flow");
      });

      expect(result.current.selectedConnections.size).toBe(0);
    });

    it("switches to 'create' tab when connections array is empty", () => {
      const params = baseParams();
      params.connections = []; // empty
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.initConnectionsForFlow("flow-1");
      });

      expect(result.current.connectionTab).toBe("create");
    });

    it("stays on current tab when connections array is not empty", () => {
      const params = baseParams();
      params.connections = [makeConnection({ id: "conn-1" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      // Default tab is 'available'
      act(() => {
        result.current.initConnectionsForFlow("flow-1");
      });

      expect(result.current.connectionTab).toBe("available");
    });
  });

  // -------------------------------------------------------------------------
  // isDuplicateConnectionName
  // -------------------------------------------------------------------------
  describe("isDuplicateConnectionName", () => {
    it("returns true for case-insensitive match", () => {
      const params = baseParams();
      params.connections = [makeConnection({ name: "My Connection" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("my connection");
      });

      expect(result.current.isDuplicateConnectionName).toBe(true);
    });

    it("returns true for match with leading/trailing whitespace", () => {
      const params = baseParams();
      params.connections = [makeConnection({ name: "My Connection" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("  My Connection  ");
      });

      expect(result.current.isDuplicateConnectionName).toBe(true);
    });

    it("returns true when existing connection name has whitespace", () => {
      const params = baseParams();
      params.connections = [makeConnection({ name: "  Spaced Name  " })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("Spaced Name");
      });

      expect(result.current.isDuplicateConnectionName).toBe(true);
    });

    it("returns false for empty name", () => {
      const params = baseParams();
      params.connections = [makeConnection({ name: "existing" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      // newConnectionName is empty by default
      expect(result.current.isDuplicateConnectionName).toBe(false);
    });

    it("returns false for whitespace-only name", () => {
      const params = baseParams();
      params.connections = [makeConnection({ name: "existing" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("   ");
      });

      expect(result.current.isDuplicateConnectionName).toBe(false);
    });

    it("returns false when no connections exist", () => {
      const params = baseParams();
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("anything");
      });

      expect(result.current.isDuplicateConnectionName).toBe(false);
    });

    it("returns false for a unique name", () => {
      const params = baseParams();
      params.connections = [makeConnection({ name: "existing" })];
      const { result } = renderHook(() => useConnectionPanelState(params));

      act(() => {
        result.current.setNewConnectionName("different");
      });

      expect(result.current.isDuplicateConnectionName).toBe(false);
    });
  });

  // -------------------------------------------------------------------------
  // updateDetectedEnvVars
  // -------------------------------------------------------------------------
  describe("updateDetectedEnvVars", () => {
    it("populates env var rows using each name as both key and global var value", () => {
      const { result } = renderHook(() =>
        useConnectionPanelState(baseParams()),
      );

      act(() => {
        result.current.updateDetectedEnvVars(["OPENAI_API_KEY", "DB_PASS"]);
      });

      const vars = result.current.envVars;
      expect(vars).toHaveLength(2);

      expect(vars[0].key).toBe("OPENAI_API_KEY");
      expect(vars[0].value).toBe("OPENAI_API_KEY");
      expect(vars[0].globalVar).toBe(true);

      expect(vars[1].key).toBe("DB_PASS");
      expect(vars[1].value).toBe("DB_PASS");
      expect(vars[1].globalVar).toBe(true);
    });

    it("sets detectedVarCount to the number of detected variables", () => {
      const { result } = renderHook(() =>
        useConnectionPanelState(baseParams()),
      );

      act(() => {
        result.current.updateDetectedEnvVars(["A", "B", "C"]);
      });

      expect(result.current.detectedVarCount).toBe(3);
    });

    it("resets to a single empty row when given an empty array", () => {
      const { result } = renderHook(() =>
        useConnectionPanelState(baseParams()),
      );

      act(() => {
        result.current.updateDetectedEnvVars(["X"]);
      });
      expect(result.current.envVars).toHaveLength(1);
      expect(result.current.detectedVarCount).toBe(1);

      act(() => {
        result.current.updateDetectedEnvVars([]);
      });

      expect(result.current.envVars).toHaveLength(1);
      expect(result.current.envVars[0].key).toBe("");
      expect(result.current.envVars[0].value).toBe("");
      expect(result.current.detectedVarCount).toBe(0);
    });

    it("assigns unique ids to each generated env var row", () => {
      const { result } = renderHook(() =>
        useConnectionPanelState(baseParams()),
      );

      act(() => {
        result.current.updateDetectedEnvVars(["A", "B"]);
      });

      const ids = result.current.envVars.map((v) => v.id);
      expect(new Set(ids).size).toBe(2);
    });
  });
});
