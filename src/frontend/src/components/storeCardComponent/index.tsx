import { usePostLikeComponent } from "@/controllers/API/queries/store";
import { ENABLE_NEW_IO_MODAL } from "@/customization/feature-flags";
import { useState } from "react";
import { getComponent } from "../../controllers/API";
import IOModalOld from "../../modals/IOModal";
import IOModalNew from "../../modals/IOModal/newModal";
import useAlertStore from "../../stores/alertStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useStoreStore } from "../../stores/storeStore";
import { FlowType } from "../../types/flow";
import { storeComponent } from "../../types/store";
import cloneFLowWithParent, {
  getInputsAndOutputs,
} from "../../utils/storeUtils";
import { cn } from "../../utils/utils";
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
import useDataEffect from "./hooks/use-data-effect";
import useInstallComponent from "./hooks/use-handle-install";
import { convertTestName } from "./utils/convert-test-name";
const IOModal = ENABLE_NEW_IO_MODAL ? IOModalNew : IOModalOld;

export default function StoreCardComponent({
  data,
  authorized = true,
  disabled = false,
}: {
  data: storeComponent;
  authorized?: boolean;
  disabled?: boolean;
}) {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setValidApiKey = useStoreStore((state) => state.updateValidApiKey);
  const [loading, setLoading] = useState(false);
  const [likedByUser, setLikedByUser] = useState(data?.liked_by_user ?? false);
  const [likesCount, setLikesCount] = useState(data?.liked_by_count ?? 0);
  const [downloadsCount, setDownloadsCount] = useState(
    data?.downloads_count ?? 0,
  );
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  // const [openPlayground, setOpenPlayground] = useState(false);
  const [loadingPlayground, setLoadingPlayground] = useState(false);
  const playground =
    data.last_tested_version?.includes("1.0.0") && !data.is_component;

  const name = data.is_component ? "Component" : "Flow";

  async function getFlowData() {
    const res = await getComponent(data.id);
    const newFlow = cloneFLowWithParent(res, res.id, data.is_component, true);
    return newFlow;
  }

  function hasPlayground(flow?: FlowType) {
    if (!flow) {
      return false;
    }
    const { inputs, outputs } = getInputsAndOutputs(flow?.data?.nodes ?? []);
    return inputs.length > 0 || outputs.length > 0;
  }

  useDataEffect(data, setLikedByUser, setLikesCount, setDownloadsCount);

  const { handleInstall } = useInstallComponent(
    data,
    name,
    downloadsCount,
    setDownloadsCount,
    setLoading,
    setSuccessData,
    setErrorData,
  );

  const { mutate, isPending } = usePostLikeComponent();

  const handleLikeWMutate = () => {
    if (likedByUser !== undefined || likedByUser !== null) {
      const temp = likedByUser;
      const tempNum = likesCount;
      setLikedByUser((prev) => !prev);
      setLikesCount((prev) => (temp ? prev - 1 : prev + 1));
      mutate(
        { componentId: data.id },
        {
          onSuccess: (res) => {
            setLikesCount(res.data.likes_count);
            setLikedByUser(res.data.liked_by_user);
          },
          onError: (error) => {
            setLikesCount(tempNum);
            setLikedByUser(temp);
            if (error.response.status === 403) {
              return setValidApiKey(false);
            }
            console.error(error);
            setErrorData({
              title: `Error liking ${name}.`,
              list: [error.response.data.detail],
            });
          },
        },
      );
    }
  };

  return (
    <>
      <Card
        data-testid={`card-${convertTestName(data.name)}`}
        //TODO check color schema
        className={cn(
          "group relative flex h-[12rem] flex-col justify-between overflow-hidden",
          !data.is_component &&
            "hover:bg-muted/50 hover:shadow-md hover:dark:bg-[#5f5f5f0e]",
          disabled ? "pointer-events-none opacity-50" : "",
        )}
      >
        <div>
          <CardHeader>
            <div>
              <CardTitle className="flex w-full items-start justify-between gap-3 text-xl">
                <IconComponent
                  className={cn(
                    "visible flex-shrink-0",
                    data.is_component
                      ? "mx-0.5 h-6 w-6 text-component-icon"
                      : "h-7 w-7 flex-shrink-0 text-flow-icon",
                  )}
                  name={data.is_component ? "ToyBrick" : "Group"}
                />

                <ShadTooltip content={data.name}>
                  <div className="w-full truncate pr-3">{data.name}</div>
                </ShadTooltip>
                <div className="flex items-center gap-3">
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
                      <IconComponent name="Heart" className={cn("h-4 w-4")} />
                      <span data-testid={`likes-${data.name}`}>
                        {likesCount ?? 0}
                      </span>
                    </span>
                  </ShadTooltip>
                  <ShadTooltip content="Downloads">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <IconComponent name="DownloadCloud" className="h-4 w-4" />
                      <span data-testid={`downloads-${data.name}`}>
                        {downloadsCount ?? 0}
                      </span>
                    </span>
                  </ShadTooltip>
                </div>
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
              <div className="flex w-full flex-1 flex-wrap gap-2"></div>
            </div>

            <CardDescription className="pb-2 pt-2">
              <div className="truncate-doubleline">{data.description}</div>
            </CardDescription>
          </CardHeader>
        </div>

        <CardFooter>
          <div className="z-50 flex w-full items-center justify-between gap-2">
            <div className="flex w-full flex-wrap items-end justify-end gap-2">
              {/* {playground && (
                <Button
                  disabled={loadingPlayground || !authorized}
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
                    getFlowData().then((res) => {
                      if (!hasPlayground(res)) {
                        setErrorData({
                          title: "Error",
                          list: ["This flow doesn't have a playground."],
                        });
                        setLoadingPlayground(false);
                        return;
                      }
                      setCurrentFlow(res);
                      setOpenPlayground(true);
                      setLoadingPlayground(false);
                    });
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
              )} */}
              <div className="flex gap-0.5">
                <ShadTooltip
                  content={authorized ? "Like" : "Please review your API key."}
                >
                  <Button
                    disabled={isPending}
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
                      handleLikeWMutate();
                    }}
                    data-testid={`like-${data.name}`}
                  >
                    <IconComponent
                      name="Heart"
                      className={cn(
                        "h-5 w-5",
                        likedByUser
                          ? "fill-destructive stroke-destructive"
                          : "",
                        !authorized ? "text-ring" : "",
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
                      name={loading ? "Loader2" : "Plus"}
                      className={cn(
                        loading ? "h-5 w-5 animate-spin" : "h-5 w-5",
                        !authorized ? "text-ring" : "",
                      )}
                    />
                  </Button>
                </ShadTooltip>
              </div>
            </div>
          </div>
        </CardFooter>
      </Card>
      {/* {openPlayground && (
        <IOModal
          key={data.id}
          cleanOnClose={true}
          open={openPlayground}
          setOpen={setOpenPlayground}
        >
          <></>
        </IOModal>
      )} */}
    </>
  );
}
