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
  const filterComponent = useRef<boolean | null>(null);

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
    setErrorApiKey(false);
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

    getStoreComponents(index - 1, size, filterComponent.current)
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
    getStoreComponents(pageIndex, pageSize, filterComponent.current)
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

  const [tabActive, setTabActive] = useState("Flows");

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
              <Search className="absolute bottom-0 right-4 top-0 my-auto h-6 stroke-1 text-muted-foreground " />
            </div>
            <div className="ml-4 flex w-full gap-2 border-b border-border">
              <button
                onClick={() => {
                  setTabActive("All");
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
          {/* <div className="flex items-center gap-3 text-sm">
            <button className="flex h-8 items-center justify-between rounded-md border border-ring/60 px-4 py-2 text-sm text-primary hover:bg-muted">
              <IconComponent name="CheckCircle2" className="mr-2 h-4 w-4 " />
              Installed Locally
            </button>
            <Select
              onValueChange={(value) => {
                if (value === "Flow") {
                  filterComponent.current = false;
                } else if (value === "Component") {
                  filterComponent.current = true;
                } else {
                  filterComponent.current = null;
                }
                setPageIndex(1);
                setPageSize(10);
                handleGetComponents();
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Component Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Both</SelectItem>
                <SelectItem value="Flow">Flows</SelectItem>
                <SelectItem value="Component">Components</SelectItem>
              </SelectContent>
            </Select>
            <Select
              onValueChange={(value) => {
                if (value === "Flow") {
                  filterComponent.current = false;
                } else if (value === "Component") {
                  filterComponent.current = true;
                } else {
                  filterComponent.current = null;
                }
                setPageIndex(1);
                setPageSize(10);
                handleGetComponents();
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Use Cases" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Both</SelectItem>
                <SelectItem value="Flow">Flows</SelectItem>
                <SelectItem value="Component">Components</SelectItem>
              </SelectContent>
            </Select>
            <Select
              onValueChange={(value) => {
                if (value === "Flow") {
                  filterComponent.current = false;
                } else if (value === "Component") {
                  filterComponent.current = true;
                } else {
                  filterComponent.current = null;
                }
                setPageIndex(1);
                setPageSize(10);
                handleGetComponents();
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Models" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Both</SelectItem>
                <SelectItem value="Flow">Flows</SelectItem>
                <SelectItem value="Component">Components</SelectItem>
              </SelectContent>
            </Select>
            <Select
              onValueChange={(value) => {
                if (value === "Flow") {
                  filterComponent.current = false;
                } else if (value === "Component") {
                  filterComponent.current = true;
                } else {
                  filterComponent.current = null;
                }
                setPageIndex(1);
                setPageSize(10);
                handleGetComponents();
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Payment" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Both</SelectItem>
                <SelectItem value="Flow">Flows</SelectItem>
                <SelectItem value="Component">Components</SelectItem>
              </SelectContent>
            </Select>
          </div> */}
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
              2,117 results
            </span>
            <Select
              onValueChange={(value) => {
                if (value === "Flow") {
                  filterComponent.current = false;
                } else if (value === "Component") {
                  filterComponent.current = true;
                } else {
                  filterComponent.current = null;
                }
                setPageIndex(1);
                setPageSize(10);
                handleGetComponents();
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Sort By" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Most Popular</SelectItem>
                <SelectItem value="Flow">Most Recent</SelectItem>
                <SelectItem value="Component">Alphabetical</SelectItem>
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
