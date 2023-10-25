import { useContext, useEffect, useState } from "react";

import { alertContext } from "../../../../contexts/alertContext";
import { AuthContext } from "../../../../contexts/authContext";
import { TabsContext } from "../../../../contexts/tabsContext";
import { getStoreComponents } from "../../../../controllers/API";
import { FlowComponent } from "../../../../types/store";
import { MarketCardComponent } from "../../../StorePage/components/market-card";

export default function SavedComponents(): JSX.Element {
  const { setTabId } = useContext(TabsContext);

  const { setApiKey, apiKey } = useContext(AuthContext);

  // set null id
  useEffect(() => {
    setTabId("");
  }, []);
  const [data, setData] = useState<FlowComponent[]>([]);
  const [loading, setLoading] = useState(false);
  const [filteredCategories, setFilteredCategories] = useState(new Set());
  const { setErrorData } = useContext(alertContext);

  useEffect(() => {
    handleGetComponents();
  }, []);

  const handleGetComponents = () => {
    setLoading(true);
    getStoreComponents(1, 10)
      .then((res) => {
        setLoading(false);
        setData(res);
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  };

  const loadingWithApiKey = loading;
  const renderComponents = !loading;

  return (
    <>
      {renderComponents && (
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

      {loadingWithApiKey && (
        <div className="flex w-full flex-col gap-4 p-4">Loading...</div>
      )}
    </>
  );
}
