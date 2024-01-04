import { cloneDeep } from "lodash";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  HistoryItem,
  UseUndoRedoOptions,
  undoRedoContextType,
} from "../types/typesContext";
import { isWrappedWithClass } from "../utils/utils";
import { FlowsContext } from "./flowsContext";

const initialValue = {
  undo: () => {},
  redo: () => {},
  takeSnapshot: () => {},
};

const defaultOptions: UseUndoRedoOptions = {
  maxHistorySize: 100,
  enableShortcuts: true,
};

export const undoRedoContext = createContext<undoRedoContextType>(initialValue);

export function UndoRedoProvider({ children }) {
  const { tabId, flows, setNodes, setEdges, nodes, edges } =
    useContext(FlowsContext);

  const [past, setPast] = useState<HistoryItem[][]>(flows.map(() => []));
  const [future, setFuture] = useState<HistoryItem[][]>(flows.map(() => []));
  const [tabIndex, setTabIndex] = useState(
    flows.findIndex((flow) => flow.id === tabId)
  );

  useEffect(() => {
    // whenever the flows variable changes, we need to add one array to the past and future states
    setPast((old) =>
      flows.map((flow, index) => (old[index] ? old[index] : []))
    );
    setFuture((old) =>
      flows.map((flow, index) => (old[index] ? old[index] : []))
    );
    setTabIndex(flows.findIndex((flow) => flow.id === tabId));
  }, [flows, tabId]);

  const takeSnapshot = useCallback(() => {
    // push the current graph to the past state
    let newPast = cloneDeep(past);
    let newState = {
      nodes: cloneDeep(nodes),
      edges: cloneDeep(edges),
    };
    if (
      past[tabIndex] &&
      JSON.stringify(past[tabIndex][past[tabIndex].length - 1]) !==
        JSON.stringify(newState)
    ) {
      newPast[tabIndex] = past[tabIndex].slice(
        past[tabIndex].length - defaultOptions.maxHistorySize + 1,
        past[tabIndex].length
      );
      newPast[tabIndex].push(newState);
    }
    setPast(newPast);

    // whenever we take a new snapshot, the redo operations need to be cleared to avoid state mismatches
    setFuture((old) => {
      let newFuture = cloneDeep(old);
      newFuture[tabIndex] = [];
      return newFuture;
    });
  }, [nodes, edges, past, future, flows, tabId, setPast, setFuture]);

  const undo = useCallback(() => {
    // get the last state that we want to go back to
    const pastState = past[tabIndex][past[tabIndex].length - 1];

    if (pastState) {
      // first we remove the state from the history
      setPast((old) => {
        let newPast = cloneDeep(old);
        newPast[tabIndex] = old[tabIndex].slice(0, old[tabIndex].length - 1);
        return newPast;
      });
      // we store the current graph for the redo operation
      setFuture((old) => {
        let newFuture = cloneDeep(old);
        newFuture[tabIndex] = old[tabIndex];
        newFuture[tabIndex].push({ nodes: nodes, edges: edges });
        return newFuture;
      });
      // now we can set the graph to the past state
      setNodes(pastState.nodes);
      setEdges(pastState.edges);
    }
  }, [
    setNodes,
    setEdges,
    nodes,
    edges,
    future,
    past,
    setFuture,
    setPast,
    tabIndex,
  ]);

  const redo = useCallback(() => {
    const futureState = future[tabIndex][future[tabIndex].length - 1];

    if (futureState) {
      setFuture((old) => {
        let newFuture = cloneDeep(old);
        newFuture[tabIndex] = old[tabIndex].slice(0, old[tabIndex].length - 1);
        return newFuture;
      });
      setPast((old) => {
        let newPast = cloneDeep(old);
        newPast[tabIndex] = old[tabIndex];
        newPast[tabIndex].push({ nodes: nodes, edges: edges });
        return newPast;
      });
      setNodes(futureState.nodes);
      setEdges(futureState.edges);
    }
  }, [
    future,
    past,
    setFuture,
    setPast,
    setNodes,
    setEdges,
    nodes,
    edges,
    future,
    tabIndex,
  ]);

  useEffect(() => {
    // this effect is used to attach the global event handlers
    if (!defaultOptions.enableShortcuts) {
      return;
    }

    const keyDownHandler = (event: KeyboardEvent) => {
      if (!isWrappedWithClass(event, "noundo")) {
        if (
          event.key === "z" &&
          (event.ctrlKey || event.metaKey) &&
          event.shiftKey
        ) {
          event.preventDefault();
          redo();
        } else if (event.key === "y" && (event.ctrlKey || event.metaKey)) {
          event.preventDefault(); // prevent the default action
          redo();
        } else if (event.key === "z" && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          undo();
        }
      }
    };

    document.addEventListener("keydown", keyDownHandler);

    return () => {
      document.removeEventListener("keydown", keyDownHandler);
    };
  }, [undo, redo]);
  return (
    <undoRedoContext.Provider
      value={{
        undo,
        redo,
        takeSnapshot,
      }}
    >
      {children}
    </undoRedoContext.Provider>
  );
}
