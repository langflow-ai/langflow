import { uniqueId } from "lodash";
import { useContext, useEffect, useState } from "react";
import CollectionCardComponent from "../../components/cardComponent";
import IconComponent from "../../components/genericIconComponent";
import PageLayout from "../../components/pageLayout";
import ShadTooltip from "../../components/shadTooltipComponent";
import { SkeletonCardComponent } from "../../components/skeletonCardComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";

import { Link, useNavigate, useParams } from "react-router-dom";
import PaginatorComponent from "../../components/paginatorComponent";
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
import {
  APIKEY_ERROR_ALERT,
  COMPONENTS_ERROR_ALERT,
  INVALID_API_ERROR_ALERT,
  NOAPI_ERROR_ALERT,
} from "../../constants/alerts_constants";
import { STORE_DESC, STORE_TITLE } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import { getStoreComponents, getStoreTags } from "../../controllers/API";
import StoreApiKeyModal from "../../modals/storeApiKeyModal";
import useAlertStore from "../../stores/alertStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useStoreStore } from "../../stores/storeStore";
import { storeComponent } from "../../types/store";
import { cn } from "../../utils/utils";

export default function StorePage(): JSX.Element {
  const hasApiKey = useStoreStore((state) => state.hasApiKey);
  const validApiKey = useStoreStore((state) => state.validApiKey);
  const loadingApiKey = useStoreStore((state) => state.loadingApiKey);

  const setValidApiKey = useStoreStore((state) => state.updateValidApiKey);

  const { apiKey } = useContext(AuthContext);

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId
  );
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
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

  const navigate = useNavigate();

  useEffect(() => {
    if (!loadingApiKey) {
      if (!hasApiKey) {
        setErrorData({
          title: APIKEY_ERROR_ALERT,
          list: [NOAPI_ERROR_ALERT],
        });
        setLoading(false);
      } else if (!validApiKey) {
        setErrorData({
          title: APIKEY_ERROR_ALERT,
          list: [INVALID_API_ERROR_ALERT],
        });
      }
    }
  }, [loadingApiKey, validApiKey, hasApiKey, currentFlowId]);

  useEffect(() => {
    handleGetTags();
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
    if (loadingApiKey) return;
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
        if (err.response?.status === 403 || err.response?.status === 401) {
          setValidApiKey(false);
        } else {
          setSearchData([]);
          setTotalRowsCount(0);
          setLoading(false);
          setErrorData({
            title: COMPONENTS_ERROR_ALERT,
            list: [err["response"]["data"]["detail"]],
          });
        }
      });
  }

  // Set a null id
  useEffect(() => {
    setCurrentFlowId("");
  }, []);

  function resetPagination() {
    setPageIndex(1);
    setPageSize(12);
  }

  return (
    <PageLayout
      betaIcon
      title={STORE_TITLE}
      description={STORE_DESC}
      button={
        <>
          {StoreApiKeyModal && (
            <StoreApiKeyModal disabled={loading}>
              <Button
                data-testid="api-key-button-store"
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
                data-testid="search-store-input"
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
                data-testid="search-store-button"
              >
                <IconComponent
                  name={loading ? "Loader2" : "Search"}
                  className={loading ? " animate-spin cursor-not-allowed" : ""}
                />
              </button>
            </div>
            <div className="ml-4 flex w-full gap-2 border-b border-border">
              <button
                data-testid="all-button-store"
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
                data-testid="flows-button-store"
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
                data-testid="components-button-store"
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
              <SelectTrigger data-testid="select-order-store">
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
                      playground={
                        item.last_tested_version?.includes("1.0.0") &&
                        !item.is_component
                      }
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
