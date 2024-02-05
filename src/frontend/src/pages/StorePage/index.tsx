import { uniqueId } from "lodash";
import { useContext, useEffect, useState } from "react";
import PaginatorComponent from "../../components/PaginatorComponent";
import ShadTooltip from "../../components/ShadTooltipComponent";
import CollectionCardComponent from "../../components/cardComponent";
import IconComponent from "../../components/genericIconComponent";
import PageLayout from "../../components/pageLayout";
import { SkeletonCardComponent } from "../../components/skeletonCardComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";

import { Link, useParams } from "react-router-dom";
import { TagsSelector } from "../../components/tagsSelectorComponent";
import { Badge } from "../../components/ui/badge";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { alertContext } from "../../contexts/alertContext";
import { AuthContext } from "../../contexts/authContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { StoreContext } from "../../contexts/storeContext";
import { getStoreComponents, getStoreTags } from "../../controllers/API";
import StoreApiKeyModal from "../../modals/StoreApiKeyModal";
import { storeComponent } from "../../types/store";
import { cn } from "../../utils/utils";
export default function StorePage(): JSX.Element {
  const { validApiKey, setValidApiKey, hasApiKey, loadingApiKey } =
    useContext(StoreContext);
  const { apiKey } = useContext(AuthContext);
  const { setErrorData } = useContext(alertContext);
  const { setTabId } = useContext(FlowsContext);
  const [loading, setLoading] = useState(true);
  const [loadingTags, setLoadingTags] = useState(true);
  const { id } = useParams();
  const [filteredCategories, setFilterCategories] = useState<any[]>([]);
  const [inputText, setInputText] = useState<string>("");
  const [searchData, setSearchData] = useState<storeComponent[]>([]);
  const [totalRowsCount, setTotalRowsCount] = useState(0);
  const [pageSize, setPageSize] = useState(12);
  const [pageIndex, setPageIndex] = useState(1);
  const [pageOrder, setPageOrder] = useState("Popular");
  const [tags, setTags] = useState<{ id: string; name: string }[]>([]);
  const [tabActive, setTabActive] = useState("All");
  const [searchNow, setSearchNow] = useState("");
  const [selectFilter, setSelectFilter] = useState("all");

  useEffect(() => {
    handleGetTags();
  }, []);

  useEffect(() => {
    if (!loadingApiKey) {
      if (!hasApiKey) {
        setErrorData({
          title: "API Key Error",
          list: [
            "You don't have an API Key. Please add one to use the Langflow Store.",
          ],
        });
        setLoading(false);
      } else if (!validApiKey) {
        setErrorData({
          title: "API Key Error",
          list: [
            "Your API Key is not valid. Please add a valid API Key to use the Langflow Store.",
          ],
        });
      }
    }
  }, [loadingApiKey, validApiKey, hasApiKey]);

  useEffect(() => {
    handleGetComponents();
  }, [
    tabActive,
    pageOrder,
    pageIndex,
    pageSize,
    filteredCategories,
    selectFilter,
    validApiKey,
    hasApiKey,
    apiKey,
    searchNow,
    loadingApiKey,
    id,
  ]);

  function handleGetTags() {
    setLoadingTags(true);
    getStoreTags()
      .then((res) => {
        setTags(res);
        setLoadingTags(false);
      })
      .catch((err) => {
        console.log(err);
        setLoadingTags(false);
      });
  }

  function handleGetComponents() {
    if (!hasApiKey || loadingApiKey) return;
    setLoading(true);
    getStoreComponents({
      component_id: id,
      page: pageIndex,
      limit: pageSize,
      is_component:
        tabActive === "All" ? null : tabActive === "Flows" ? false : true,
      sort: pageOrder === "Popular" ? "-count(downloads)" : "name",
      tags: filteredCategories,
      liked: selectFilter === "likedbyme" && validApiKey ? true : null,
      isPrivate: null,
      search: inputText === "" ? null : inputText,
      filterByUser: selectFilter === "createdbyme" && validApiKey ? true : null,
    })
      .then((res) => {
        if (!res?.authorized && validApiKey === true) {
          setValidApiKey(false);
          setSelectFilter("all");
        } else {
          if (res?.authorized) {
            setValidApiKey(true);
          }
          setLoading(false);
          setSearchData(res?.results ?? []);
          setTotalRowsCount(
            filteredCategories?.length === 0
              ? Number(res?.count ?? 0)
              : res?.results?.length ?? 0
          );
        }
      })
      .catch((err) => {
        if (err.response.status === 403 || err.response.status === 401) {
          setValidApiKey(false);
        } else {
          setSearchData([]);
          setTotalRowsCount(0);
          setLoading(false);
          setErrorData({
            title: "Error getting components.",
            list: [err["response"]["data"]["detail"]],
          });
        }
      });
  }

  // Set a null id
  useEffect(() => {
    setTabId("");
  }, []);

  function resetPagination() {
    setPageIndex(1);
    setPageSize(12);
  }

  return (
    <PageLayout
      betaIcon
      title="Langflow Store"
      description="Search flows and components from the community."
      button={
        <>
          {StoreApiKeyModal && (
            <StoreApiKeyModal disabled={loading}>
              <Button
                disabled={loading}
                className={cn(
                  `${!validApiKey ? "animate-pulse border-error" : ""}`,
                  loading ? "cursor-not-allowed" : ""
                )}
                variant="primary"
              >
                <IconComponent name="Key" className="mr-2 w-4" />
                API Key
              </Button>
            </StoreApiKeyModal>
          )}
        </>
      }
    >
      <div className="flex h-full w-full flex-col justify-between">
        <div className="flex w-full flex-col gap-4 p-0">
          <div className="flex items-end gap-4">
            <div className="relative h-12 w-[40%]">
              <Input
                disabled={loading}
                placeholder="Search Flows and Components"
                className="absolute h-12 pl-5 pr-12"
                onChange={(e) => {
                  setInputText(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setSearchNow(uniqueId());
                  }
                }}
                value={inputText}
              />
              <button
                disabled={loading}
                className="absolute bottom-0 right-4 top-0 my-auto h-6 cursor-pointer stroke-1 text-muted-foreground"
                onClick={() => {
                  setSearchNow(uniqueId());
                }}
              >
                <IconComponent
                  name={loading ? "Loader2" : "Search"}
                  className={loading ? " animate-spin cursor-not-allowed" : ""}
                />
              </button>
            </div>
            <div className="ml-4 flex w-full gap-2 border-b border-border">
              <button
                disabled={loading}
                onClick={() => {
                  setTabActive("All");
                }}
                className={
                  (tabActive === "All"
                    ? "border-b-2 border-primary p-3"
                    : " border-b-2 border-transparent p-3 text-muted-foreground hover:text-primary") +
                  (loading ? " cursor-not-allowed " : "")
                }
              >
                All
              </button>
              <button
                disabled={loading}
                onClick={() => {
                  resetPagination();
                  setTabActive("Flows");
                }}
                className={
                  (tabActive === "Flows"
                    ? "border-b-2 border-primary p-3"
                    : " border-b-2 border-transparent p-3 text-muted-foreground hover:text-primary") +
                  (loading ? " cursor-not-allowed " : "")
                }
              >
                Flows
              </button>
              <button
                disabled={loading}
                onClick={() => {
                  resetPagination();
                  setTabActive("Components");
                }}
                className={
                  (tabActive === "Components"
                    ? "border-b-2 border-primary p-3"
                    : " border-b-2 border-transparent p-3 text-muted-foreground hover:text-primary") +
                  (loading ? " cursor-not-allowed " : "")
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

          <div className="flex items-center gap-2">
            <Select
              disabled={loading}
              onValueChange={setSelectFilter}
              value={selectFilter}
            >
              <SelectTrigger className="mr-4 w-[160px] flex-shrink-0">
                <SelectValue placeholder="Filter Values" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem
                    disabled={!hasApiKey || !validApiKey}
                    value="createdbyme"
                  >
                    Created By Me
                  </SelectItem>
                  <SelectItem
                    disabled={!hasApiKey || !validApiKey}
                    value="likedbyme"
                  >
                    Liked By Me
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            {id === undefined ? (
              <TagsSelector
                tags={tags}
                loadingTags={loadingTags}
                disabled={loading}
                selectedTags={filteredCategories}
                setSelectedTags={setFilterCategories}
              />
            ) : (
              <Badge
                key="id"
                variant="outline"
                size="sq"
                className="gap-2 bg-beta-foreground text-background hover:bg-beta-foreground"
              >
                <Link to={"/store"} className="cursor-pointer">
                  <IconComponent name="X" className="h-4 w-4" />
                </Link>
                {id}
              </Badge>
            )}
          </div>
          <div className="flex items-end justify-between">
            <span className="px-0.5 text-sm text-muted-foreground">
              {(!loading || searchData.length !== 0) && (
                <>
                  {totalRowsCount} {totalRowsCount !== 1 ? "results" : "result"}
                </>
              )}
            </span>

            <Select
              disabled={loading}
              onValueChange={(e) => {
                setPageOrder(e);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Popular" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Popular">Popular</SelectItem>
                {/* <SelectItem value="Recent">Most Recent</SelectItem> */}
                <SelectItem value="Alphabetical">Alphabetical</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid w-full gap-4 md:grid-cols-2 lg:grid-cols-3">
            {!loading || searchData.length !== 0 ? (
              searchData.map((item) => {
                return (
                  <>
                    <CollectionCardComponent
                      key={item.id}
                      data={item}
                      authorized={validApiKey}
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

          {!loading && searchData?.length === 0 && (
            <div className="mt-6 flex w-full items-center justify-center text-center">
              <div className="flex h-full w-full flex-col">
                <div className="flex w-full flex-col gap-4">
                  <div className="grid w-full gap-4">
                    {selectFilter != "all" ? (
                      <>
                        You haven't{" "}
                        {selectFilter === "createdbyme" ? "created" : "liked"}{" "}
                        anything with the selected filters yet.
                      </>
                    ) : (
                      <>
                        There are no{" "}
                        {tabActive == "Flows" ? "Flows" : "Components"} with the
                        selected filters.
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
        {!loading && searchData.length > 0 && (
          <div className="relative py-6">
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
    </PageLayout>
  );
}
