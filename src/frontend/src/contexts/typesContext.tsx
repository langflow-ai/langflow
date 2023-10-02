import _ from "lodash";
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
import { localStorageUserType } from "../types/entities";
import { NodeDataType } from "../types/flow";
import { typesContextType } from "../types/typesContext";
import {
  checkLocalStorageKey,
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
        const savedComponents = autoLogin
          ? localStorage.getItem("auto")
          : localStorage.getItem(userData?.id!);
        if (savedComponents !== null) {
          const { components }: localStorageUserType = JSON.parse(
            savedComponents!
          );
          Object.keys(components).forEach((key) => {
            data["custom_components"][key] = components[key].node!;
          });
        }
        setData(data);
        setTemplates(
          Object.keys(data).reduce((acc, curr) => {
            Object.keys(data[curr]).forEach((c: keyof APIKindType) => {
              acc[c] = data[curr][c];
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

  function saveComponent(component: NodeDataType, id: string) {
    let savedComponentsJSON: localStorageUserType = { components: {} };
    if (checkLocalStorageKey(id)) {
      let savedComponents = localStorage.getItem(id)!;
      savedComponentsJSON = JSON.parse(savedComponents);
    }
    let components = savedComponentsJSON.components;
    let key = component.type;
    if (data["custom_components"][key] !== undefined) {
      const { newKey, increment } = IncrementObjectKey(
        data["custom_components"],
        key
      );
      key = newKey;
      console.log(component.node?.display_name);
      component.node!.display_name =
        removeCountFromString(component.node?.display_name!) +
        ` (${increment})`;
    }
    components[key] = component;
    savedComponentsJSON.components = components;
    localStorage.setItem(id, JSON.stringify(savedComponentsJSON));
    setData((prev) => {
      let newData = { ...prev };
      //clone to prevent reference erro
      newData["custom_components"][key] = _.cloneDeep(component.node);
      return newData;
    });
  }
  return (
    <typesContext.Provider
      value={{
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
