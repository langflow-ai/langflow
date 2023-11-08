import { useContext, useEffect, useRef, useState } from "react";
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
import { StoreContext } from "../../../contexts/storeContext";
import { TabsContext } from "../../../contexts/tabsContext";
import {
  getComponent,
  postLikeComponent,
  saveFlowStore,
} from "../../../controllers/API";
import { FlowType } from "../../../types/flow";
import { storeComponent } from "../../../types/store";
import cloneFLowWithParent from "../../../utils/storeUtils";
import { classNames } from "../../../utils/utils";

export const MarketCardComponent = ({
  data,
  authorized = true,
  disabled = false,
}: {
  data: storeComponent;
  authorized?: boolean;
  disabled?: boolean;
}) => {
  const { savedFlows } = useContext(StoreContext);
  const [added, setAdded] = useState(savedFlows.has(data.id) ? true : false);
  const [loading, setLoading] = useState(false);
  const { addFlow } = useContext(TabsContext);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const flowData = useRef<FlowType>();
  const [liked_by_user, setLiked_by_user] = useState(data.liked_by_user);
  const [likes_count, setLikes_count] = useState(data.liked_by_count ?? 0);

  useEffect(() => {
    setAdded(savedFlows.has(data.id) ? true : false);
  }, [savedFlows]);

  function handleAdd() {
    setLoading(true);
    getComponent(data.id).then(
      (res) => {
        console.log(res);
        const newFLow = cloneFLowWithParent(res, res.id, data.is_component);
        flowData.current = newFLow;
        console.log(newFLow);
        saveFlowStore(
          newFLow,
          data.tags.map((tag) => tag.id)
        )
          .then(() => {
            setAdded(true);
            setLoading(false);
            setSuccessData({ title: "Component Added to account" });
          })
          .catch((error) => {
            console.error(error);
            setErrorData({
              title: "Error on adding Component",
              list: [error["response"]["data"]["detail"]],
            });
          });
      },
      (error) => {
        console.log(error);
      }
    );
  }

  function handleLike() {
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
          console.error(error);
          setLiked_by_user(temp);
          setLikes_count(tempNum);
          setErrorData({
            title: "Error on liking component",
            list: [error["response"]["data"]["detail"]],
          });
        })
        .then((response) => {
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
              <span className="flex w-full items-center gap-2 word-break-break-word">
                {data.name}
              </span>
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
                  variant="ghost"
                  size="xs"
                  className={
                    "whitespace-nowrap" +
                    (!authorized ? " cursor-not-allowed" : "")
                  }
                  onClick={() => {
                    if (authorized) handleLike();
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
                      ? "Added to Account"
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
                    }
                  }}
                >
                  <IconComponent
                    name={loading ? "Loader2" : added ? "Check" : "Plus"}
                    className={classNames(
                      "h-6 w-6",
                      added ? "text-chat-send" : "",
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
