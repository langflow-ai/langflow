import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { BuildStatus } from "@/constants/enums";
import { useAddMCPServer } from "@/controllers/API/queries/mcp/use-add-mcp-server";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import AddMcpServerModal from "@/modals/addMcpServerModal";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import ListSelectionComponent from "../../../../../CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "../../../../../utils/utils";
import { default as ForwardedIconComponent } from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import type { InputProps } from "../../types";

export type McpServerValue = {
  name: string;
  config?: Record<string, unknown>;
};

type McpSelectionItem = {
  name: string;
  description?: string;
};

export default function McpComponent({
  value,
  disabled,
  handleOnNewValue,
  editNode = false,
  id = "",
  showParameter = true,
  nodeId = "",
  nodeClass,
  handleNodeClass,
}: InputProps<McpServerValue>): JSX.Element | null {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const {
    data: mcpServers,
    refetch: refetchMCPServers,
    isFetching: isFetchingMCPServers,
  } = useGetMCPServers({ withCounts: true });
  const { mutate: addMcpServer } = useAddMCPServer();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const updateBuildStatus = useFlowStore((state) => state.updateBuildStatus);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const options = useMemo(
    () =>
      mcpServers?.map((server) => ({
        name: server.name,
        description: server.error
          ? server.error
          : server.toolsCount === null
            ? t("mcp.loadingTools")
            : !server.toolsCount
              ? t("mcp.noToolsFound")
              : t("mcp.toolCount", { count: server.toolsCount }),
      })),
    [mcpServers],
  );
  const [addOpen, setAddOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<McpSelectionItem[]>([]);
  const { name, config } = useMemo(
    () => value ?? { name: "", config: {} },
    [value],
  );
  const selectedServerError = useMemo(
    () => mcpServers?.find((server) => server.name === name)?.error,
    [mcpServers, name],
  );

  const postTemplateValue = usePostTemplateValue({
    parameterId: "mcp_server",
    nodeId,
    node: nodeClass!,
  });

  const clearStaleErrorStatus = useCallback(() => {
    if (nodeId && typeof updateBuildStatus === "function") {
      updateBuildStatus([nodeId], BuildStatus.TO_BUILD);
    }
  }, [nodeId, updateBuildStatus]);

  const refreshNodeClass = useCallback(
    (newNodeClass: APIClassType) => {
      handleNodeClass?.(newNodeClass);
      clearStaleErrorStatus();
    },
    [clearStaleErrorStatus, handleNodeClass],
  );

  // Initialize selected item from value on mount or value/options change
  const selectedOption = useMemo(
    () =>
      name
        ? (options?.find((option) => option.name === name) ?? { name: null })
        : null,
    [name, options],
  );

  useEffect(() => {
    if (!options) return;
    const selectedOption = name
      ? options?.find((option) => option.name === name)
      : null;

    if (
      name !== selectedOption?.name &&
      Object.keys(config ?? {}).length === 0
    ) {
      const nextName = selectedOption?.name ?? "";
      setSelectedItem((current) =>
        current[0]?.name === nextName ? current : [{ name: nextName }],
      );
      handleOnNewValue(
        { value: { name: "", config: {} } },
        { skipSnapshot: true },
      );
      return;
    }
    setSelectedItem((current) =>
      current[0]?.name === name ? current : [{ name }],
    );
  }, [name, options]);

  // Handle selection from dialog
  const handleSelection = (item: McpSelectionItem) => {
    setSelectedItem([{ name: item.name }]);
    handleOnNewValue(
      { value: { name: item.name, config: {} } },
      { skipSnapshot: true, setNodeClass: clearStaleErrorStatus },
    );
    setOpen(false);
  };

  const handleAddButtonClick = () => {
    setAddOpen(true);
  };

  const handleSaveButtonClick = () => {
    addMcpServer(
      {
        name,
        ...(config ?? {}),
      },
      {
        onSuccess: () => {
          handleSuccess(name);
        },
        onError: (error) => {
          setErrorData({
            title: t("errors.addMcpServer"),
            list: [error.message],
          });
        },
      },
    );
  };

  const handleRemoveButtonClick = () => {
    handleOnNewValue({ value: { name: "", config: {} } });
  };

  const handleRefreshButtonClick = async () => {
    if (!name || !nodeClass || !nodeId) return;

    setIsRefreshing(true);
    setOpen(false);
    try {
      await refetchMCPServers();
      await mutateTemplate(
        { name, config: config ?? {} },
        nodeId,
        nodeClass,
        refreshNodeClass,
        postTemplateValue,
        setErrorData,
        "mcp_server",
        () => {
          clearStaleErrorStatus();
          setIsRefreshing(false);
        },
        nodeClass.tool_mode,
        true,
      );
    } catch (error) {
      setIsRefreshing(false);
      setErrorData({
        title: t("errors.refreshMcpServer"),
        list: [error instanceof Error ? error.message : String(error)],
      });
    } finally {
      setTimeout(() => setIsRefreshing(false), 5000);
    }
  };

  const handleOpenListSelectionDialog = () => {
    setOpen(true);
  };
  const handleCloseListSelectionDialog = () => setOpen(false);

  const handleSuccess = (server: string) => {
    handleOnNewValue(
      { value: { name: server, config: {} } },
      { setNodeClass: clearStaleErrorStatus },
    );
    setOpen(false);
  };

  const showSaveButton = useMemo(() => {
    return (
      !selectedOption?.name &&
      Object.keys(config ?? {}).length > 0 &&
      options !== null
    );
  }, [selectedOption, config]);

  if (!showParameter) {
    return null;
  }

  return (
    <div className="flex w-full flex-col gap-2">
      {options == null || options.length > 0 || showSaveButton ? (
        <div className="flex w-full gap-2">
          <Button
            variant={!showSaveButton ? "primary" : "secondary"}
            size="xs"
            role="combobox"
            onClick={
              !showSaveButton
                ? handleOpenListSelectionDialog
                : handleRemoveButtonClick
            }
            className={cn(
              !showSaveButton
                ? "dropdown-component-outline input-edit-node"
                : "",
              "w-full py-2",
            )}
            data-testid="mcp-server-dropdown"
            disabled={disabled || !options}
          >
            <div
              className={cn(
                "flex w-full items-center justify-start text-sm font-normal",
              )}
            >
              <span className="truncate">
                {!options
                  ? t("mcp.loadingServers")
                  : selectedItem[0]?.name
                    ? selectedItem[0]?.name
                    : t("mcp.selectServer")}
              </span>
              <ForwardedIconComponent
                name={!showSaveButton ? "ChevronsUpDown" : "X"}
                className="ml-auto h-5 w-5 text-muted-foreground"
              />
            </div>
          </Button>
          {showSaveButton && (
            <Button
              variant="primary"
              size="iconMd"
              className="px-2.5"
              onClick={handleSaveButtonClick}
              data-testid="save-mcp-server-button"
            >
              <ForwardedIconComponent
                name="Save"
                className="h-5 w-5 text-muted-foreground"
              />
            </Button>
          )}
          {name && !showSaveButton && (
            <ShadTooltip content={t("mcp.refreshServer")}>
              <Button
                variant="ghost"
                size="iconMd"
                className="px-2.5"
                onClick={handleRefreshButtonClick}
                data-testid="refresh-mcp-server-button"
                aria-label={t("mcp.refreshServer")}
                disabled={disabled || isRefreshing || isFetchingMCPServers}
              >
                <ForwardedIconComponent
                  name="RefreshCcw"
                  className={cn(
                    "h-5 w-5 text-muted-foreground",
                    (isRefreshing || isFetchingMCPServers) && "animate-spin",
                  )}
                />
              </Button>
            </ShadTooltip>
          )}
        </div>
      ) : (
        <Button
          size="sm"
          onClick={handleAddButtonClick}
          data-testid="add-mcp-server-simple-button"
        >
          <span>{t("input.addMcpServer")}</span>
        </Button>
      )}
      {options && (
        <>
          <ListSelectionComponent
            open={open}
            onClose={handleCloseListSelectionDialog}
            onSelection={handleSelection}
            setSelectedList={setSelectedItem}
            selectedList={selectedItem}
            options={options}
            limit={1}
            id={id}
            value={name}
            editNode={editNode}
            headerSearchPlaceholder={t("mcp.searchServers")}
            handleOnNewValue={handleOnNewValue}
            disabled={disabled}
            addButtonText={t("mcp.addServer")}
            onAddButtonClick={handleAddButtonClick}
          />
          <AddMcpServerModal
            open={addOpen}
            setOpen={setAddOpen}
            onSuccess={handleSuccess}
          />
        </>
      )}
      {selectedServerError && (
        <div
          className="break-words text-xs text-destructive"
          data-testid="mcp-server-error"
        >
          {selectedServerError}
        </div>
      )}
    </div>
  );
}
