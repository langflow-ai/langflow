import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { Node, ReactFlowInstance } from "reactflow";
import { getAll, getHealth } from "../controllers/API";
import { APIKindType } from "../types/api";
import { typesContextType } from "../types/typesContext";
import { alertContext } from "./alertContext";

//context to share types adn functions from nodes to flow

const initialValue: typesContextType = {
  reactFlowInstance: null,
  setReactFlowInstance: (newState: ReactFlowInstance) => {},
  deleteNode: () => {},
  types: {},
  setTypes: () => {},
  templates: {},
  setTemplates: () => {},
  data: {},
  setData: () => {},
  setFetchError: () => {},
  fetchError: false,
};

export const typesContext = createContext<typesContextType>(initialValue);

export function TypesProvider({ children }: { children: ReactNode }) {
  const [types, setTypes] = useState({});
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance | null>(null);
  const [templates, setTemplates] = useState({});
  const [data, setData] = useState({});
  const [fetchError, setFetchError] = useState(false);
  const { setLoading } = useContext(alertContext);

  useEffect(() => {

    setTimeout(() => {
      
    // We will keep a flag to handle the case where the component is unmounted before the API call resolves.
    let isMounted = true;

    async function getTypes(): Promise<void> {
      try {
        const result = await getAll();
        // Make sure to only update the state if the component is still mounted.
        if (isMounted && result?.status === 200) {
          setLoading(false);
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
      } catch (error) {
        console.error("An error has occurred while fetching types.");
        await getHealth().catch((e) => {
          setFetchError(true);
        });
      }
    }

    getTypes();
    }, 2000);

  }, []);

  function deleteNode(idx: string) {
    reactFlowInstance!.setNodes(
      reactFlowInstance!.getNodes().filter((node: Node) => node.id !== idx)
    );
    reactFlowInstance!.setEdges(
      reactFlowInstance!
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
        fetchError,
        setFetchError,
      }}
    >
      {children}
    </typesContext.Provider>
  );
}
