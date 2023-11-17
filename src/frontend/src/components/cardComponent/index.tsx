import { useContext, useEffect, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { StoreContext } from "../../contexts/storeContext";
import { getComponent, postLikeComponent } from "../../controllers/API";
import { storeComponent } from "../../types/store";
import cloneFLowWithParent from "../../utils/storeUtils";
import { gradients } from "../../utils/styleUtils";
import { classNames } from "../../utils/utils";
import ShadTooltip from "../ShadTooltipComponent";
import IconComponent from "../genericIconComponent";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../ui/card";

export default function CollectionCardComponent({
  data,
  authorized = true,
  disabled = false,
  button,
  onDelete,
}: {
  data: storeComponent;
  authorized?: boolean;
  disabled?: boolean;
  button?: JSX.Element;
  onDelete?: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const { addFlow } = useContext(FlowsContext);
  const [loadingLike, setLoadingLike] = useState(false);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const { setValidApiKey } = useContext(StoreContext);
  const [liked_by_user, setLiked_by_user] = useState(
    data?.liked_by_user ?? false
  );
  const [likes_count, setLikes_count] = useState(data?.liked_by_count ?? 0);
  const [downloads_count, setDownloads_count] = useState(
    data?.downloads_count ?? 0
  );

  const name = data.is_component ? "Component" : "Flow";

  useEffect(() => {
    if (data) {
      setLiked_by_user(data?.liked_by_user ?? false);
      setLikes_count(data?.liked_by_count ?? 0);
      setDownloads_count(data?.downloads_count ?? 0);
    }
  }, [data, data.liked_by_count, data.liked_by_user, data.downloads_count]);

  function handleInstall() {
    const temp = downloads_count;
    setDownloads_count((old) => old + 1);
    setLoading(true);
    getComponent(data.id)
      .then((res) => {
        const newFlow = cloneFLowWithParent(res, res.id, data.is_component);
        addFlow(true, newFlow)
          .then((id) => {
            setSuccessData({ title: `${name} Installed Successfully.` });
            setLoading(false);
          })
          .catch((error) => {
            setLoading(false);
            setErrorData({
              title: `Error installing the ${name}`,
              list: [error["response"]["data"]["detail"]],
            });
          });
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: `Error installing the ${name}`,
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
        setLikes_count((prev) => prev + 1);
      } else {
        setLikes_count((prev) => prev - 1);
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
    <Card
      className={classNames(
        "group relative flex flex-col justify-between overflow-hidden transition-all hover:shadow-md",
        disabled ? "pointer-events-none opacity-50" : ""
      )}
    >
      <div>
        <CardHeader>
          <div>
            <CardTitle className="flex w-full items-center justify-between gap-3 text-xl">
              <div
                className={classNames(
                  "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-primary",
                  gradients[
                    parseInt(data.id.slice(0, 12), 16) % gradients.length
                  ]
                )}
              >
                <div
                  className={classNames(
                    data.is_component ? "h-7 w-7 rounded-full bg-muted" : "",
                    "flex items-center justify-center"
                  )}
                >
                  {data.is_component ? (
                    <svg className="h-5 w-5" viewBox="0 0 24 24">
                      <defs>
                        <linearGradient
                          id={data.id}
                          x1="0%"
                          y1="0%"
                          x2="100%"
                          y2="100%"
                          className={
                            gradients[
                              parseInt(data.id.slice(0, 12), 16) %
                                gradients.length
                            ]
                          }
                        >
                          <stop
                            offset="0%"
                            stopColor="var(--tw-gradient-from)"
                          />
                          <stop
                            offset="100%"
                            stopColor="var(--tw-gradient-to)"
                          />
                        </linearGradient>
                      </defs>
                      <IconComponent
                        className={classNames(
                          "h-4 w-4",
                          gradients[
                            parseInt(data.id.slice(0, 12), 16) %
                              gradients.length
                          ]
                        )}
                        stroke={`url(#${data.id})`}
                        name="ToyBrick"
                      />
                    </svg>
                  ) : (
                    <IconComponent
                      className="h-4 w-4 text-background"
                      name="Network"
                    />
                  )}
                </div>
              </div>
              <ShadTooltip content={data.name}>
                <div className="w-full truncate">{data.name}</div>
              </ShadTooltip>
              {data?.metadata !== undefined && (
                <div className="flex gap-3">
                  {!data.is_component && (
                    <ShadTooltip content="Components">
                      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <IconComponent name="ToyBrick" className="h-4 w-4" />
                        {data?.metadata?.total ?? 0}
                      </span>
                    </ShadTooltip>
                  )}
                  <ShadTooltip content="Likes">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <IconComponent
                        name="Heart"
                        className={classNames("h-4 w-4 ")}
                      />
                      {likes_count ?? 0}
                    </span>
                  </ShadTooltip>
                  <ShadTooltip content="Downloads">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <IconComponent name="DownloadCloud" className="h-4 w-4" />
                      {downloads_count ?? 0}
                    </span>
                  </ShadTooltip>
                </div>
              )}

              {onDelete && (
                <button onClick={onDelete}>
                  <IconComponent
                    name="Trash2"
                    className="h-5 w-5 text-primary opacity-0 transition-all hover:text-destructive group-hover:opacity-100"
                  />
                </button>
              )}
            </CardTitle>
          </div>
          {data.user_created && data.user_created.username && (
            <span className="text-xs text-primary">
              by <b>{data.user_created.username}</b>
            </span>
          )}

          <CardDescription className="pb-2 pt-2">
            <div className="truncate-doubleline">{data.description}</div>
          </CardDescription>
        </CardHeader>
      </div>

      <CardFooter>
        <div className="flex w-full items-center justify-between gap-2">
          <div className="flex w-full flex-wrap items-end justify-between gap-2">
            <div className="flex w-full flex-1 flex-wrap gap-2">
              {data.tags &&
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
                ))}
            </div>
            {data.liked_by_count != undefined && (
              <div className="flex gap-0.5">
                <ShadTooltip
                  content={authorized ? "Like" : "Please review your API key."}
                >
                  <Button
                    disabled={loadingLike}
                    variant="ghost"
                    size="xs"
                    className={
                      "whitespace-nowrap" +
                      (!authorized ? " cursor-not-allowed" : "")
                    }
                    onClick={() => {
                      handleLike();
                    }}
                  >
                    <IconComponent
                      name="Heart"
                      className={classNames(
                        "h-6 w-6 p-0.5",
                        liked_by_user
                          ? "fill-destructive stroke-destructive"
                          : "",
                        !authorized ? " text-ring" : ""
                      )}
                    />
                  </Button>
                </ShadTooltip>
                <ShadTooltip
                  content={
                    authorized
                      ? "Install Locally"
                      : "Please review your API key."
                  }
                >
                  <Button
                    disabled={loading}
                    variant="ghost"
                    size="xs"
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
                  >
                    <IconComponent
                      name={loading ? "Loader2" : "Plus"}
                      className={classNames(
                        loading ? "h-5 w-5 animate-spin" : "h-6 w-6",
                        !authorized ? " text-ring" : ""
                      )}
                    />
                  </Button>
                </ShadTooltip>
              </div>
            )}
            {button && button}
          </div>
        </div>
      </CardFooter>
    </Card>
  );
}
