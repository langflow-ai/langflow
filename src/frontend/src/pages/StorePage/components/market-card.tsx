import { useContext, useEffect, useRef, useState } from "react";
import ShadTooltip from "../../../components/ShadTooltipComponent";
import IconComponent from "../../../components/genericIconComponent";
import ElementStack from "../../../components/stackedComponents";
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
import { getComponent, saveFlowStore } from "../../../controllers/API";
import { FlowType } from "../../../types/flow";
import { storeComponent } from "../../../types/store";
import cloneFLowWithParent from "../../../utils/storeUtils";

export const MarketCardComponent = ({ data }: { data: storeComponent }) => {
  const { savedFlows } = useContext(StoreContext);
  const [added, setAdded] = useState(savedFlows.has(data.id) ? true : false);
  const [loading, setLoading] = useState(false);
  const { addFlow } = useContext(TabsContext);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const flowData = useRef<FlowType>();

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

  function handleInstall() {
    if (flowData.current) {
      addFlow(true, flowData.current!).then(() => {
        setSuccessData({ title: "Flow Installed" });
      });
    } else {
      getComponent(data.id).then((res) => {
        const newFLow = cloneFLowWithParent(res, res.id, data.is_component);
        flowData.current = newFLow;
        addFlow(true, newFLow);
        setSuccessData({ title: "Flow Installed" });
      });
    }
  }

  const totalComponentsMetadata = () => {
    return data?.metadata ? data.metadata["total"] : 0;
  };

  return (
    <Card className="group relative flex flex-col justify-between overflow-hidden transition-all hover:shadow-md">
      <div>
        <CardHeader>
          <div>
            <CardTitle className="flex w-full items-center justify-between gap-3 text-xl">
              <span className="flex w-full items-center gap-2 word-break-break-word">
                {data.name}
              </span>
              <Badge size="sm" variant="gray">
                Free
              </Badge>
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
            <div className=" flex items-center gap-3">
              <ShadTooltip
                styleClasses="bg-transparent border-none shadow-none"
                side="right"
                content={
                  <div className="flex flex-wrap gap-1">
                    {data.tags
                      .sort((a, b) => a.name.length - b.name.length)
                      .map((tag, index) => (
                        <div className="">
                          <Badge
                            key={index}
                            className="bg-card shadow-md"
                            size="sm"
                            variant="outline"
                          >
                            {tag.name}
                          </Badge>
                        </div>
                      ))}
                  </div>
                }
              >
                <div className="pr-2 hover:opacity-40">
                  {data.tags.length > 0 ? (
                    <ElementStack>
                      {data.tags.map((tag, index) => (
                        <Badge
                          key={index}
                          size="md"
                          className="bg-card"
                          variant="outline"
                        >
                          {tag.name}
                        </Badge>
                      ))}
                    </ElementStack>
                  ) : (
                    <Badge size="md" variant="outline">
                      -
                    </Badge>
                  )}
                </div>
              </ShadTooltip>
              <ShadTooltip content="Components">
                <span className="flex items-center gap-1.5 text-xs text-foreground">
                  <IconComponent name="ToyBrick" className="h-4 w-4" />
                  {totalComponentsMetadata()}
                </span>
              </ShadTooltip>
              <ShadTooltip content="Favorites">
                <span className="flex items-center gap-1.5 text-xs text-foreground">
                  <IconComponent name="Heart" className="h-4 w-4" />
                  {data.liked_by_count ?? 0}
                </span>
              </ShadTooltip>
              <ShadTooltip content="Downloads">
                <span className="flex items-center gap-1.5 text-xs text-foreground">
                  <IconComponent name="DownloadCloud" className="h-4 w-4" />
                  {data.downloads_count}
                </span>
              </ShadTooltip>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="whitespace-nowrap "
              onClick={() => {
                if (loading) {
                  return;
                }
                if (!added) {
                  handleAdd();
                } else {
                  handleInstall();
                }
              }}
            >
              <IconComponent
                name={
                  loading ? "Loader2" : added ? "GitBranchPlus" : "BookmarkPlus"
                }
                className={
                  "main-page-nav-button" + (loading ? " animate-spin" : "")
                }
              />
              {added ? "Install Localy" : "Add to Account"}
            </Button>
          </div>
        </div>
      </CardFooter>
    </Card>
  );
};
