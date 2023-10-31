import { useContext, useEffect, useState } from "react";

import { SkeletonCardComponent } from "../../../../components/skeletonCardComponent";
import { alertContext } from "../../../../contexts/alertContext";
import { AuthContext } from "../../../../contexts/authContext";
import { TabsContext } from "../../../../contexts/tabsContext";
import {
  getStoreComponents,
  getStoreSavedComponents,
} from "../../../../controllers/API";
import { storeComponent } from "../../../../types/store";
import { MarketCardComponent } from "../../../StorePage/components/market-card";

export default function SavedComponents(): JSX.Element {
  const { setTabId } = useContext(TabsContext);

  const { setApiKey, apiKey } = useContext(AuthContext);

  // set null id
  useEffect(() => {
    setTabId("");
  }, []);
  const [data, setData] = useState<storeComponent[]>([]);
  const [loading, setLoading] = useState(false);
  const [filteredCategories, setFilteredCategories] = useState(new Set());
  const { setErrorData } = useContext(alertContext);

  useEffect(() => {
    handleGetComponents();
  }, []);

  const handleGetComponents = () => {
    setLoading(true);
    getStoreComponents(0, 10000)
      .then((res) => {
        handleAddedOnly(res);
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  };

  function handleAddedOnly(components: storeComponent[]) {
    getStoreSavedComponents()
      .then((res) => {
        const idSet = new Set(res.map((item) => item.id));
        const filteredArray = components.filter((item) => idSet.has(item.id));
        setData(filteredArray);
        setLoading(false);
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  }

  return (
    <>
      {loading ? (
        <>
          <div className="mt-6 grid w-full gap-4 md:grid-cols-2 lg:grid-cols-3">
            <SkeletonCardComponent />
            <SkeletonCardComponent />
            <SkeletonCardComponent />
          </div>
        </>
      ) : (
        <div className="flex w-full flex-col gap-4 p-4">
          <div className="mt-6 grid w-full gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data
              .filter(
                (f) =>
                  Array.from(filteredCategories).length === 0 ||
                  filteredCategories.has(f.is_component)
              )
              .map((item, idx) => (
                <MarketCardComponent key={idx} data={item} />
              ))}
          </div>
        </div>
      )}
    </>
  );
}
