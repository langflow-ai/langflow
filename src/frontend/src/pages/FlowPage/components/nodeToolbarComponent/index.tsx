import { useUpdateNodeInternals } from "@xyflow/react";
import _, { cloneDeep } from "lodash";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { usePostRetrieveVertexOrder } from "@/controllers/API/queries/vertex";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import useAddFlow from "@/hooks/flows/use-add-flow";
import type { APIClassType } from "@/types/api";
import useAlertStore from "../../../../stores/alertStore";
import { useDarkStore } from "../../../../stores/darkStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useStoreStore } from "../../../../stores/storeStore";
import { useUtilityStore } from "../../../../stores/utilityStore";
import type { nodeToolbarPropsType } from "../../../../types/components";
import type { FlowType } from "../../../../types/flow";
import {
  createFlowComponent,
  downloadNode,
  expandGroupNode,
  updateFlowPosition,
} from "../../../../utils/reactflowUtils";
import { ToolbarButtonRow } from "./components/ToolbarButtonRow";
import { ToolbarMoreMenu } from "./components/ToolbarMoreMenu";
import ToolbarModals from "./components/toolbar-modals";
import {
  buildToolbarActionMap,
  type ToolbarActionEvent,
} from "./helpers/build-toolbar-action-map";
import useShortcuts from "./hooks/use-shortcuts";
import { useToolbarNodeState } from "./hooks/use-toolbar-node-state";

