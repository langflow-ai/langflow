import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { Edge, Node, ReactFlowInstance } from "reactflow";
import { getAll, getHealth } from "../controllers/API";
import { APIKindType } from "../types/api";
import { typesContextType } from "../types/typesContext";
import { alertContext } from "./alertContext";
import { AuthContext } from "./authContext";

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
  setFilterEdge: (filter) => {},
  getFilterEdge: [],
  deleteEdge: () => {},
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
  const { getAuthentication } = useContext(AuthContext);
  const [getFilterEdge, setFilterEdge] = useState([]);

  useEffect(() => {
    // If the user is authenticated, fetch the types. This code is important to check if the user is auth because of the execution order of the useEffect hooks.
    if (getAuthentication() === true) {
      getTypes();
    }
  }, [getAuthentication()]);

  async function getTypes(): Promise<void> {
    // We will keep a flag to handle the case where the component is unmounted before the API call resolves.
    let isMounted = true;
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
              Object.keys(result.data[curr]).forEach((c: keyof APIKindType) => {
                acc[c] = curr;
                // Add the base classes to the accumulator as well.
                result.data[curr][c].base_classes?.forEach((b) => {
                  acc[b] = curr;
                });
              });
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

  function deleteNode(idx: string | Array<string>) {
    reactFlowInstance!.setNodes(
      reactFlowInstance!
        .getNodes()
        .filter((node: Node) =>
          typeof idx === "string" ? node.id !== idx : !idx.includes(node.id)
        )
    );
    reactFlowInstance!.setEdges(
      reactFlowInstance!
        .getEdges()
        .filter((edge) =>
          typeof idx === "string"
            ? edge.source !== idx && edge.target !== idx
            : !idx.includes(edge.source) && !idx.includes(edge.target)
        )
    );
  }
  function deleteEdge(idx: string | Array<string>) {
    reactFlowInstance!.setEdges(
      reactFlowInstance!
        .getEdges()
        .filter((edge: Edge) =>
          typeof idx === "string" ? edge.id !== idx : !idx.includes(edge.id)
        )
    );
  }

  return (
    <typesContext.Provider
      value={{
        deleteEdge,
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
        setFilterEdge,
        getFilterEdge,
      }}
    >
      {children}
    </typesContext.Provider>
  );
}
