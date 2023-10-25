import { Link, ToyBrick } from "lucide-react";
import { useContext, useEffect, useRef, useState } from "react";
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
import { StoreContext } from "../../../contexts/storeContext";
import { TabsContext } from "../../../contexts/tabsContext";
import { getComponent, saveFlowStore } from "../../../controllers/API";
import { FlowType } from "../../../types/flow";
import { FlowComponent } from "../../../types/store";
import cloneFLowWithParent from "../../../utils/storeUtils";

export const MarketCardComponent = ({ data }: { data: FlowComponent }) => {
  const { savedFlows } = useContext(StoreContext);
  const [added, setAdded] = useState(savedFlows.has(data.id) ? true : false);
  const [loading, setLoading] = useState(false);
  const { addFlow } = useContext(TabsContext);
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
        saveFlowStore(newFLow)
          .then(() => {
            setAdded(true);
            setLoading(false);
          })
          .catch((error) => {
            console.error(error);
          });
      },
      (error) => {
        console.log(error);
      }
    );
  }

  function handleInstall() {
    if (flowData.current) {
      addFlow(true, flowData.current!);
    } else {
      getComponent(data.id).then((res) => {
        console.log(res);
        const newFLow = cloneFLowWithParent(res, res.id, data.is_component);
        flowData.current = newFLow;
        addFlow(true, newFLow);
      });
    }
  }

  function handleFork(flowId: string, is_component: boolean) {
    getComponent(flowId).then(
      (res) => {
        console.log(res);
        const newFLow = cloneFLowWithParent(res.data, res.id, is_component);
        console.log(newFLow);
        saveFlowStore(newFLow).then(
          (res) => {
            console.log(JSON.parse(JSON.stringify(res)));
            addFlow(true, newFLow);
          },
          (error) => {
            console.error(error);
          }
        );
      },
      (error) => {
        console.log(error);
      }
    );
  }

  return (
    <Card className="group relative flex cursor-pointer flex-col justify-between overflow-hidden transition-all hover:shadow-md">
      <div>
        <CardHeader>
          {/*
          <div className="mb-2 flex flex-wrap gap-1">
            {data.tags.map((tag) => (
              <Badge
                size="sm"
                className={
                  tagGradients[parseInt(tag, 35) % tagGradients.length] +
                  " " +
                  tagText[parseInt(tag, 35) % tagText.length]
                }
              >
                {tag}
              </Badge>
            ))}
          </div> */}
          <div>
            <CardTitle className="flex w-full items-center justify-between gap-3 text-xl">
              <span className="flex w-full items-center gap-2 word-break-break-word">
                {data.name}
              </span>
              <Badge size="sm" variant="gray">
                Free
              </Badge>
            </CardTitle>
            {/* <span className="inline-flex items-center text-sm">
              <img
                className="mr-2 h-4 w-4 rounded-full"
                src={data.image}
              />
              {data.creator.name}
            </span>
            <span className="flex text-xs items-center gap-2 text-ring">
              <Download className="h-3 w-3" />
              {nFormatter(data.downloads, 2)}
            </span> */}
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
              <Badge size="md" variant="outline">
                chain
                <Link className="ml-1.5 w-3 text-green-700" />
              </Badge>
              <span className="flex items-center gap-1.5 text-xs text-foreground">
                <ToyBrick className="h-4 w-4" />
                123
              </span>
            </div>
            {/* {data.isChat ? (
              <Button size="sm" variant="outline">
                <Plus className="h-4 mr-2" />
                Add
              </Button>
            ) : (
              <Button size="sm" variant="success">
                <Check className="h-4 mr-2" />
                Added
              </Button>
            )} */}
            <Button
              variant="outline"
              size="sm"
              className="whitespace-nowrap "
              onClick={() => {
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