const NodeToolbarComponent = memo(
  ({
    data,
    deleteNode,
    setShowNode,
    numberOfOutputHandles,
    showNode,
    name = "code",
    updateNode,
    isOutdated,
    isUserEdited,
    hasBreakingChange,
    setOpenShowMoreOptions,
    openDropdownOnRightClick = false,
  }: nodeToolbarPropsType & {
    openDropdownOnRightClick?: boolean;
  }): JSX.Element => {
    const { t } = useTranslation();
    const version = useDarkStore((state) => state.version);
    const [showconfirmShare, setShowconfirmShare] = useState(false);
    const [showOverrideModal, setShowOverrideModal] = useState(false);
    const [flowComponent, setFlowComponent] = useState<FlowType>(
      createFlowComponent(cloneDeep(data), version),
    );
    const updateFreezeStatus = useFlowStore(
      (state) => state.updateFreezeStatus,
    );
    const { hasStore, hasApiKey, validApiKey } = useStoreStore((state) => ({
      hasStore: state.hasStore,
      hasApiKey: state.hasApiKey,
      validApiKey: state.validApiKey,
    }));
    const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
    const [openModal, setOpenModal] = useState(false);
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const frozen = data.node?.frozen ?? false;
    const updateNodeInternals = useUpdateNodeInternals();

    const paste = useFlowStore((state) => state.paste);
    const setNodes = useFlowStore((state) => state.setNodes);
    const setEdges = useFlowStore((state) => state.setEdges);
    const getNodePosition = useFlowStore((state) => state.getNodePosition);
    const flows = useFlowsManagerStore((state) => state.flows);
    const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
    const { mutate: FreezeAllVertices } = usePostRetrieveVertexOrder({
      onSuccess: ({ vertices_to_run }) => {
        updateFreezeStatus(vertices_to_run, !data.node?.frozen);
        vertices_to_run.forEach((vertex) => {
          updateNodeInternals(vertex);
        });
      },
    });

    const freezeAllVertices = useCallback(() => {
      const { nodes, edges } = useFlowStore.getState();
      FreezeAllVertices({
        flowId: currentFlowId,
        data: { nodes, edges },
        stopNodeId: data.id,
      });
    }, [FreezeAllVertices, currentFlowId, data.id]);

    const postToolModeValue = usePostTemplateValue({
      node: data.node!,
      nodeId: data.id,
      parameterId: "tool_mode",
    });

    const isSaved = flows?.some((flow) =>
      Object.values(flow).includes(data.node?.display_name!),
    );

    const allowCustomComponents = useUtilityStore(
      (state) => state.allowCustomComponents,
    );

    const {
      hasCode,
      canEditCode,
      isGroup,
      hasToolMode,
      toolMode,
      setToolMode,
    } = useToolbarNodeState({
      data,
      allowCustomComponents,
      isPostToolModePending: postToolModeValue.isPending,
    });
    const addFlow = useAddFlow();

    const { handleNodeClass: handleNodeClassHook } = useHandleNodeClass(
      data.id,
    );

    const handleNodeClass = (newNodeClass: APIClassType, type: string) => {
      handleNodeClassHook(newNodeClass, type);
    };

    const handleActivateToolMode = () => {
      const newValue = !toolMode;
      setToolMode(newValue);
      mutateTemplate(
        newValue,
        data.id,
        data.node!,
        handleNodeClass,
        postToolModeValue,
        setErrorData,
        "tool_mode",
        () => updateNodeInternals(data.id),
        newValue,
      );
    };

    // LE-1810: any component can be minimized, regardless of how many
    // input/output handles it has.
    const handleMinimize = useCallback(() => {
      setShowNode(!showNode);
      updateNodeInternals(data.id);
    }, [showNode, data.id]);

    const handleungroup = useCallback(() => {
      if (isGroup) {
        takeSnapshot();
        expandGroupNode(
          data.id,
          updateFlowPosition(getNodePosition(data.id), data.node?.flow!),
          data.node!.template,
          setNodes,
          setEdges,
          data.node?.outputs,
        );
      }
    }, [
      isGroup,
      data.id,
      data.node?.flow,
      data.node?.template,
      data.node?.outputs,
      setNodes,
      setEdges,
      takeSnapshot,
      getNodePosition,
      updateFlowPosition,
      expandGroupNode,
    ]);

    const shareComponent = useCallback(() => {
      if (hasApiKey || hasStore) {
        setShowconfirmShare((state) => !state);
      }
    }, [hasApiKey, hasStore]);

    const handleCodeModal = useCallback(() => {
      if (!hasCode) {
        setNoticeData({ title: t("node.cannotAccessCode", { id: data.id }) });
        return;
      }
      if (!allowCustomComponents) {
        setNoticeData({ title: t("node.customComponentEditingDisabled") });
        return;
      }
      setOpenModal((state) => !state);
    }, [hasCode, allowCustomComponents, data.id]);

    const saveComponent = useCallback(() => {
      if (isSaved) {
        setShowOverrideModal((state) => !state);
        return;
      }
      addFlow({
        flow: flowComponent,
        override: false,
      });
      setSuccessData({ title: t("success.componentSaved", { id: data.id }) });
    }, [isSaved, data.id, flowComponent, addFlow]);

    const openDocs = useCallback(() => {
      if (data.node?.documentation) {
        return customOpenNewTab(data.node.documentation);
      }
      setNoticeData({ title: t("node.docsUnavailable", { id: data.id }) });
    }, [data.id, data.node?.documentation]);

    const handleDownloadNode = useCallback(async () => {
      try {
        await downloadNode(flowComponent!);
        setSuccessData({
          title: t("node.downloadSuccess", {
            name: flowComponent?.name || "Node",
          }),
        });
      } catch (error) {
        console.error("Error downloading node:", error);
        const nodeName = flowComponent?.name || "Node";
        setErrorData({
          title: t("node.downloadFailed", { name: nodeName }),
          list: [
            error instanceof Error
              ? error.message
              : t("node.downloadUnknownError"),
          ],
        });
      }
    }, [flowComponent]);

    const inspectionPanelVisible = useFlowStore(
      (state) => state.inspectionPanelVisible,
    );
    const setInspectionPanelVisible = useFlowStore(
      (state) => state.setInspectionPanelVisible,
    );

    const handleToggleInspectionPanel = useCallback(() => {
      setInspectionPanelVisible(!inspectionPanelVisible);
    }, [inspectionPanelVisible, setInspectionPanelVisible]);

    useShortcuts({
      showOverrideModal,
      advancedSurfaceOpen: inspectionPanelVisible,
      openModal,
      showconfirmShare,
      FreezeAllVertices: freezeAllVertices,
      downloadFunction: () => downloadNode(flowComponent!),
      displayDocs: openDocs,
      saveComponent,
      showAdvance: handleToggleInspectionPanel,
      handleCodeModal,
      shareComponent,
      ungroup: handleungroup,
      minimizeFunction: handleMinimize,
      activateToolMode: handleActivateToolMode,
      hasToolMode,
    });

    // Open dropdown when right-clicked
    useEffect(() => {
      if (openDropdownOnRightClick) {
        setDropdownOpen(true);
      } else {
        setDropdownOpen(false);
      }
    }, [openDropdownOnRightClick]);

    const setLastCopiedSelection = useFlowStore(
      (state) => state.setLastCopiedSelection,
    );

    const setSuccessData = useAlertStore((state) => state.setSuccessData);
    const setNoticeData = useAlertStore((state) => state.setNoticeData);
    const setErrorData = useAlertStore((state) => state.setErrorData);

    useEffect(() => {
      setFlowComponent(createFlowComponent(cloneDeep(data), version));
    }, [
      data,
      data.node,
      data.node?.display_name,
      data.node?.description,
      data.node?.template,
      showconfirmShare,
    ]);

    const [selectedValue, setSelectedValue] = useState<string | null>(null);

    const toolbarActionMap = useMemo(
      () =>
        buildToolbarActionMap({
          save: saveComponent,
          freezeAll: () => {
            takeSnapshot();
            freezeAllVertices();
          },
          code: handleCodeModal,
          show: () => {
            takeSnapshot();
            handleMinimize();
          },
          share: shareComponent,
          download: handleDownloadNode,
          saveAll: () => addFlow({ flow: flowComponent, override: false }),
          documentation: openDocs,
          ungroup: handleungroup,
          override: () => setShowOverrideModal(true),
          delete: () => deleteNode(data.id),
          update: updateNode,
          copy: () => {
            const nodes = useFlowStore.getState().nodes;
            const node = nodes.filter((node) => node.id === data.id);
            setLastCopiedSelection({ nodes: _.cloneDeep(node), edges: [] });
          },
          duplicate: () => {
            const nodes = useFlowStore.getState().nodes;
            paste(
              {
                nodes: [nodes.find((node) => node.id === data.id)!],
                edges: [],
              },
              {
                x: 50,
                y: 10,
                paneX: nodes.find((node) => node.id === data.id)?.position.x,
                paneY: nodes.find((node) => node.id === data.id)?.position.y,
              },
            );
          },
          toolMode: handleActivateToolMode,
        }),
      [
        saveComponent,
        takeSnapshot,
        freezeAllVertices,
        handleCodeModal,
        handleMinimize,
        shareComponent,
        handleDownloadNode,
        addFlow,
        flowComponent,
        openDocs,
        handleungroup,
        setShowOverrideModal,
        deleteNode,
        updateNode,
        setLastCopiedSelection,
        paste,
        handleActivateToolMode,
      ],
    );

    const handleSelectChange = useCallback(
      (event: string) => {
        setSelectedValue(event);

        // Clear right-clicked state when user selects an option
        if (openDropdownOnRightClick) {
          const setRightClickedNodeId =
            useFlowStore.getState().setRightClickedNodeId;
          setRightClickedNodeId(null);
        }

        toolbarActionMap[event as ToolbarActionEvent]?.();

        setSelectedValue(null);
      },
      [toolbarActionMap, openDropdownOnRightClick],
    );

    const { handleOnNewValue: handleOnNewValueHook } = useHandleOnNewValue({
      node: data.node!,
      nodeId: data.id,
      name,
    });

    const handleOnNewValue = (value: string | string[]) => {
      handleOnNewValueHook({ value });
    };

    const selectTriggerRef = useRef(null);

    const handleButtonClick = () => {
      (selectTriggerRef.current! as HTMLElement)?.click();
    };

    const handleOpenChange = (open: boolean) => {
      setOpenShowMoreOptions && setOpenShowMoreOptions(open);
      setDropdownOpen(open);

      // Clear right-clicked state when dropdown closes without selection
      if (!open && openDropdownOnRightClick) {
        const setRightClickedNodeId =
          useFlowStore.getState().setRightClickedNodeId;
        setRightClickedNodeId(null);
      }
    };

    const isCustomComponent = useMemo(() => {
      const isCustom = data.type === "CustomComponent" && !data.node?.edited;
      if (isCustom && !inspectionPanelVisible) {
        data.node.edited = true;
      }
      return isCustom;
    }, [data.type, data.node]);

    return (
      <>
        <div className="noflow nopan nodelete nodrag">
          <div className="toolbar-wrapper">
            <ToolbarButtonRow
              canEditCode={canEditCode}
              isCustomComponent={isCustomComponent}
              onCode={handleCodeModal}
              onToggleInspectionPanel={handleToggleInspectionPanel}
              inspectionPanelVisible={inspectionPanelVisible}
              hasToolMode={hasToolMode}
              frozen={frozen}
              onFreeze={() => {
                takeSnapshot();
                freezeAllVertices();
              }}
              toolMode={toolMode}
              onToolMode={() => {
                takeSnapshot();
                handleSelectChange("toolMode");
              }}
            />
            <ToolbarMoreMenu
              onSelect={handleSelectChange}
              selectedValue={selectedValue}
              onOpenChange={handleOpenChange}
              open={dropdownOpen}
              onTriggerClick={handleButtonClick}
              isOutdated={isOutdated}
              hasBreakingChange={hasBreakingChange}
              isUserEdited={isUserEdited}
              hasStore={hasStore}
              hasApiKey={hasApiKey}
              validApiKey={validApiKey}
              documentation={data.node?.documentation}
              showNode={showNode}
              isGroup={isGroup}
              hasToolMode={hasToolMode}
              frozen={frozen}
            />
          </div>

          <ToolbarModals
            showconfirmShare={showconfirmShare}
            showOverrideModal={showOverrideModal}
            openModal={openModal}
            hasCode={hasCode}
            setShowconfirmShare={setShowconfirmShare}
            setShowOverrideModal={setShowOverrideModal}
            setOpenModal={setOpenModal}
            data={data}
            flowComponent={flowComponent}
            handleOnNewValue={handleOnNewValue}
            handleNodeClass={handleNodeClass}
            setToolMode={setToolMode}
            setSuccessData={setSuccessData}
            addFlow={addFlow}
            name={name}
          />
        </div>
      </>
    );
  },
);

NodeToolbarComponent.displayName = "NodeToolbarComponent";

export default NodeToolbarComponent;
