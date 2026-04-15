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

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// updateDetectedEnvVars
// ---------------------------------------------------------------------------

describe("updateDetectedEnvVars", () => {
  it("populates env var rows using each name as both key and global var value", () => {
    const { result } = renderHook(() => useConnectionPanelState(baseParams()));

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
    const { result } = renderHook(() => useConnectionPanelState(baseParams()));

    act(() => {
      result.current.updateDetectedEnvVars(["A", "B", "C"]);
    });

    expect(result.current.detectedVarCount).toBe(3);
  });

  it("resets to a single empty row when given an empty array", () => {
    const { result } = renderHook(() => useConnectionPanelState(baseParams()));

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
    const { result } = renderHook(() => useConnectionPanelState(baseParams()));

    act(() => {
      result.current.updateDetectedEnvVars(["A", "B"]);
    });

    const ids = result.current.envVars.map((v) => v.id);
    expect(new Set(ids).size).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// handleEnvVarSelectGlobalVar
// ---------------------------------------------------------------------------

describe("handleEnvVarSelectGlobalVar", () => {
  it("sets value to selected global var and marks globalVar true", () => {
    const { result } = renderHook(() => useConnectionPanelState(baseParams()));

    const id = result.current.envVars[0].id;
    act(() => {
      result.current.handleEnvVarSelectGlobalVar(id, "MY_SECRET");
    });

    const updated = result.current.envVars[0];
    expect(updated.value).toBe("MY_SECRET");
    expect(updated.globalVar).toBe(true);
    expect(updated.key).toBe("MY_SECRET");
  });

  it("clears globalVar when deselecting (empty string)", () => {
    const { result } = renderHook(() => useConnectionPanelState(baseParams()));

    const id = result.current.envVars[0].id;
    act(() => {
      result.current.handleEnvVarSelectGlobalVar(id, "MY_SECRET");
    });
    expect(result.current.envVars[0].globalVar).toBe(true);

    act(() => {
      result.current.handleEnvVarSelectGlobalVar(id, "");
    });
    expect(result.current.envVars[0].globalVar).toBe(false);
    expect(result.current.envVars[0].value).toBe("");
  });
});

// ---------------------------------------------------------------------------
// handleEnvVarChange
// ---------------------------------------------------------------------------

describe("handleEnvVarChange", () => {
  it("clears globalVar flag when user manually types a value", () => {
    const { result } = renderHook(() => useConnectionPanelState(baseParams()));

    const id = result.current.envVars[0].id;
    act(() => {
      result.current.handleEnvVarSelectGlobalVar(id, "MY_SECRET");
    });
    expect(result.current.envVars[0].globalVar).toBe(true);

    act(() => {
      result.current.handleEnvVarChange(id, "value", "raw-text");
    });
    expect(result.current.envVars[0].globalVar).toBe(false);
    expect(result.current.envVars[0].value).toBe("raw-text");
  });
});

// ---------------------------------------------------------------------------
// handleCreateConnection — globalVarKeys
// ---------------------------------------------------------------------------

describe("handleCreateConnection", () => {
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
