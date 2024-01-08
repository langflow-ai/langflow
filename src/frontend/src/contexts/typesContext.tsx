import _ from "lodash";
import { createContext, ReactNode, useState } from "react";
import { getAll, getHealth } from "../controllers/API";
import useAlertStore from "../stores/alertStore";
import { APIKindType } from "../types/api";
import { typesContextType } from "../types/typesContext";

//context to share types adn functions from nodes to flow

const initialValue: typesContextType = {
  types: {},
  setTypes: () => {},
  templates: {},
  setTemplates: () => {},
  data: {},
  setData: () => {},
  getTypes: () => {},
  setFetchError: () => {},
  fetchError: false,
  setFilterEdge: (filter) => {},
  getFilterEdge: [],
};

export const typesContext = createContext<typesContextType>(initialValue);

export function TypesProvider({ children }: { children: ReactNode }) {
  const [types, setTypes] = useState({});
  const [templates, setTemplates] = useState({});
  const [data, setData] = useState({});
  const [fetchError, setFetchError] = useState(false);
  const setLoading = useAlertStore((state) => state.setLoading);
  const [getFilterEdge, setFilterEdge] = useState([]);

  async function getTypes(): Promise<void> {
    // We will keep a flag to handle the case where the component is unmounted before the API call resolves.
    let isMounted = true;
    try {
      const result = await getAll();
      // Make sure to only update the state if the component is still mounted.
      if (isMounted && result?.status === 200) {
        setLoading(false);
        let { data } = _.cloneDeep(result);
        setData((old) => ({ ...old, ...data }));
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

  return (
    <typesContext.Provider
      value={{
        types,
        setTypes,
        setTemplates,
        templates,
        data,
        setData,
        getTypes,
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
