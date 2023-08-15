import { createContext, ReactNode, useEffect, useState } from "react";
import { Node } from "reactflow";
import { getAll } from "../controllers/API";
import { APIKindType } from "../types/api";
import { typesContextType } from "../types/typesContext";

//context to share types adn functions from nodes to flow

const initialValue: typesContextType = {
  reactFlowInstance: null,
  setReactFlowInstance: () => {},
  deleteNode: () => {},
  types: {},
  setTypes: () => {},
  templates: {},
  setTemplates: () => {},
  data: {},
  setData: () => {},
};

export const typesContext = createContext<typesContextType>(initialValue);

export function TypesProvider({ children }: { children: ReactNode }) {
  const [types, setTypes] = useState({});
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const [templates, setTemplates] = useState({});
  const [data, setData] = useState({});

  useEffect(() => {
    let delay = 1000; // Start delay of 1 second
    let intervalId = null;
    let retryCount = 0; // Count of retry attempts
    const maxRetryCount = 5; // Max retry attempts

    // We will keep a flag to handle the case where the component is unmounted before the API call resolves.
    let isMounted = true;

    async function getTypes(): Promise<void> {
      try {
        const result = await getAll();
        // Make sure to only update the state if the component is still mounted.
        if (isMounted) {
          setData(result.data);
          setTemplates(
            Object.keys(result.data).reduce((acc, curr) => {
              Object.keys(result.data[curr]).forEach((c: keyof APIKindType) => {
                acc[c] = result.data[curr][c];
              });
              return acc;
            }, {})
          );
          // Set the types by reducing over the keys of the result data and updating the accumulator.
          setTypes(
            // Reverse the keys so the tool world does not overlap
            Object.keys(result.data)
              .reverse()
              .reduce((acc, curr) => {
                Object.keys(result.data[curr]).forEach(
                  (c: keyof APIKindType) => {
                    acc[c] = curr;
                    // Add the base classes to the accumulator as well.
                    result.data[curr][c].base_classes?.forEach((b) => {
                      acc[b] = curr;
                    });
                  }
                );
                return acc;
              }, {})
          );
        }
        // Clear the interval if successful.
        clearInterval(intervalId);
      } catch (error) {
        console.error("An error has occurred while fetching types.");
      }
    }

    // Start the initial interval.
    intervalId = setInterval(getTypes, delay);

    return () => {
      // This will clear the interval when the component unmounts, or when the dependencies of the useEffect hook change.
      clearInterval(intervalId);
      // Indicate that the component has been unmounted.
      isMounted = false;
    };
  }, []);

  function deleteNode(idx: string) {
    reactFlowInstance.setNodes(
      reactFlowInstance.getNodes().filter((node: Node) => node.id !== idx)
    );
    reactFlowInstance.setEdges(
      reactFlowInstance
        .getEdges()
        .filter((edge) => edge.source !== idx && edge.target !== idx)
    );
  }
  return (
    <typesContext.Provider
      value={{
        types,
        setTypes,
        reactFlowInstance,
        setReactFlowInstance,
        deleteNode,
        setTemplates,
        templates,
        data,
        setData,
      }}
    >
      {children}
    </typesContext.Provider>
  );
}
