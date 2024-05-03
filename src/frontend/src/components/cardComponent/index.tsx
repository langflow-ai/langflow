import { useEffect, useState } from "react";
import { getComponent, postLikeComponent } from "../../controllers/API";
import IOModal from "../../modals/IOModal";
import DeleteConfirmationModal from "../../modals/deleteConfirmationModal";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useStoreStore } from "../../stores/storeStore";
import { storeComponent } from "../../types/store";
import cloneFLowWithParent from "../../utils/storeUtils";
import { cn, convertTestName } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import ShadTooltip from "../shadTooltipComponent";
import { Button } from "../ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../ui/card";
import Loading from "../ui/loading";

export default function CollectionCardComponent({
  data,
  authorized = true,
  disabled = false,
  button,
  onClick,
  onDelete,
  playground,
}: {
  data: storeComponent;
  authorized?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  button?: JSX.Element;
  playground?: boolean;
  onDelete?: () => void;
}) {
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setValidApiKey = useStoreStore((state) => state.updateValidApiKey);
  const cleanFlowPool = useFlowStore((state) => state.CleanFlowPool);
  const isStore = false;
  const [loading, setLoading] = useState(false);
  const [loadingLike, setLoadingLike] = useState(false);
  const [liked_by_user, setLiked_by_user] = useState(
    data?.liked_by_user ?? false,
  );
  const [likes_count, setLikes_count] = useState(data?.liked_by_count ?? 0);
  const [downloads_count, setDownloads_count] = useState(
    data?.downloads_count ?? 0,
  );
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const getFlowById = useFlowsManagerStore((state) => state.getFlowById);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const [openPlayground, setOpenPlayground] = useState(false);
  const [openDelete, setOpenDelete] = useState(false);
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId,
  );
  const [loadingPlayground, setLoadingPlayground] = useState(false);

  const name = data.is_component ? "Component" : "Flow";

  async function getFlowData() {
    const res = await getComponent(data.id);
    const newFlow = cloneFLowWithParent(res, res.id, data.is_component, true);
    return newFlow;
  }

  useEffect(() => {
    if (currentFlowId && playground) {
      if (openPlayground) {
        setNodes(currentFlow?.data?.nodes ?? [], true);
        setEdges(currentFlow?.data?.edges ?? [], true);
      } else {
        setNodes([], true);
        setEdges([], true);
      }
      cleanFlowPool();
    }
  }, [openPlayground]);

  useEffect(() => {
    if (data) {
      setLiked_by_user(data?.liked_by_user ?? false);
      setLikes_count(data?.liked_by_count ?? 0);
      setDownloads_count(data?.downloads_count ?? 0);
    }
  }, [data, data.liked_by_count, data.liked_by_user, data.downloads_count]);

  function handleInstall() {
    const temp = downloads_count;
    setDownloads_count((old) => Number(old) + 1);
    setLoading(true);
    getComponent(data.id)
      .then((res) => {
        const newFlow = cloneFLowWithParent(res, res.id, data.is_component);
        addFlow(true, newFlow)
          .then((id) => {
            setSuccessData({
              title: `${name} ${
                isStore ? "Downloaded" : "Installed"
              } Successfully.`,
            });
            setLoading(false);
          })
          .catch((error) => {
            setLoading(false);
            setErrorData({
              title: `Error ${
                isStore ? "downloading" : "installing"
              } the ${name}`,
              list: [error["response"]["data"]["detail"]],
            });
          });
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: `Error ${isStore ? "downloading" : "installing"} the ${name}`,
          list: [err["response"]["data"]["detail"]],
        });
        setDownloads_count(temp);
      });
  }

  function handleLike() {
    setLoadingLike(true);
    if (liked_by_user !== undefined || liked_by_user !== null) {
      const temp = liked_by_user;
      const tempNum = likes_count;
      setLiked_by_user((prev) => !prev);
      if (!temp) {
        setLikes_count((prev) => Number(prev) + 1);
      } else {
        setLikes_count((prev) => Number(prev) - 1);
      }
      postLikeComponent(data.id)
        .then((response) => {
          setLoadingLike(false);
          setLikes_count(response.data.likes_count);
          setLiked_by_user(response.data.liked_by_user);
        })
        .catch((error) => {
          setLoadingLike(false);
          setLikes_count(tempNum);
          setLiked_by_user(temp);
          if (error.response.status === 403) {
            setValidApiKey(false);
          } else {
            console.error(error);
            setErrorData({
              title: `Error liking ${name}.`,
              list: [error["response"]["data"]["detail"]],
            });
          }
        });
    }
  }

  return (
    <>
      <Card
        data-testid={`card-${convertTestName(data.name)}`}
        //TODO check color schema
        className={cn(
          "group relative flex min-h-[11rem] flex-col justify-between overflow-hidden transition-all hover:bg-muted/50 hover:shadow-md hover:dark:bg-[#ffffff10]",
          disabled ? "pointer-events-none opacity-50" : "",
          onClick ? "cursor-pointer" : "",
        )}
        onClick={onClick}
      >
        <div>
          <CardHeader>
            <div>
              <CardTitle className="flex w-full items-center justify-between gap-3 text-xl">
                <IconComponent
                  className={cn(
                    "flex-shrink-0",
                    data.is_component
                      ? "mx-0.5 h-6 w-6 text-component-icon"
                      : "h-7 w-7 flex-shrink-0 text-flow-icon",
                  )}
                  name={data.is_component ? "ToyBrick" : "Group"}
                />
                <ShadTooltip content={data.name}>
                  <div className="w-full truncate">{data.name}</div>
                </ShadTooltip>
                {data?.metadata !== undefined && (
                  <div className="flex gap-3">
                    {data.private && (
                      <ShadTooltip content="Private">
                        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <IconComponent name="Lock" className="h-4 w-4" />
                        </span>
                      </ShadTooltip>
                    )}
                    {!data.is_component && (
                      <ShadTooltip content="Components">
                        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <IconComponent name="ToyBrick" className="h-4 w-4" />
                          <span data-testid={`total-${data.name}`}>
                            {data?.metadata?.total ?? 0}
                          </span>
                        </span>
                      </ShadTooltip>
                    )}
                    <ShadTooltip content="Likes">
                      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <IconComponent
                          name="Heart"
                          className={cn("h-4 w-4 ")}
                        />
                        <span data-testid={`likes-${data.name}`}>
                          {likes_count ?? 0}
                        </span>
                      </span>
                    </ShadTooltip>
                    <ShadTooltip content="Downloads">
                      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <IconComponent
                          name="DownloadCloud"
                          className="h-4 w-4"
                        />
                        <span data-testid={`downloads-${data.name}`}>
                          {downloads_count ?? 0}
                        </span>
                      </span>
                    </ShadTooltip>
                  </div>
                )}

                {onDelete && data?.metadata === undefined && (
                  <button
                    className="z-50"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenDelete(true);
                    }}
                  >
                    <IconComponent
                      name="Trash2"
                      className="h-5 w-5 text-primary opacity-0 transition-all hover:text-destructive group-hover:opacity-100"
                    />
                  </button>
                )}
              </CardTitle>
            </div>
            <div className="flex gap-2">
              {data.user_created && data.user_created.username && (
                <span className="text-sm text-primary">
                  by <b>{data.user_created.username}</b>
                  {data.last_tested_version && (
                    <>
                      {" "}
                      |{" "}
                      <span className="text-xs">
                        {" "}
                        ⛓︎ v{data.last_tested_version}
                      </span>
                    </>
                  )}
                </span>
              )}
              <div className="flex w-full flex-1 flex-wrap gap-2">
                {/* {data.tags &&
                  data.tags.length > 0 &&
                  data.tags.map((tag, index) => (
                    <Badge
                      key={index}
                      variant="outline"
                      size="xq"
                      className="text-muted-foreground"
                    >
                      {tag.name}
                    </Badge>
                  ))} */}
              </div>
            </div>

            <CardDescription className="pb-2 pt-2">
              <div className="truncate-doubleline">{data.description}</div>
            </CardDescription>
          </CardHeader>
        </div>

        <CardFooter>
          <div className="z-50 flex w-full items-center justify-between gap-2">
            <div className="flex w-full flex-wrap items-end justify-end gap-2">
              {playground && data?.metadata !== undefined ? (
                <Button
                  disabled={loadingPlayground}
                  key={data.id}
                  tabIndex={-1}
                  variant="outline"
                  size="sm"
                  className="z-50 gap-2 whitespace-nowrap"
                  data-testid={"playground-flow-button-" + data.id}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setLoadingPlayground(true);
                    if (getFlowById(data.id)) {
                      setCurrentFlowId(data.id);
                      setOpenPlayground(true);
                      setLoadingPlayground(false);
                    } else {
                      getFlowData().then((res) => {
                        setCurrentFlow(res);
                        setOpenPlayground(true);
                        setLoadingPlayground(false);
                      });
                    }
                  }}
                >
                  {!loadingPlayground ? (
                    <IconComponent
                      name="BotMessageSquareIcon"
                      className="h-4 w-4 select-none"
                    />
                  ) : (
                    <Loading className="h-4 w-4 text-medium-indigo" />
                  )}
                  Playground
                </Button>
              ) : undefined}
              {data.liked_by_count != undefined && (
                <div className="flex gap-0.5">
                  {onDelete && data?.metadata !== undefined ? (
                    <ShadTooltip
                      content={
                        authorized ? "Delete" : "Please review your API key."
                      }
                    >
                      <DeleteConfirmationModal
                        onConfirm={() => {
                          onDelete();
                        }}
                      >
                        <Button
                          variant="ghost"
                          size="icon"
                          className={
                            "whitespace-nowrap" +
                            (!authorized ? " cursor-not-allowed" : "")
                          }
                        >
                          <IconComponent
                            data-testid={`delete-${convertTestName(data.name)}`}
                            name="Trash2"
                            className={cn(
                              "h-5 w-5",
                              !authorized ? " text-ring" : "",
                            )}
                          />
                        </Button>
                      </DeleteConfirmationModal>
                    </ShadTooltip>
                  ) : (
                    <ShadTooltip
                      content={
                        authorized ? "Like" : "Please review your API key."
                      }
                    >
                      <Button
                        disabled={loadingLike}
                        variant="ghost"
                        size="icon"
                        className={
                          "whitespace-nowrap" +
                          (!authorized ? " cursor-not-allowed" : "")
                        }
                        onClick={() => {
                          if (!authorized) {
                            return;
                          }
                          handleLike();
                        }}
                        data-testid={`like-${data.name}`}
                      >
                        <IconComponent
                          name="Heart"
                          className={cn(
                            "h-5 w-5",
                            liked_by_user
                              ? "fill-destructive stroke-destructive"
                              : "",
                            !authorized ? " text-ring" : "",
                          )}
                        />
                      </Button>
                    </ShadTooltip>
                  )}
                  <ShadTooltip
                    content={
                      authorized
                        ? isStore
                          ? "Download"
                          : "Install Locally"
                        : "Please review your API key."
                    }
                  >
                    <Button
                      disabled={loading}
                      variant="ghost"
                      size="icon"
                      className={
                        "whitespace-nowrap" +
                        (!authorized ? " cursor-not-allowed" : "") +
                        (!loading ? " p-0.5" : "")
                      }
                      onClick={() => {
                        if (loading || !authorized) {
                          return;
                        }
                        handleInstall();
                      }}
                      data-testid={`install-${data.name}`}
                    >
                      <IconComponent
                        name={
                          loading ? "Loader2" : isStore ? "Download" : "Plus"
                        }
                        className={cn(
                          loading ? "h-5 w-5 animate-spin" : "h-5 w-5",
                          !authorized ? " text-ring" : "",
                        )}
                      />
                    </Button>
                  </ShadTooltip>
                </div>
              )}
              {playground && data?.metadata === undefined && (
                <Button
                  disabled={loadingPlayground}
                  key={data.id}
                  tabIndex={-1}
                  variant="primary"
                  size="sm"
                  className="gap-2 whitespace-nowrap bg-muted"
                  data-testid={"playground-flow-button-" + data.id}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setLoadingPlayground(true);
                    if (getFlowById(data.id)) {
                      setCurrentFlowId(data.id);
                      setOpenPlayground(true);
                      setLoadingPlayground(false);
                    } else {
                      getFlowData().then((res) => {
                        setCurrentFlow(res);
                        setOpenPlayground(true);
                        setLoadingPlayground(false);
                      });
                    }
                  }}
                >
                  {!loadingPlayground ? (
                    <IconComponent
                      name="BotMessageSquareIcon"
                      className="h-4 w-4 select-none"
                    />
                  ) : (
                    <Loading className="h-4 w-4 text-medium-indigo" />
                  )}
                  Playground
                </Button>
              )}
            </div>
          </div>
        </CardFooter>
      </Card>
      {openPlayground && (
        <IOModal
          cleanOnClose={true}
          open={openPlayground}
          setOpen={setOpenPlayground}
        >
          <></>
        </IOModal>
      )}
      {openDelete && (
        <DeleteConfirmationModal
          open={openDelete}
          setOpen={setOpenDelete}
          onConfirm={() => {
            if (onDelete) onDelete();
          }}
        >
          <></>
        </DeleteConfirmationModal>
      )}
    </>
  );
}
