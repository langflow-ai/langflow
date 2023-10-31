import { cloneDeep } from "lodash";
import { Search } from "lucide-react";
import { useContext, useEffect, useRef, useState } from "react";
import PaginatorComponent from "../../components/PaginatorComponent";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import { SkeletonCardComponent } from "../../components/skeletonCardComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { alertContext } from "../../contexts/alertContext";
import { StoreContext } from "../../contexts/storeContext";
import { TabsContext } from "../../contexts/tabsContext";
import {
  getNumberOfComponents,
  getStoreComponents,
  getStoreSavedComponents,
  getStoreTags,
  searchComponent,
} from "../../controllers/API";
import StoreApiKeyModal from "../../modals/StoreApiKeyModal";
import { storeComponent } from "../../types/store";
import { cn } from "../../utils/utils";
import { MarketCardComponent } from "./components/market-card";
export default function StorePage(): JSX.Element {
  const { setTabId } = useContext(TabsContext);
  // set null id
  useEffect(() => {
    setTabId("");
  }, []);
  const [data, setData] = useState<storeComponent[]>([]);
  const [loading, setLoading] = useState(false);
  const [filteredCategories, setFilterCategories] = useState<any[]>([]);
  const [inputText, setInputText] = useState<string>("");
  const [searchData, setSearchData] = useState(data);
  const { setErrorData } = useContext(alertContext);
  const [totalRowsCount, setTotalRowsCount] = useState(0);
  const [size, setPageSize] = useState(10);
  const [index, setPageIndex] = useState(1);
  const [errorApiKey, setErrorApiKey] = useState(false);
  const { setSavedFlows, savedFlows } = useContext(StoreContext);
  const [tags, setTags] = useState<{ id: string; name: string }[]>([]);
  const tagListId = useRef<{ id: string; name: string }[]>([]);
  const [renderPagination, setRenderPagination] = useState(false);

  useEffect(() => {
    getStoreTags().then((res) => {
      tagListId.current = res;
      setTags(res);
    });
  }, []);

  async function getSavedComponents() {
    setLoading(true);
    const result = await getStoreSavedComponents();
    let savedIds = new Set<string>();
    result.forEach((flow) => {
      savedIds.add(flow.id);
    });
    setSavedFlows(savedIds);
  }

  useEffect(() => {
    getNumberOfComponents().then((res) => {
      setTotalRowsCount(Number(res["count"]));
    });
    getSavedComponents()
      .finally(() => handleGetComponents())
      .catch((err) => {
        setErrorApiKey(true);
        console.error(err);
      });
  }, []);

  const handleGetComponents = () => {
    setLoading(true);
    setRenderPagination(true);
    getStoreComponents(index - 1, size)
      .then((res) => {
        setSearchData(res);
        setData(res);
        setLoading(false);
        setErrorApiKey(true);
      })
      .catch((err) => {
        setSearchData([]);
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  };

  const handleSearch = (inputText: string) => {
    if (inputText === "") {
      handleGetComponents();
      return;
    }
    setLoading(true);
    searchComponent(inputText).then(
      (res) => {
        setSearchData(res);
        setData(res);
        setLoading(false);
        setRenderPagination(false);
      },
      (error) => {
        setLoading(false);
      }
    );
  };

  function handleChangePagination(pageIndex: number, pageSize: number) {
    setLoading(true);
    setRenderPagination(true);
    getStoreComponents(pageIndex, pageSize)
      .then((res) => {
        setData(res);
        setSearchData(res);
        setPageIndex(pageIndex);
        setPageSize(pageSize);
        setLoading(false);
      })
      .catch((err) => {
        setSearchData([]);
        setLoading(false);
        setErrorData({
          title: "Error to get components.",
          list: [err["response"]["data"]["detail"]],
        });
      });
  }

  function handleFilterByTags(filterArray) {
    if (filterArray.length === 0) {
      handleGetComponents();
      return;
    }
    setRenderPagination(false);
    searchComponent(null, 1, 10000, null, filterArray).then(
      (res) => {
        setSearchData(res);
        setData(res);
        setLoading(false);
      },
      (error) => {
        setLoading(false);
        setSearchData([]);
      }
    );
  }

  return (
    <>
      <Header />

      <div className="community-page-arrangement">
        <div className="community-page-nav-arrangement">
          <span className="community-page-nav-title">
            <IconComponent name="Users2" className="w-6" />
            Langflow Store
          </span>
          <div className="community-page-nav-button">
            <StoreApiKeyModal
              onCloseModal={() => {
                handleGetComponents();
              }}
            >
              <Button
                className={`${errorApiKey ? "animate-pulse border-error" : ""}`}
                variant="primary"
              >
                <IconComponent name="Key" className="main-page-nav-button" />
                API Key
              </Button>
            </StoreApiKeyModal>
          </div>
        </div>
        <span className="community-page-description-text">
          Search flows and components from the community.
        </span>
        <div className="flex w-full flex-col gap-4 p-4">
          <div className="flex items-center justify-center gap-4">
            <div className="relative h-12 w-[35%]">
              <Input
                placeholder="Search Flows and Components"
                className="absolute h-12 px-5"
                onChange={(e) => {
                  setInputText(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleSearch(inputText);
                  }
                }}
                value={inputText}
              />
              <Search className="absolute bottom-0 right-4 top-0 my-auto h-6 stroke-1 text-muted-foreground " />
            </div>
            <div className="flex items-center justify-center text-sm">
              <Button
                onClick={() => {
                  handleSearch(inputText);
                }}
              >
                Search
              </Button>
            </div>
            <div className="flex w-[13%] items-center justify-center gap-3 text-sm">
              <Select
                onValueChange={(value) => {
                  if (value === "Flow") {
                    setSearchData(data.filter((f) => f.is_component === false));
                    setRenderPagination(false);
                  } else if (value === "Component") {
                    setSearchData(data.filter((f) => f.is_component === true));
                    setRenderPagination(false);
                  } else {
                    setSearchData(data);
                    setRenderPagination(true);
                  }
                }}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Both" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Both</SelectItem>
                  <SelectItem value="Flow">Flows</SelectItem>
                  <SelectItem value="Component">Components</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex h-2 items-center justify-center gap-4">
            {!loading &&
              tags.map((i, idx) => (
                <Badge
                  onClick={() => {
                    const index = filteredCategories?.indexOf(i.id);
                    const copyFilterArray = cloneDeep(filteredCategories);
                    if (index === -1) {
                      copyFilterArray.push(i.id);
                    } else {
                      copyFilterArray.splice(index, 1);
                    }
                    setFilterCategories(copyFilterArray);
                    handleFilterByTags(copyFilterArray);
                  }}
                  variant="gray"
                  size="md"
                  className={cn(
                    "cursor-pointer border-none",
                    filteredCategories.some((category) => category === i.id)
                      ? "bg-beta-foreground text-background hover:bg-beta-foreground"
                      : ""
                  )}
                >
                  {i.name}
                </Badge>
              ))}
          </div>
          <div className="mt-6 grid w-full gap-4 md:grid-cols-2 lg:grid-cols-3">
            {loading ? (
              <>
                <SkeletonCardComponent />
                <SkeletonCardComponent />
                <SkeletonCardComponent />
              </>
            ) : (
              searchData
                .filter(
                  (f) =>
                    filteredCategories?.length === 0 ||
                    filteredCategories.some(
                      (category) => category === f.is_component
                    )
                )
                .map((item, idx) => (
                  <MarketCardComponent key={idx} data={item} />
                ))
            )}
          </div>
        </div>

        {!loading && renderPagination && (
          <div className="relative my-3">
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
      </div>
    </>
  );
}
