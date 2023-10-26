import { useContext, useEffect, useState } from "react";

import PaginatorComponent from "../../../../components/PaginatorComponent";
import { SkeletonCardComponent } from "../../../../components/skeletonCardComponent";
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
  const [totalRowsCount, setTotalRowsCount] = useState(0);
  const [size, setPageSize] = useState(10);
  const [index, setPageIndex] = useState(1);

  useEffect(() => {
    handleGetComponents();
  }, []);

  const handleGetComponents = () => {
    setLoading(true);
    getStoreComponents(index - 1, 10000)
      .then((res) => {
        setTotalRowsCount(res.length);
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  };

  function handleChangePagination(pageIndex: number, pageSize: number) {
    setLoading(true);
    getStoreComponents(pageIndex, pageSize)
      .then((res) => {
        setData(res);
        setPageIndex(pageIndex);
        setPageSize(pageSize);
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

  const renderPagination = data.length > 0 && !loading;

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

      {renderPagination && (
        <div className="relative mt-3">
          <PaginatorComponent
            storeComponent={true}
            pageIndex={index}
            pageSize={size}
            totalRowsCount={totalRowsCount}
            paginate={(pageSize, pageIndex) => {
              handleChangePagination(pageIndex, pageSize);
            }}
          ></PaginatorComponent>
        </div>
      )}
    </>
  );
}
