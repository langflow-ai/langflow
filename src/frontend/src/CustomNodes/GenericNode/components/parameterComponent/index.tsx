import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { ParameterRenderComponent } from "@/components/parameterRenderComponent";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import useAlertStore from "@/stores/alertStore";
import { cloneDeep } from "lodash";
import { ReactNode, useEffect, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useUpdateNodeInternals } from "reactflow";
import { default as IconComponent } from "../../../../components/genericIconComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import { Button } from "../../../../components/ui/button";
import { LANGFLOW_SUPPORTED_TYPES } from "../../../../constants/constants";
import { Case } from "../../../../shared/components/caseComponent";
import useFlowStore from "../../../../stores/flowStore";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import { useTypesStore } from "../../../../stores/typesStore";
import { ParameterComponentType } from "../../../../types/components";
import {
  getGroupOutputNodeId,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import {
  classNames,
  cn,
  isThereModal,
  logHasMessage,
  logTypeIsError,
  logTypeIsUnknown,
} from "../../../../utils/utils";
import useFetchDataOnMount from "../../../hooks/use-fetch-data-on-mount";
import useHandleOnNewValue from "../../../hooks/use-handle-new-value";
import OutputComponent from "../OutputComponent";
import HandleRenderComponent from "../handleRenderComponent";
import OutputModal from "../outputModal";

export default function ParameterComponent({
  left,
  id,
  data,
  tooltipTitle,
  title,
  colors,
  type,
  name = "",
  required = false,
  optionalHandle = null,
  info = "",
  proxy,
  showNode,
  index,
  outputName,
  selected,
  outputProxy,
}: ParameterComponentType): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const infoHtml = useRef<HTMLDivElement & ReactNode>(null);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNode = useFlowStore((state) => state.setNode);
  const myData = useTypesStore((state) => state.data);
  const postTemplateValue = usePostTemplateValue({
    node: data.node!,
    nodeId: data.id,
    parameterId: name,
  });
  const updateNodeInternals = useUpdateNodeInternals();
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const [openOutputModal, setOpenOutputModal] = useState(false);
  const flowPool = useFlowStore((state) => state.flowPool);

  let flowPoolId = data.id;
  let internalOutputName = outputName;

  if (data.node?.flow && outputProxy) {
    const realOutput = getGroupOutputNodeId(
      data.node.flow,
      outputProxy.name,
      outputProxy.id,
    );
    if (realOutput) {
      flowPoolId = realOutput.id;
      internalOutputName = realOutput.outputName;
    }
  }

  const flowPoolNode = (flowPool[flowPoolId] ?? [])[
    (flowPool[flowPoolId]?.length ?? 1) - 1
  ];

  const displayOutputPreview =
    !!flowPool[flowPoolId] &&
    logHasMessage(flowPoolNode?.data, internalOutputName);

  const unknownOutput = logTypeIsUnknown(
    flowPoolNode?.data,
    internalOutputName,
  );
  const errorOutput = logTypeIsError(flowPoolNode?.data, internalOutputName);

  if (outputProxy) {
    console.log(logHasMessage(flowPoolNode?.data, internalOutputName));
  }

  const preventDefault = true;

  function handleOutputWShortcut() {
    if (!displayOutputPreview || unknownOutput) return;
    if (isThereModal() && !openOutputModal) return;
    if (selected && !left) {
      setOpenOutputModal((state) => !state);
    }
  }

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const output = useShortcutsStore((state) => state.output);
  useHotkeys(output, handleOutputWShortcut, { preventDefault });

  const { handleNodeClass } = useHandleNodeClass(data.id);

  let disabled =
    edges.some(
      (edge) =>
        edge.targetHandle === scapedJSONStringfy(proxy ? { ...id, proxy } : id),
    ) ?? false;

  let disabledOutput =
    edges.some(
      (edge) =>
        edge.sourceHandle === scapedJSONStringfy(proxy ? { ...id, proxy } : id),
    ) ?? false;

  const { handleOnNewValue } = useHandleOnNewValue({
    node: data.node!,
    nodeId: data.id,
    name,
  });

  useFetchDataOnMount(data.node!, handleNodeClass, name, postTemplateValue);

  useEffect(() => {
    // @ts-ignore
    infoHtml.current = (
      <div className="h-full w-full break-words">
        {info.split("\n").map((line, index) => (
          <p key={index} className="block">
            {line}
          </p>
        ))}
      </div>
    );
  }, [info]);

  function renderTitle() {
    return !left ? (
      <OutputComponent
        proxy={outputProxy}
        idx={index}
        types={type?.split("|") ?? []}
        selected={
          data.node?.outputs![index].selected ??
          data.node?.outputs![index].types[0] ??
          title
        }
        nodeId={data.id}
        frozen={data.node?.frozen}
        name={title ?? type}
      />
    ) : (
      <span>{title}</span>
    );
  }

  useEffect(() => {
    if (optionalHandle && optionalHandle.length === 0) {
      optionalHandle = null;
    }
  }, [optionalHandle]);

  const handleUpdateOutputHide = (value?: boolean) => {
    setNode(data.id, (oldNode) => {
      let newNode = cloneDeep(oldNode);
      newNode.data = {
        ...newNode.data,
        node: {
          ...newNode.data.node,
          outputs: newNode.data.node.outputs?.map((output, i) => {
            if (i === index) {
              output.hidden = value ?? !output.hidden;
            }
            return output;
          }),
        },
      };
      return newNode;
    });
    updateNodeInternals(data.id);
  };

  useEffect(() => {
    if (disabledOutput && data.node?.outputs![index].hidden) {
      handleUpdateOutputHide(false);
    }
  }, [disabledOutput]);

  return !showNode ? (
    left && LANGFLOW_SUPPORTED_TYPES.has(type ?? "") && !optionalHandle ? (
      <></>
    ) : (
      <HandleRenderComponent
        left={left}
        nodes={nodes}
        tooltipTitle={tooltipTitle}
        proxy={proxy}
        id={id}
        title={title}
        edges={edges}
        myData={myData}
        colors={colors}
        setFilterEdge={setFilterEdge}
        showNode={showNode}
        testIdComplement={`${data?.type?.toLowerCase()}-noshownode`}
      />
    )
  ) : (
    <div
      ref={ref}
      className={
        "relative mt-1 flex w-full flex-wrap items-center justify-between bg-muted px-5 py-2" +
        ((name === "code" && type === "code") ||
        (name.includes("code") && proxy)
          ? " hidden"
          : "")
      }
    >
      <>
        <div
          className={
            "flex w-full items-center truncate text-sm" +
            (left ? "" : " justify-end")
          }
        >
          {!left && (
            <div className="flex-1">
              <Button
                disabled={disabledOutput}
                unstyled
                onClick={() => handleUpdateOutputHide()}
                data-testid={`input-inspection-${title.toLowerCase()}`}
              >
                <IconComponent
                  className={cn(
                    "h-4 w-4",
                    disabledOutput ? "text-muted-foreground" : "",
                  )}
                  strokeWidth={1.5}
                  name={data.node?.outputs![index].hidden ? "EyeOff" : "Eye"}
                />
              </Button>
            </div>
          )}
          <Case condition={!left && data.node?.frozen}>
            <div className="pr-1">
              <IconComponent className="h-5 w-5 text-ice" name={"Snowflake"} />
            </div>
          </Case>

          {proxy ? (
            <ShadTooltip content={<span>{proxy.id}</span>}>
              {renderTitle()}
            </ShadTooltip>
          ) : (
            <div className="flex gap-2">
              <span className={!left && data.node?.frozen ? "text-ice" : ""}>
                {renderTitle()}
              </span>
              {!left && (
                <ShadTooltip
                  content={
                    displayOutputPreview
                      ? unknownOutput
                        ? "Output can't be displayed"
                        : "Inspect Output"
                      : "Please build the component first"
                  }
                >
                  <Button
                    unstyled
                    disabled={!displayOutputPreview || unknownOutput}
                    onClick={() => setOpenOutputModal(true)}
                    data-testid={`output-inspection-${title.toLowerCase()}`}
                  >
                    {errorOutput ? (
                      <IconComponent
                        className={classNames(
                          "h-5 w-5 rounded-md text-status-red",
                        )}
                        name={"X"}
                      />
                    ) : (
                      <IconComponent
                        className={classNames(
                          "h-5 w-5 rounded-md",
                          displayOutputPreview && !unknownOutput
                            ? "hover:text-medium-indigo"
                            : "cursor-not-allowed text-muted-foreground",
                        )}
                        name={"ScanEye"}
                      />
                    )}
                  </Button>
                </ShadTooltip>
              )}
            </div>
          )}
          <span className={(required ? "ml-2 " : "") + "text-status-red"}>
            {required ? "*" : ""}
          </span>
          <div className="">
            {info !== "" && (
              <ShadTooltip content={infoHtml.current}>
                {/* put div to avoid bug that does not display tooltip */}
                <div className="cursor-help">
                  <IconComponent
                    name="Info"
                    className="relative bottom-px ml-1.5 h-3 w-4"
                  />
                </div>
              </ShadTooltip>
            )}
          </div>
        </div>

        {left && LANGFLOW_SUPPORTED_TYPES.has(type ?? "") && !optionalHandle ? (
          <></>
        ) : (
          <HandleRenderComponent
            left={left}
            nodes={nodes}
            tooltipTitle={tooltipTitle}
            proxy={proxy}
            id={id}
            title={title}
            edges={edges}
            myData={myData}
            colors={colors}
            setFilterEdge={setFilterEdge}
            showNode={showNode}
            testIdComplement={`${data?.type?.toLowerCase()}-shownode`}
          />
        )}
        {data.node?.template[name] !== undefined && (
          <div className="mt-2 w-full">
            <ParameterRenderComponent
              handleOnNewValue={handleOnNewValue}
              name={name}
              nodeId={data.id}
              templateData={data.node?.template[name]!}
              templateValue={data.node?.template[name].value ?? ""}
              editNode={false}
              handleNodeClass={handleNodeClass}
              nodeClass={data.node!}
              disabled={disabled}
            />
          </div>
        )}
        {openOutputModal && (
          <OutputModal
            open={openOutputModal}
            nodeId={flowPoolId}
            setOpen={setOpenOutputModal}
            outputName={internalOutputName}
          />
        )}
      </>
    </div>
  );
}
