import _ from "lodash";
import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { Edge, Node, ReactFlowInstance } from "reactflow";
import { getAll, getHealth, saveFlowToDatabase } from "../controllers/API";
import { APIClassType, APIKindType } from "../types/api";
import { NodeDataType } from "../types/flow";
import { typesContextType } from "../types/typesContext";
import { createFlowComponent } from "../utils/reactflowUtils";
import {
  getSetFromObject,
  IncrementObjectKey,
  removeCountFromString,
} from "../utils/utils";
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
  saveComponent: (component: NodeDataType, key: string) => {},
  deleteComponent: (id: string, key: string) => {},
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
  const { getAuthentication, autoLogin, userData } = useContext(AuthContext);
  const [getFilterEdge, setFilterEdge] = useState([]);

  useEffect(() => {
    // If the user is authenticated, fetch the types. This code is important to check if the user is auth because of the execution order of the useEffect hooks.
    if (getAuthentication() === true) {
      getTypes();
    }
  }, [getAuthentication(), autoLogin, userData]);

  async function getTypes(): Promise<void> {
    // We will keep a flag to handle the case where the component is unmounted before the API call resolves.
    let isMounted = true;
    try {
      const result = await getAll();
      // Make sure to only update the state if the component is still mounted.
      if (isMounted && result?.status === 200) {
        setLoading(false);
        let { data } = _.cloneDeep(result);
        setData(data);
        setTemplates(
          Object.keys(data).reduce((acc, curr) => {
            Object.keys(data[curr]).forEach((c: keyof APIKindType) => {
              //prevent wrong overwriting of the component template by a group of the same type
              if (!data[curr][c].flow) acc[c] = data[curr][c];
            });
            return acc;
          }, {})
        );
        // Set the types by reducing over the keys of the result data and updating the accumulator.
        setTypes(
          // Reverse the keys so the tool world does not overlap
          Object.keys(data)
            .reverse()
            .reduce((acc, curr) => {
              Object.keys(data[curr]).forEach((c: keyof APIKindType) => {
                acc[c] = curr;
                // Add the base classes to the accumulator as well.
                data[curr][c].base_classes?.forEach((b) => {
                  acc[b] = curr;
                });
              });
              return acc;
            }, {})
        );
      }
    } catch (error) {
      console.error("An error has occurred while fetching types.");
      console.log(error);
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

  function saveComponent(component: NodeDataType, id: string) {
    let key = component.type;
    if (data["custom_components"][key] !== undefined) {
      let { newKey, increment } = IncrementObjectKey(
        data["custom_components"],
        key
      );
      key = newKey;
      component.type = newKey;
      let componentNodes: { [key: string]: APIClassType } = {};
      Object.keys(data["custom_components"]).forEach((key) => {
        componentNodes[key] = data["custom_components"][key];
      });
      const display_nameSet = getSetFromObject(componentNodes, "display_name");
      if (display_nameSet.has(component.node?.display_name!)) {
        increment = 1;
        while (
          display_nameSet.has(
            removeCountFromString(component.node?.display_name!) +
              ` (${increment})`
          )
        ) {
          increment++;
        }
        component.node!.display_name =
          removeCountFromString(component.node?.display_name!) +
          ` (${increment})`;
      }
    }
    component.node!.official = false;
    saveFlowToDatabase(createFlowComponent(component));
    setData((prev) => {
      let newData = { ...prev };
      //clone to prevent reference erro
      newData["custom_components"][key] = _.cloneDeep({
        ...component.node,
        official: false,
      });
      return newData;
    });
  }

  function deleteComponent(id: string, key: string) {
    setData((prev) => {
      let newData = _.cloneDeep(prev);
      delete newData["custom_components"][key];
      return newData;
    });
  }

  return (
    <typesContext.Provider
      value={{
        deleteEdge,
        deleteComponent,
        saveComponent,
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
