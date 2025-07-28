import { useEffect, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { getSpecificClassFromBuildStatus } from "@/CustomNodes/helpers/get-class-from-build-status";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useIconStatus from "@/CustomNodes/hooks/use-icons-status";
import useUpdateValidationStatus from "@/CustomNodes/hooks/use-update-validation-status";
import useValidationStatusString from "@/CustomNodes/hooks/use-validation-status-string";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { BuildStatus } from "@/constants/enums";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { track } from "@/customization/utils/analytics";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import useAlertStore from "@/stores/alertStore";
import { useDarkStore } from "@/stores/darkStore";
import useFlowStore from "@/stores/flowStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { useUtilityStore } from "@/stores/utilityStore";
import type { VertexBuildTypeAPI } from "@/types/api";
import type { NodeDataType } from "@/types/flow";
import { findLastNode } from "@/utils/reactflowUtils";
import { classNames, cn } from "@/utils/utils";
import IconComponent from "../../../../components/common/genericIconComponent";
import BuildStatusDisplay from "./components/build-status-display";
import { normalizeTimeString } from "./utils/format-run-time";

const POLLING_TIMEOUT = 21000;
const POLLING_INTERVAL = 3000;

export default function NodeStatus({
  nodeId,
  display_name,
  selected,
  setBorderColor,
  frozen,
  showNode,
  data,
  buildStatus,
  dismissAll,
  isOutdated,
  isUserEdited,
  isBreakingChange,
  getValidationStatus,
}: {
  nodeId: string;
  display_name: string;
  selected?: boolean;
  setBorderColor: (color: string) => void;
  frozen?: boolean;
  showNode: boolean;
  data: NodeDataType;
  buildStatus: BuildStatus;
  dismissAll: boolean;
  isOutdated: boolean;
  isUserEdited: boolean;
  isBreakingChange: boolean;
  getValidationStatus: (data) => VertexBuildTypeAPI | null;
}) {
  const nodeId_ = data.node?.flow?.data
    ? (findLastNode(data.node?.flow.data!)?.id ?? nodeId)
    : nodeId;
  const [validationString, setValidationString] = useState<string>("");
  const [validationStatus, setValidationStatus] =
    useState<VertexBuildTypeAPI | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const nodeAuth = Object.values(data.node?.template ?? {}).find(
    (value) => value.type === "auth",
  );

  const connectionLink = nodeAuth?.value;
  const isAuthenticated = nodeAuth?.value === "validated";

  const pollingInterval = useRef<NodeJS.Timeout | null>(null);
  const pollingTimeout = useRef<NodeJS.Timeout | null>(null);

  const conditionSuccess =
    buildStatus === BuildStatus.BUILT ||
    (buildStatus !== BuildStatus.TO_BUILD && validationStatus?.valid);

  const conditionError = buildStatus === BuildStatus.ERROR;
  const conditionInactive = buildStatus === BuildStatus.INACTIVE;

  const showNodeStatus =
    conditionSuccess || conditionError || conditionInactive;

  const lastRunTime = useFlowStore(
    (state) => state.flowBuildStatus[nodeId_]?.timestamp,
  );
  const iconStatus = useIconStatus(buildStatus);
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const setNode = useFlowStore((state) => state.setNode);
  const version = useDarkStore((state) => state.version);
  const eventDeliveryConfig = useUtilityStore((state) => state.eventDelivery);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const postTemplateValue = usePostTemplateValue({
    parameterId: nodeAuth?.name ?? "auth",
    nodeId: nodeId,
    node: data.node,
  });

  // Start polling when connection is initiated
  const startPolling = () => {
    stopPolling();
    setIsPolling(true);

    mutateTemplate(
      { validate: "" },
      data.id,
      data.node,
      (newNode) => {
        setNode(nodeId, (old) => ({
          ...old,
          data: { ...old.data, node: newNode },
        }));

        const updatedAuth = Object.values(newNode?.template ?? {}).find(
          (value: any) => value?.type === "auth",
        ) as any;
        const oauthUrl = updatedAuth?.value;

        if (
          oauthUrl &&
          typeof oauthUrl === "string" &&
          oauthUrl.startsWith("http")
        ) {
          customOpenNewTab(oauthUrl);
        }
      },
      postTemplateValue,
      setErrorData,
      nodeAuth?.name ?? "auth_link",
      () => {
        pollingInterval.current = setInterval(() => {
          mutateTemplate(
            { validate: data.node?.template?.auth?.value || "" },
            data.id,
            data.node,
            (newNode) => {
              setNode(nodeId, (old) => ({
                ...old,
                data: { ...old.data, node: newNode },
              }));
            },
            postTemplateValue,
            setErrorData,
            nodeAuth?.name ?? "auth_link",
            () => {},
            data.node.tool_mode,
          );
        }, POLLING_INTERVAL);

        pollingTimeout.current = setTimeout(() => {
          stopPolling();
        }, POLLING_TIMEOUT);
      },
      data.node.tool_mode,
    );
  };

  useEffect(() => {
    if (isAuthenticated) {
      stopPolling();
    }
  }, [isAuthenticated]);

  const handleDisconnect = () => {
    setIsPolling(true);
    mutateTemplate(
      "disconnect",
      data.id,
      data.node,
      (newNode) => {
        setNode(nodeId, (old) => ({
          ...old,
          data: { ...old.data, node: newNode },
        }));
      },
      postTemplateValue,
      setErrorData,
      nodeAuth?.name ?? "auth_link",
      () => {
        setIsPolling(false);
      },
      data.node.tool_mode,
    );
  };

  const stopPolling = () => {
    setIsPolling(false);

    if (pollingInterval.current) clearInterval(pollingInterval.current);
    if (pollingTimeout.current) clearTimeout(pollingTimeout.current);
  };

  function handlePlayWShortcut() {
    if (buildStatus === BuildStatus.BUILDING || isBuilding || !selected) return;
    setValidationStatus(null);
    buildFlow({
      stopNodeId: nodeId,
      eventDelivery: eventDeliveryConfig,
    });
  }

  const play = useShortcutsStore((state) => state.play);
  const flowPool = useFlowStore((state) => state.flowPool);
  useHotkeys(play, handlePlayWShortcut, { preventDefault: true });
  useValidationStatusString(validationStatus, setValidationString);
  useUpdateValidationStatus(
    nodeId_,
    flowPool,
    setValidationStatus,
    getValidationStatus,
  );

  const getBaseBorderClass = (selected) => {
    const className =
      selected && !isBuilding
        ? " border ring-[0.75px] ring-muted-foreground border-muted-foreground hover:shadow-node"
        : "border ring-[0.5px] hover:shadow-node ring-border";
    const frozenClass = selected ? "border-ring-frozen" : "border-frozen";
    const updateClass =
      isOutdated && !isUserEdited && !dismissAll && isBreakingChange
        ? "border-warning"
        : "";
    return cn(frozen ? frozenClass : className, updateClass);
  };

  const getNodeBorderClassName = (
    selected: boolean | undefined,
    buildStatus: BuildStatus | undefined,
    validationStatus: VertexBuildTypeAPI | null,
  ) => {
    const specificClassFromBuildStatus = getSpecificClassFromBuildStatus(
      buildStatus,
      validationStatus,
      isBuilding,
    );

    const baseBorderClass = getBaseBorderClass(selected);
    const names = classNames(baseBorderClass, specificClassFromBuildStatus);
    return names;
  };

  useEffect(() => {
    setBorderColor(
      getNodeBorderClassName(selected, buildStatus, validationStatus),
    );
  }, [
    selected,
    showNode,
    buildStatus,
    validationStatus,
    isOutdated,
    isUserEdited,
    frozen,
    dismissAll,
  ]);

  useEffect(() => {
    if (buildStatus === BuildStatus.BUILT && !isBuilding) {
      setNode(
        nodeId,
        (old) => {
          return {
            ...old,
            data: {
              ...old.data,
              node: {
                ...old.data.node,
                lf_version: version,
              },
            },
          };
        },
        false,
      );
    }
  }, [buildStatus, isBuilding]);

  const [isHovered, setIsHovered] = useState(false);

  const stopBuilding = useFlowStore((state) => state.stopBuilding);

  const handleClickRun = () => {
    if (BuildStatus.BUILDING === buildStatus && isHovered) {
      stopBuilding();
      return;
    }
    if (buildStatus === BuildStatus.BUILDING || isBuilding) return;
    buildFlow({
      stopNodeId: nodeId,
      eventDelivery: eventDeliveryConfig,
    });
    track("Flow Build - Clicked", { stopNodeId: nodeId });
  };

  const iconName =
    BuildStatus.BUILDING === buildStatus
      ? isHovered
        ? "Square"
        : "Loader2"
      : "Play";

  const iconClasses = cn(
    "h-3.5 w-3.5 transition-all group-hover/node:opacity-100",
    isHovered ? "text-foreground" : "text-muted-foreground",
    BuildStatus.BUILDING === buildStatus &&
      (isHovered ? "text-status-red" : "animate-spin"),
  );

  const getTooltipContent = () => {
    if (BuildStatus.BUILDING === buildStatus && isHovered) {
      return "Stop build";
    }
    return "Run component";
  };

  const handleClickConnect = () => {
    if (connectionLink === "error") return;
    if (isAuthenticated) {
      handleDisconnect();
    } else {
      startPolling();
    }
  };

  const getConnectionButtonClasses: (
    connectionLink: string,
    isAuthenticated: boolean,
    isPolling: boolean,
  ) => string = (
    connectionLink: string,
    isAuthenticated: boolean,
    isPolling: boolean,
  ): string => {
    return cn(
      "nodrag button-run-bg group relative h-4 w-4 p-0.5 rounded-sm border border-accent-amber-foreground transition-colors hover:bg-accent-amber",
      connectionLink === "error"
        ? "border-destructive text-destructive"
        : isAuthenticated && !isPolling
          ? "border-accent-emerald-foreground hover:border-accent-amber-foreground"
          : "",
      connectionLink === "" && "cursor-not-allowed opacity-50",
    );
  };

  const getConnectionIconClasses: (
    connectionLink: string,
    isAuthenticated: boolean,
    isPolling: boolean,
  ) => string = (
    connectionLink: string,
    isAuthenticated: boolean,
    isPolling: boolean,
  ): string => {
    return cn(
      "transition-opacity h-2.5 w-2.5",
      connectionLink === "error"
        ? "text-destructive"
        : isAuthenticated && !isPolling
          ? "text-accent-emerald-foreground"
          : "text-accent-amber-foreground",
      isPolling && "animate-spin",
      isAuthenticated && !isPolling ? "group-hover:opacity-0" : "",
    );
  };

  const getDataTestId = () => {
    if (isAuthenticated && !isPolling) {
      return `button_connected_${display_name.toLowerCase()}`;
    }
    if (connectionLink === "error") {
      return `button_error_${display_name.toLowerCase()}`;
    }
    return `button_disconnected_${display_name.toLowerCase()}`;
  };

  return (
    <div className="flex shrink-0 items-center gap-2">
      {(showNodeStatus || nodeAuth) && (
        <div className="flex items-center gap-2 self-center">
          {showNodeStatus && (
            <ShadTooltip
              styleClasses={cn(
                "border rounded-xl",
                conditionSuccess
                  ? "border-accent-emerald-foreground bg-success-background"
                  : "border-destructive bg-error-background",
              )}
              content={
                <BuildStatusDisplay
                  buildStatus={buildStatus}
                  validationStatus={validationStatus}
                  validationString={validationString}
                  lastRunTime={lastRunTime}
                />
              }
              side="bottom"
            >
              <div className="cursor-help">
                {conditionSuccess && validationStatus?.data?.duration ? (
                  <div className="flex rounded-sm px-1 font-mono text-xs text-accent-emerald-foreground transition-colors hover:bg-accent-emerald">
                    <span>
                      {normalizeTimeString(validationStatus?.data?.duration)}
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center self-center">
                    {iconStatus}
                  </div>
                )}
              </div>
            </ShadTooltip>
          )}

          {nodeAuth && showNode && (
            <ShadTooltip content={nodeAuth.auth_tooltip || "Connect"}>
              <div>
                <Button
                  unstyled
                  disabled={connectionLink === "" || connectionLink === "error"}
                  className={getConnectionButtonClasses(
                    connectionLink,
                    isAuthenticated,
                    isPolling,
                  )}
                  onClick={handleClickConnect}
                  data-testid={getDataTestId()}
                >
                  <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                    <IconComponent
                      name={
                        isPolling
                          ? "Loader2"
                          : isAuthenticated
                            ? "Link"
                            : "AlertTriangle"
                      }
                      className={getConnectionIconClasses(
                        connectionLink,
                        isAuthenticated,
                        isPolling,
                      )}
                      strokeWidth={ICON_STROKE_WIDTH}
                    />
                  </div>
                  <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                    <IconComponent
                      name={"Unlink"}
                      className={cn(
                        "h-2.5 w-2.5 text-accent-amber-foreground opacity-0 transition-opacity",
                        isAuthenticated && !isPolling
                          ? "group-hover:opacity-100"
                          : "",
                      )}
                      strokeWidth={ICON_STROKE_WIDTH}
                    />
                  </div>
                </Button>
              </div>
            </ShadTooltip>
          )}
        </div>
      )}
      {showNode && (
        <ShadTooltip content={getTooltipContent()}>
          <div
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            onClick={handleClickRun}
            className="-m-0.5"
          >
            <Button unstyled className="nodrag button-run-bg group">
              <div data-testid={`button_run_` + display_name.toLowerCase()}>
                <IconComponent
                  name={iconName}
                  className={iconClasses}
                  strokeWidth={ICON_STROKE_WIDTH}
                />
              </div>
            </Button>
          </div>
        </ShadTooltip>
      )}
    </div>
  );
}
