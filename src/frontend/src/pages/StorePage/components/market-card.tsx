import { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ShadTooltip from "../../../components/ShadTooltipComponent";
import IconComponent from "../../../components/genericIconComponent";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { alertContext } from "../../../contexts/alertContext";
import { FlowsContext } from "../../../contexts/flowsContext";
import { StoreContext } from "../../../contexts/storeContext";
import {
  getComponent,
  postLikeComponent,
  saveFlowStore,
} from "../../../controllers/API";
import { storeComponent } from "../../../types/store";
import cloneFLowWithParent from "../../../utils/storeUtils";
import { classNames } from "../../../utils/utils";

export const MarketCardComponent = ({
  data,
  authorized = true,
  disabled = false,
  installable = false,
}: {
  data: storeComponent;
  authorized?: boolean;
  disabled?: boolean;
  installable?: boolean;
}) => {
  const { savedFlows } = useContext(StoreContext);
  const [added, setAdded] = useState(savedFlows.has(data.id) ? true : false);
  const [installed, setInstalled] = useState(false);
  const [loading, setLoading] = useState(false);
  const { addFlow } = useContext(FlowsContext);
  const [loadingLike, setLoadingLike] = useState(false);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const [liked_by_user, setLiked_by_user] = useState(data.liked_by_user);
  const [likes_count, setLikes_count] = useState(data.liked_by_count ?? 0);

  const name = data.is_component ? "Component" : "Flow";

  useEffect(() => {
    setAdded(savedFlows.has(data.id) ? true : false);
  }, [savedFlows]);

  function handleAdd() {
    setLoading(true);
    getComponent(data.id).then(
      (res) => {
        console.log(res);
        const newFLow = cloneFLowWithParent(res, res.id, data.is_component);
        console.log(newFLow);
        saveFlowStore(
          newFLow,
          data.tags.map((tag) => tag.id)
        )
          .then(() => {
            setAdded(true);
            setLoading(false);
            setSuccessData({ title: `${name} added to account.` });
          })
          .catch((error) => {
            console.error(error);
            setErrorData({
              title: `Error on adding ${name}`,
              list: [error["response"]["data"]["detail"]],
            });
          });
      },
      (error) => {
        console.log(error);
      }
    );
  }

  const navigate = useNavigate();

  function handleInstall() {
    setLoading(true);
    getComponent(data.id).then((res) => {
      const newFlow = cloneFLowWithParent(res, res.id, data.is_component);
      addFlow(true, newFlow).then((id) => {
        setSuccessData({ title: `${name} Installed` });
        setLoading(false);
        setInstalled(true);
        if (!data.is_component) navigate("/flow/" + id);
      });
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
      console.log(data.id);
      postLikeComponent(data.id)
        .catch((error) => {
          setLoadingLike(false);
          console.error(error);
          setLiked_by_user(temp);
          setLikes_count(tempNum);
          setErrorData({
            title: `Error on liking ${name}.`,
            list: [error["response"]["data"]["detail"]],
          });
        })
        .then((response) => {
          setLoadingLike(false);
          setLikes_count(response.likes_count);
          setLiked_by_user(response.liked_by_user);
        });
    }
  }

  const totalComponentsMetadata = () => {
    return data?.metadata ? data.metadata["total"] : 0;
  };

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
              <ShadTooltip content={data.name}>
                <div className="w-full truncate">{data.name}</div>
              </ShadTooltip>
              <div className="flex gap-3">
                {!data.is_component && (
                  <ShadTooltip content="Components">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <IconComponent name="ToyBrick" className="h-4 w-4" />
                      {totalComponentsMetadata()}
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
                    {data.downloads_count}
                  </span>
                </ShadTooltip>
              </div>
            </CardTitle>
          </div>
          <span className="text-xs text-primary">
            by <b>{data.user_created.username}</b>
          </span>
          <CardDescription className="pb-2 pt-2">
            <div className="truncate-doubleline">{data.description}</div>
          </CardDescription>
        </CardHeader>
      </div>

      <CardFooter>
        <div className="flex w-full items-center justify-between gap-2">
          <div className="flex w-full flex-wrap items-end justify-between gap-2">
            <div className="flex w-full flex-1 flex-wrap gap-2">
              {data.tags.length > 0 &&
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
            <div className="flex gap-0.5">
              <ShadTooltip
                content={authorized ? "Like" : "Please review your API key."}
              >
                <Button
                  disabled={loadingLike || !authorized}
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
                    ? added
                      ? installable
                        ? "Install Locally"
                        : "Added to Account"
                      : "Add to Account"
                    : "Please review your API key."
                }
              >
                <Button
                  variant="ghost"
                  size="xs"
                  className={
                    "whitespace-nowrap" +
                    (!authorized ? " cursor-not-allowed" : "")
                  }
                  onClick={() => {
                    if (loading || !authorized) {
                      return;
                    }
                    if (!added) {
                      handleAdd();
                    } else if (installable) {
                      handleInstall();
                    }
                  }}
                >
                  <IconComponent
                    name={
                      loading
                        ? "Loader2"
                        : added && installable && !installed
                        ? "ExternalLink"
                        : added
                        ? "Check"
                        : "Plus"
                    }
                    className={classNames(
                      !added && !installable && !loading
                        ? "h-6 w-6"
                        : "h-5 w-5",
                      ((added && !installable) || installed) && !loading
                        ? "text-chat-send"
                        : "",
                      added && installable && !installed && !loading
                        ? "text-high-indigo"
                        : "",
                      loading ? " animate-spin" : "",
                      !authorized ? " text-ring" : ""
                    )}
                  />
                </Button>
              </ShadTooltip>
            </div>
          </div>
        </div>
      </CardFooter>
    </Card>
  );
};
