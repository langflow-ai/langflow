import { useCallback, useContext, useEffect, useState } from "react";
import { Edge, Node, useReactFlow } from "reactflow";
import { TabsContext } from "../../../contexts/tabsContext";
import { cloneDeep } from "lodash";

type UseUndoRedoOptions = {
  maxHistorySize: number;
  enableShortcuts: boolean;
};

type UseUndoRedo = (options?: UseUndoRedoOptions) => {
  undo: () => void;
  redo: () => void;
  takeSnapshot: () => void;
  canUndo: boolean;
  canRedo: boolean;
};

type HistoryItem = {
  nodes: Node[];
  edges: Edge[];
};

const defaultOptions: UseUndoRedoOptions = {
  maxHistorySize: 100,
  enableShortcuts: true,
};

// https://redux.js.org/usage/implementing-undo-history
export const useUndoRedo: UseUndoRedo = ({
  maxHistorySize = defaultOptions.maxHistorySize,
  enableShortcuts = defaultOptions.enableShortcuts,
} = defaultOptions) => {
  // the past and future arrays store the states that we can jump to
  const { tabIndex, flows } = useContext(TabsContext);

  const [past, setPast] = useState<HistoryItem[][]>(flows.map(() => []));
  const [future, setFuture] = useState<HistoryItem[][]>(flows.map(() => []));

  useEffect(() => {
    // whenever the flows variable changes, we need to add one array to the past and future states
    setPast((old) => flows.map((f, i) => (old[i] ? old[i] : [])));
    setFuture((old) => flows.map((f, i) => (old[i] ? old[i] : [])));
  }, [flows]);

  const { setNodes, setEdges, getNodes, getEdges } = useReactFlow();

  const takeSnapshot = useCallback(() => {
    // push the current graph to the past state
    setPast((old) => {
      let newPast = cloneDeep(old);
      newPast[tabIndex] = old[tabIndex].slice(
        old[tabIndex].length - maxHistorySize + 1,
        old[tabIndex].length
      );
      newPast[tabIndex].push({ nodes: getNodes(), edges: getEdges() });
      return newPast;
    });

    // whenever we take a new snapshot, the redo operations need to be cleared to avoid state mismatches
    setFuture((old) => {
      let newFuture = cloneDeep(old);
      newFuture[tabIndex] = [];
      return newFuture;
    });
  }, [
    getNodes,
    getEdges,
    past,
    future,
    tabIndex,
    setPast,
    setFuture,
    maxHistorySize,
  ]);

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
        newFuture[tabIndex].push({ nodes: getNodes(), edges: getEdges() });
        return newFuture;
      });
      // now we can set the graph to the past state
      setNodes(pastState.nodes);
      setEdges(pastState.edges);
    }
  }, [
    setNodes,
    setEdges,
    getNodes,
    getEdges,
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
        newPast[tabIndex].push({ nodes: getNodes(), edges: getEdges() });
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
    getNodes,
    getEdges,
    future,
    tabIndex,
  ]);

  useEffect(() => {
    // this effect is used to attach the global event handlers
    if (!enableShortcuts) {
      return;
    }

    const keyDownHandler = (event: KeyboardEvent) => {
      if (
        event.key === "z" &&
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey
      ) {
        redo();
      } else if (event.key === "y" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault(); // prevent the default action
        redo();
      } else if (event.key === "z" && (event.ctrlKey || event.metaKey)) {
        undo();
      }
    };

    document.addEventListener("keydown", keyDownHandler);

    return () => {
      document.removeEventListener("keydown", keyDownHandler);
    };
  }, [undo, redo, enableShortcuts]);

  return {
    undo,
    redo,
    takeSnapshot,
    canUndo: !!past.length,
    canRedo: !!future.length,
  };
};

export default useUndoRedo;
