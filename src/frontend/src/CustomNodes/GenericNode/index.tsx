import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { useEffect, useMemo, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { NodeToolbar, useUpdateNodeInternals } from "reactflow";
import IconComponent, {
  ForwardedIconComponent,
} from "../../components/genericIconComponent";
import ShadTooltip from "../../components/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import { TOOLTIP_OUTDATED_NODE } from "../../constants/constants";
import NodeToolbarComponent from "../../pages/FlowPage/components/nodeToolbarComponent";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../stores/shortcuts";
import { useTypesStore } from "../../stores/typesStore";
import { OutputFieldType } from "../../types/api";
import { NodeDataType } from "../../types/flow";
import { scapedJSONStringfy } from "../../utils/reactflowUtils";
import { nodeIconsLucide } from "../../utils/styleUtils";
import { classNames, cn } from "../../utils/utils";
import { getNodeInputColors } from "../helpers/get-node-input-colors";
import { getNodeOutputColors } from "../helpers/get-node-output-colors";
import useCheckCodeValidity from "../hooks/use-check-code-validity";
import useUpdateNodeCode from "../hooks/use-update-node-code";
import getFieldTitle from "../utils/get-field-title";
import sortFields from "../utils/sort-fields";
import NodeDescription from "./components/NodeDescription";
import NodeInputField from "./components/NodeInputField";
import NodeName from "./components/NodeName";
import NodeOutputField from "./components/NodeOutputfield";
import NodeStatus from "./components/NodeStatus";
import { NodeIcon } from "./components/nodeIcon";

export default function GenericNode({
  data,
  selected,
}: {
  data: NodeDataType;
  selected: boolean;
  xPos?: number;
  yPos?: number;
}): JSX.Element {
  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const deleteNode = useFlowStore((state) => state.deleteNode);
  const setNode = useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const [isOutdated, setIsOutdated] = useState(false);
  const [isUserEdited, setIsUserEdited] = useState(false);
  const [borderColor, setBorderColor] = useState<string>("");
  const showNode = data.showNode ?? true;

  const updateNodeCode = useUpdateNodeCode(
    data?.id,
    data.node!,
    setNode,
    setIsOutdated,
    setIsUserEdited,
    updateNodeInternals,
  );

  const name = nodeIconsLucide[data.type] ? data.type : types[data.type];

  if (!data.node!.template) {
    setErrorData({
      title: `Error in component ${data.node!.display_name}`,
      list: [
        `The component ${data.node!.display_name} has no template.`,
        `Please contact the developer of the component to fix this issue.`,
      ],
    });
    takeSnapshot();
    deleteNode(data.id);
  }

  useCheckCodeValidity(data, templates, setIsOutdated, setIsUserEdited, types);

  const [loadingUpdate, setLoadingUpdate] = useState(false);

  const [showHiddenOutputs, setShowHiddenOutputs] = useState(false);

  const { mutate: validateComponentCode } = usePostValidateComponentCode();

  const handleUpdateCode = () => {
    setLoadingUpdate(true);
    takeSnapshot();
    // to update we must get the code from the templates in useTypesStore
    const thisNodeTemplate = templates[data.type]?.template;
    // if the template does not have a code key
    // return
    if (!thisNodeTemplate?.code) return;

    const currentCode = thisNodeTemplate.code.value;
    if (data.node) {
      validateComponentCode(
        { code: currentCode, frontend_node: data.node },
        {
          onSuccess: ({ data, type }) => {
            if (data && type && updateNodeCode) {
              updateNodeCode(data, currentCode, "code", type);
              setLoadingUpdate(false);
            }
          },
          onError: (error) => {
            setErrorData({
              title: "Error updating Compoenent code",
              list: [
                "There was an error updating the Component.",
                "If the error persists, please report it on our Discord or GitHub.",
              ],
            });
            console.log(error);
            setLoadingUpdate(false);
          },
        },
      );
    }
  };

  function handleUpdateCodeWShortcut() {
    if (isOutdated && selected) {
      handleUpdateCode();
    }
  }

  const shownOutputs =
    data.node!.outputs?.filter((output) => !output.hidden) ?? [];

  const hiddenOutputs =
    data.node!.outputs?.filter((output) => output.hidden) ?? [];

  const update = useShortcutsStore((state) => state.update);
  useHotkeys(update, handleUpdateCodeWShortcut, { preventDefault: true });

  const shortcuts = useShortcutsStore((state) => state.shortcuts);

  const renderOutputParameter = (output: OutputFieldType, idx: number) => {
    return (
      <NodeOutputField
        index={idx}
        selected={selected}
        key={
          scapedJSONStringfy({
            output_types: output.types,
            name: output.name,
            id: data.id,
            dataType: data.type,
          }) + idx
        }
        data={data}
        colors={getNodeOutputColors(output, data, types)}
        outputProxy={output.proxy}
        title={output.display_name ?? output.name}
        tooltipTitle={output.selected ?? output.types[0]}
        id={{
          output_types: [output.selected ?? output.types[0]],
          id: data.id,
          dataType: data.type,
          name: output.name,
        }}
        type={output.types.join("|")}
        showNode={showNode}
        outputName={output.name}
      />
    );
  };

  useEffect(() => {
    if (hiddenOutputs && hiddenOutputs.length == 0) {
      setShowHiddenOutputs(false);
    }
  }, [hiddenOutputs]);

  const memoizedNodeToolbarComponent = useMemo(() => {
    return (
      <NodeToolbar>
        <NodeToolbarComponent
          data={data}
          deleteNode={(id) => {
            takeSnapshot();
            deleteNode(id);
          }}
          setShowNode={(show) => {
            setNode(data.id, (old) => ({
              ...old,
              data: { ...old.data, showNode: show },
            }));
          }}
          numberOfOutputHandles={shownOutputs.length ?? 0}
          showNode={showNode}
          openAdvancedModal={false}
          onCloseAdvancedModal={() => {}}
          updateNode={handleUpdateCode}
          isOutdated={isOutdated && isUserEdited}
        />
      </NodeToolbar>
    );
  }, [
    data,
    deleteNode,
    takeSnapshot,
    setNode,
    showNode,
    updateNodeCode,
    isOutdated,
    isUserEdited,
    selected,
    shortcuts,
  ]);

  const renderInputParameter = Object.keys(data.node!.template)
    .filter((templateField) => templateField.charAt(0) !== "_")
    .sort((a, b) => sortFields(a, b, data.node?.field_order ?? []))
    .map(
      (templateField: string, idx) =>
        data.node!.template[templateField]?.show &&
        !data.node!.template[templateField]?.advanced && (
          <NodeInputField
            key={scapedJSONStringfy({
              inputTypes: data.node!.template[templateField].input_types,
              type: data.node!.template[templateField].type,
              id: data.id,
              fieldName: templateField,
              proxy: data.node!.template[templateField].proxy,
            })}
            data={data}
            colors={getNodeInputColors(
              data.node?.template[templateField].input_types,
              data.node?.template[templateField].type,
              types,
            )}
            title={getFieldTitle(data.node?.template!, templateField)}
            info={data.node?.template[templateField].info!}
            name={templateField}
            tooltipTitle={
              data.node?.template[templateField].input_types?.join("\n") ??
              data.node?.template[templateField].type
            }
            required={data.node!.template[templateField].required}
            id={{
              inputTypes: data.node!.template[templateField].input_types,
              type: data.node!.template[templateField].type,
              id: data.id,
              fieldName: templateField,
            }}
            type={data.node?.template[templateField].type}
            optionalHandle={data.node?.template[templateField].input_types}
            proxy={data.node?.template[templateField].proxy}
            showNode={showNode}
          />
        ),
    );

  return (
    <>
      {memoizedNodeToolbarComponent}
      <div
        className={cn(
          borderColor,
          showNode ? "w-96 rounded-lg" : "w-26 h-26 rounded-full",
          "generic-node-div group/node",
        )}
      >
        {data.node?.beta && showNode && (
          <div className="beta-badge-wrapper">
            <div className="beta-badge-content">BETA</div>
          </div>
        )}
        <div>
          <div
            data-testid={"div-generic-node"}
            className={
              "generic-node-div-title " +
              (!showNode
                ? " relative h-24 w-24 rounded-full"
                : " justify-between rounded-t-lg")
            }
          >
            <div
              className={
                "generic-node-title-arrangement " +
                (!showNode ? " justify-center" : "")
              }
              data-testid="generic-node-title-arrangement"
            >
              <NodeIcon
                dataType={data.type}
                showNode={showNode}
                icon={data.node?.icon}
                isGroup={!!data.node?.flow}
              />
              {showNode && (
                <div className="generic-node-tooltip-div">
                  <NodeName
                    display_name={data.node?.display_name}
                    nodeId={data.id}
                    selected={selected}
                  />
                  {isOutdated && !isUserEdited && (
                    <ShadTooltip content={TOOLTIP_OUTDATED_NODE}>
                      <Button
                        onClick={handleUpdateCode}
                        unstyled
                        className={"group p-1"}
                        loading={loadingUpdate}
                      >
                        <IconComponent
                          name="AlertTriangle"
                          className="h-5 w-5 fill-status-yellow text-muted"
                        />
                      </Button>
                    </ShadTooltip>
                  )}
                </div>
              )}
            </div>
            <div>
              {!showNode && (
                <>
                  {renderInputParameter}
                  {shownOutputs &&
                    shownOutputs.length > 0 &&
                    renderOutputParameter(
                      shownOutputs[0],
                      data.node!.outputs?.findIndex(
                        (out) => out.name === shownOutputs[0].name,
                      ) ?? 0,
                    )}
                </>
              )}
            </div>
            {showNode && (
              <NodeStatus
                frozen={data.node?.frozen}
                showNode={showNode}
                display_name={data.node?.display_name!}
                nodeId={data.id}
                selected={selected}
                setBorderColor={setBorderColor}
              />
            )}
          </div>
        </div>

        {showNode && (
          <div className="relative pb-8 pt-5">
            {/* increase height!! */}
            <NodeDescription
              description={data.node?.description}
              nodeId={data.id}
              selected={selected}
            />
            <>
              {renderInputParameter}
              <div
                className={classNames(
                  Object.keys(data.node!.template).length < 1 ? "hidden" : "",
                  "flex-max-width justify-center",
                )}
              >
                {" "}
              </div>
              {!showHiddenOutputs &&
                shownOutputs &&
                shownOutputs.map((output, idx) =>
                  renderOutputParameter(
                    output,
                    data.node!.outputs?.findIndex(
                      (out) => out.name === output.name,
                    ) ?? idx,
                  ),
                )}
              <div
                className={cn(showHiddenOutputs ? "" : "h-0 overflow-hidden")}
              >
                <div className="block">
                  {data.node!.outputs &&
                    data.node!.outputs.map((output, idx) =>
                      renderOutputParameter(
                        output,
                        data.node!.outputs?.findIndex(
                          (out) => out.name === output.name,
                        ) ?? idx,
                      ),
                    )}
                </div>
              </div>
              {hiddenOutputs && hiddenOutputs.length > 0 && (
                <div
                  className={cn(
                    "absolute left-0 right-0 flex justify-center",
                    (shownOutputs && shownOutputs.length > 0) ||
                      showHiddenOutputs
                      ? "bottom-5"
                      : "bottom-1.5",
                  )}
                >
                  <Button
                    unstyled
                    className="left-0 right-0 rounded-full border bg-background"
                    onClick={() => setShowHiddenOutputs(!showHiddenOutputs)}
                  >
                    <ForwardedIconComponent
                      name={"ChevronDown"}
                      strokeWidth={1.5}
                      className={cn(
                        "h-5 w-5 pt-px text-muted-foreground group-hover:text-medium-indigo group-hover/node:opacity-100",
                        showHiddenOutputs ? "rotate-180 transform" : "",
                      )}
                    />
                  </Button>
                </div>
              )}
            </>
          </div>
        )}
      </div>
    </>
  );
}
