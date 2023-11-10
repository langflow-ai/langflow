import { useContext, useEffect, useState } from "react";
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
import { getStoreComponents, getStoreTags } from "../../controllers/API";
import StoreApiKeyModal from "../../modals/StoreApiKeyModal";
import { storeComponent } from "../../types/store";
import { cn } from "../../utils/utils";
import { MarketCardComponent } from "./components/market-card";
export default function StorePage(): JSX.Element {
  const { setTabId } = useContext(TabsContext);
  useEffect(() => {
    setTabId("");
  }, []);
  const { getSavedComponents, loadingSaved, errorApiKey, hasApiKey } =
    useContext(StoreContext);
  const { setErrorData } = useContext(alertContext);
  const [loading, setLoading] = useState(true);
  const [loadingTags, setLoadingTags] = useState(true);
  const [filteredCategories, setFilterCategories] = useState<any[]>([]);
  const [inputText, setInputText] = useState<string>("");
  const [searchData, setSearchData] = useState<storeComponent[]>([]);
  const [totalRowsCount, setTotalRowsCount] = useState(0);
  const [pageSize, setPageSize] = useState(12);
  const [pageIndex, setPageIndex] = useState(1);
  const [pageOrder, setPageOrder] = useState("Popular");
  const [tags, setTags] = useState<{ id: string; name: string }[]>([]);
  const [tabActive, setTabActive] = useState("Flows");
  const [searchText, setSearchText] = useState("");

  useEffect(() => {
    handleGetTags();
  }, []);

  useEffect(() => {
    handleGetComponents();
  }, [
    searchText,
    tabActive,
    pageOrder,
    pageIndex,
    pageSize,
    filteredCategories,
  ]);

  function handleGetTags() {
    setLoadingTags(true);
    getStoreTags().then((res) => {
      setTags(res);
      setLoadingTags(false);
    });
  }

  const handleGetComponents = () => {
    setLoading(true);
    getStoreComponents(
      pageIndex,
      pageSize,
      tabActive === "All" ? null : tabActive === "Flows" ? false : true,
      pageOrder === "Popular" ? "-count(liked_by)" : "name",
      filteredCategories,
      null,
      null,
      searchText === "" ? null : searchText
    )
      .then((res) => {
        setLoading(false);
        setSearchData(res?.results ?? []);
        setTotalRowsCount(Number(res?.count ?? 0));
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

  const updateTags = (tagName: string) => {
    setFilterCategories((prevArray) => {
      const index = prevArray.indexOf(tagName);
      if (index === -1) {
        // Item does not exist in array, add it
        return [...prevArray, tagName];
      } else {
        // Item exists in array, remove it
        return prevArray.filter((_, i) => i !== index);
      }
    });
  };

  return (
    <>
      <Header />

      <div className="community-page-arrangement">
        <div>
          <div className="community-page-nav-arrangement">
            <span className="community-page-nav-title">
              <IconComponent name="Store" className="w-6" />
              Langflow Store
            </span>
            <div className="community-page-nav-button">
              <StoreApiKeyModal
                onCloseModal={() => {
                  getSavedComponents();
                  handleGetTags();
                  handleGetComponents();
                }}
              >
                <Button
                  className={`${
                    errorApiKey && !hasApiKey
                      ? "animate-pulse border-error"
                      : ""
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
                      setSearchText(inputText);
                    }
                  }}
                  value={inputText}
                />
                <button
                  className="absolute bottom-0 right-4 top-0 my-auto h-6 cursor-pointer stroke-1 text-muted-foreground"
                  onClick={() => {
                    setSearchText(inputText);
                  }}
                >
                  <IconComponent
                    name={loading ? "Loader2" : "Search"}
                    className={loading ? " animate-spin" : ""}
                  />
                </button>
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

            <div className="flex h-6 items-center gap-2 px-2">
              {!loadingTags &&
                tags.map((tag, idx) => (
                  <Badge
                    key={idx}
                    onClick={() => {
                      updateTags(tag.name);
                    }}
                    variant="outline"
                    size="sq"
                    className={cn(
                      "cursor-pointer",
                      filteredCategories.some(
                        (category) => category === tag.name
                      )
                        ? "bg-beta-foreground text-background hover:bg-beta-foreground"
                        : ""
                    )}
                  >
                    {tag.name}
                  </Badge>
                ))}
            </div>
            <div className="flex items-end justify-between">
              <span className="px-0.5 text-sm text-muted-foreground">
                {(!loading || searchData.length !== 0) && (
                  <>
                    {totalRowsCount}{" "}
                    {totalRowsCount !== 1 ? "results" : "result"}
                  </>
                )}
              </span>

              <Select
                onValueChange={(e) => {
                  setPageOrder(e);
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
              {!loading || searchData.length !== 0 ? (
                searchData.map((item, idx) => {
                  return (
                    <>
                      <MarketCardComponent
                        key={idx}
                        data={item}
                        authorized={!loadingSaved}
                        disabled={loading}
                      />
                    </>
                  );
                })
              ) : (
                <>
                  <SkeletonCardComponent />
                  <SkeletonCardComponent />
                  <SkeletonCardComponent />
                </>
              )}
            </div>
          </div>
        </div>
        {(!loading || searchData.length !== 0) && (
          <div className="relative my-6">
            <PaginatorComponent
              storeComponent={true}
              pageIndex={pageIndex}
              pageSize={pageSize}
              totalRowsCount={totalRowsCount}
              paginate={(pageSize, pageIndex) => {
                setPageIndex(pageIndex);
                setPageSize(pageSize);
              }}
            ></PaginatorComponent>
          </div>
        )}
      </div>
    </>
  );
}
