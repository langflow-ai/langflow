import { cloneDeep } from "lodash";
import { Search } from "lucide-react";
import { useContext, useEffect, useRef, useState } from "react";
import PaginatorComponent from "../../components/PaginatorComponent";
import ShadTooltip from "../../components/ShadTooltipComponent";
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
  useEffect(() => {
    setTabId("");
  }, []);
  const [loading, setLoading] = useState(false);
  const [filteredCategories, setFilterCategories] = useState<any[]>([]);
  const [inputText, setInputText] = useState<string>("");
  const [searchData, setSearchData] = useState<storeComponent[]>([]);
  const { setErrorData } = useContext(alertContext);
  const [totalRowsCount, setTotalRowsCount] = useState(0);
  const [size, setPageSize] = useState(10);
  const [index, setPageIndex] = useState(1);
  const [errorApiKey, setErrorApiKey] = useState(false);
  const { setSavedFlows, hasApiKey } = useContext(StoreContext);
  const [tags, setTags] = useState<{ id: string; name: string }[]>([]);
  const tagListId = useRef<{ id: string; name: string }[]>([]);
  const [renderPagination, setRenderPagination] = useState(false);
  const filterComponent = useRef<boolean | null>(null);
  const [tabActive, setTabActive] = useState("Flows");

  useEffect(() => {
    getStoreTags().then((res) => {
      tagListId.current = res;
      setTags(res);
    });
  }, []);

  useEffect(() => {
    filterComponent.current = false;
    getSavedComponents()
      .finally(() => handleGetComponents())
      .catch((err) => {
        setErrorApiKey(true);
        console.error(err);
      });
  }, []);

  async function getSavedComponents() {
    setLoading(true);
    const data = await getStoreSavedComponents();
    let savedIds = new Set<string>();
    let results = data?.results ?? [];
    results.forEach((flow) => {
      savedIds.add(flow.id);
    }); /*
    setSavedFlows(savedIds); */
    setErrorApiKey(false);
    setLoading(false);
  }

  const handleGetComponents = () => {
    setLoading(true);
    setRenderPagination(true);

    getStoreComponents(index - 1, size, filterComponent.current)
      .then((res) => {
        setLoading(false);
        setSearchData(res?.results ?? []);
        setTotalRowsCount(Number(res?.count ?? 0));
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
        setLoading(false);
        setRenderPagination(false);
        setTotalRowsCount(res.length);
      },
      (error) => {
        setLoading(false);
      }
    );
  };

  function handleChangePagination(pageIndex: number, pageSize: number) {
    setLoading(true);
    setRenderPagination(true);
    getStoreComponents(pageIndex, pageSize, filterComponent.current)
      .then((res) => {
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
        setLoading(false);
        setTotalRowsCount(res.length);
      },
      (error) => {
        setLoading(false);
        setSearchData([]);
      }
    );
  }

  function handleChangeTab(tab: string) {
    if (tab === "All") {
      filterComponent.current = null;
    } else if (tab === "Flows") {
      filterComponent.current = false;
    } else if (tab === "Components") {
      filterComponent.current = true;
    }
    setPageIndex(1);
    setPageSize(10);
    handleGetComponents();
  }

  const handleOrderPage = (e) => {
    let sortedData = cloneDeep(searchData);

    if (e === "Popular") {
      sortedData = sortedData.sort(
        (a, b) => Number(b.liked_by_count) - Number(a.liked_by_count)
      );
    } else if (e === "Alphabetical") {
      sortedData = sortedData.sort((a, b) => a.name.localeCompare(b.name));
    }

    setSearchData([...sortedData]);
  };

  return (
    <>
      <Header />

      <div className="community-page-arrangement">
        <div className="community-page-nav-arrangement">
          <span className="community-page-nav-title">
            <IconComponent name="Store" className="w-6" />
            Langflow Store
          </span>
          <div className="community-page-nav-button">
            <StoreApiKeyModal
              onCloseModal={() => {
                handleGetComponents();
              }}
            >
              <Button
                className={`${
                  errorApiKey && !hasApiKey ? "animate-pulse border-error" : ""
                }`}
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
        <div className="flex w-full flex-col gap-4 p-0">
          <div className="flex items-end gap-4">
            <div className="relative h-12 w-[40%]">
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
              <Search
                onClick={() => {
                  handleSearch(inputText);
                }}
                className="absolute bottom-0 right-4 top-0 my-auto h-6 cursor-pointer stroke-1 text-muted-foreground"
              />
            </div>
            <div className="ml-4 flex w-full gap-2 border-b border-border">
              <button
                onClick={() => {
                  setTabActive("All");
                  handleChangeTab("All");
                }}
                className={
                  tabActive === "All"
                    ? "border-b-2 border-primary p-3"
                    : " border-b-2 border-transparent p-3 text-muted-foreground hover:text-primary"
                }
              >
                All
              </button>
              <button
                onClick={() => {
                  setTabActive("Flows");
                  handleChangeTab("Flows");
                }}
                className={
                  tabActive === "Flows"
                    ? "border-b-2 border-primary p-3"
                    : " border-b-2 border-transparent p-3 text-muted-foreground hover:text-primary"
                }
              >
                Flows
              </button>
              <button
                onClick={() => {
                  setTabActive("Components");
                  handleChangeTab("Components");
                }}
                className={
                  tabActive === "Components"
                    ? "border-b-2 border-primary p-3"
                    : " border-b-2 border-transparent p-3 text-muted-foreground hover:text-primary"
                }
              >
                Components
              </button>
              <ShadTooltip content="Coming Soon">
                <button className="cursor-not-allowed p-3 text-muted-foreground">
                  Bundles
                </button>
              </ShadTooltip>
            </div>
          </div>

          <div className="flex items-center gap-2 px-2">
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
                  variant="outline"
                  size="sq"
                  className={cn(
                    "cursor-pointer",
                    filteredCategories.some((category) => category === i.id)
                      ? "bg-beta-foreground text-background hover:bg-beta-foreground"
                      : ""
                  )}
                >
                  {i.name}
                </Badge>
              ))}
          </div>
          <div className="flex items-end justify-between">
            <span className="px-0.5 text-sm text-muted-foreground">
              {!loading && (
                <>
                  {totalRowsCount} {totalRowsCount > 0 ? "results" : "result"}
                </>
              )}
            </span>

            <Select
              onValueChange={(e) => {
                handleOrderPage(e);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Sort By" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Popular">Most Popular</SelectItem>
                {/* <SelectItem value="Recent">Most Recent</SelectItem> */}
                <SelectItem value="Alphabetical">Alphabetical</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid w-full gap-4 md:grid-cols-2 lg:grid-cols-3">
            {loading ? (
              <>
                <SkeletonCardComponent />
                <SkeletonCardComponent />
                <SkeletonCardComponent />
              </>
            ) : (
              searchData.map((item, idx) => {
                return (
                  <>
                    <MarketCardComponent key={idx} data={item} />
                  </>
                );
              })
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
