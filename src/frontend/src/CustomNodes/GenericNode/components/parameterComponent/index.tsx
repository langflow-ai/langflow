import { cloneDeep } from "lodash";
import { ReactNode, useEffect, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useUpdateNodeInternals } from "reactflow";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import DictComponent from "../../../../components/dictComponent";
import Dropdown from "../../../../components/dropdownComponent";
import FloatComponent from "../../../../components/floatComponent";
import { default as IconComponent } from "../../../../components/genericIconComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import InputGlobalComponent from "../../../../components/inputGlobalComponent";
import InputListComponent from "../../../../components/inputListComponent";
import IntComponent from "../../../../components/intComponent";
import KeypairListComponent from "../../../../components/keypairListComponent";
import { Multiselect } from "../../../../components/multiselectComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import ToggleShadComponent from "../../../../components/toggleShadComponent";
import { Button } from "../../../../components/ui/button";
import { RefreshButton } from "../../../../components/ui/refreshButton";
import { LANGFLOW_SUPPORTED_TYPES } from "../../../../constants/constants";
import { Case } from "../../../../shared/components/caseComponent";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType } from "../../../../types/api";
import { ParameterComponentType } from "../../../../types/components";
import {
  debouncedHandleUpdateValues,
  handleUpdateValues,
} from "../../../../utils/parameterUtils";
import {
  convertObjToArray,
  convertValuesToNumbers,
  getGroupOutputNodeId,
  hasDuplicateKeys,
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
import useHandleNodeClass from "../../../hooks/use-handle-node-class";
import useHandleRefreshButtonPress from "../../../hooks/use-handle-refresh-buttons";
import OutputComponent from "../OutputComponent";
import HandleRenderComponent from "../handleRenderComponent";
import OutputModal from "../outputModal";
import { TEXT_FIELD_TYPES } from "./constants";

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
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const [isLoading, setIsLoading] = useState(false);
  const updateNodeInternals = useUpdateNodeInternals();
  const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);
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

  const output = useShortcutsStore((state) => state.output);
  useHotkeys(output, handleOutputWShortcut, { preventDefault });

  const { handleOnNewValue: handleOnNewValueHook } = useHandleOnNewValue(
    data,
    name,
    takeSnapshot,
    handleUpdateValues,
    debouncedHandleUpdateValues,
    setNode,
    setIsLoading,
  );

  const { handleNodeClass: handleNodeClassHook } = useHandleNodeClass(
    data,
    name,
    takeSnapshot,
    setNode,
    updateNodeInternals,
  );

  const { handleRefreshButtonPress: handleRefreshButtonPressHook } =
    useHandleRefreshButtonPress(setIsLoading, setNode);

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

  const handleRefreshButtonPress = async (name, data) => {
    handleRefreshButtonPressHook(name, data);
  };

  useFetchDataOnMount(data, name, handleUpdateValues, setNode, setIsLoading);

  const handleOnNewValue = async (
    newValue: string | string[] | boolean | Object[],
    dbValue?: boolean,
    skipSnapshot: boolean | undefined = false,
  ): Promise<void> => {
    handleOnNewValueHook(newValue, dbValue, skipSnapshot);
  };

  const handleNodeClass = (
    newNodeClass: APIClassType,
    code?: string,
    type?: string,
  ): void => {
    handleNodeClassHook(newNodeClass, code, type);
  };

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

        <Case
          condition={
            left === true &&
            TEXT_FIELD_TYPES.includes(type ?? "") &&
            !data.node?.template[name]?.options
          }
        >
          <div className="w-full">
            <Case condition={data.node?.template[name]?.list}>
              <div
                className={
                  // Commenting this out until we have a better
                  // way to display
                  // (data.node?.template[name]?.refresh ? "w-5/6 " : "") +
                  "mt-2 flex-grow"
                }
              >
                <InputListComponent
                  componentName={name}
                  disabled={disabled}
                  value={
                    !data.node!.template[name]?.value ||
                    data.node!.template[name]?.value === ""
                      ? [""]
                      : data.node!.template[name]?.value
                  }
                  onChange={handleOnNewValue}
                />
              </div>
            </Case>
            <Case condition={data.node?.template[name]?.multiline}>
              <div className="mt-2 flex w-full flex-col">
                <div className="flex-grow">
                  <TextAreaComponent
                    disabled={disabled}
                    value={data.node!.template[name]?.value ?? ""}
                    onChange={handleOnNewValue}
                    id={"textarea-" + data.node!.template[name]?.name}
                    data-testid={"textarea-" + data.node!.template[name]?.name}
                  />
                </div>
                {data.node?.template[name]?.refresh_button && (
                  <div className="flex-grow">
                    <RefreshButton
                      isLoading={isLoading}
                      disabled={disabled}
                      name={name}
                      data={data}
                      button_text={
                        data.node?.template[name].refresh_button_text
                      }
                      className="extra-side-bar-buttons mt-1"
                      handleUpdateValues={handleRefreshButtonPress}
                      id={"refresh-button-" + name}
                    />
                  </div>
                )}
              </div>
            </Case>
            <Case
              condition={
                !data.node?.template[name]?.multiline &&
                !data.node?.template[name]?.list
              }
            >
              <div className="mt-2 flex w-full items-center">
                <div
                  className={
                    "flex-grow " +
                    (data.node?.template[name]?.refresh_button ? "w-5/6" : "")
                  }
                >
                  <InputGlobalComponent
                    disabled={disabled}
                    onChange={handleOnNewValue}
                    name={name}
                    data={data.node?.template[name]!}
                  />
                </div>
                {data.node?.template[name]?.refresh_button && (
                  <div className="w-1/6">
                    <RefreshButton
                      isLoading={isLoading}
                      disabled={disabled}
                      name={name}
                      data={data}
                      button_text={
                        data.node?.template[name].refresh_button_text
                      }
                      className="extra-side-bar-buttons ml-2 mt-1"
                      handleUpdateValues={handleRefreshButtonPress}
                      id={"refresh-button-" + name}
                    />
                  </div>
                )}
              </div>
            </Case>
          </div>
        </Case>

        <Case condition={left === true && type === "bool"}>
          <div className="mt-2 w-full">
            <ToggleShadComponent
              id={"toggle-" + name}
              disabled={disabled}
              enabled={data.node?.template[name]?.value ?? false}
              setEnabled={handleOnNewValue}
              size="large"
              editNode={false}
            />
          </div>
        </Case>

        <Case condition={left === true && type === "float"}>
          <div className="mt-2 w-full">
            <FloatComponent
              disabled={disabled}
              value={data.node?.template[name]?.value ?? ""}
              rangeSpec={data.node?.template[name]?.rangeSpec}
              onChange={handleOnNewValue}
            />
          </div>
        </Case>

        <Case
          condition={
            left === true &&
            type === "str" &&
            !data.node?.template[name]?.list &&
            (data.node?.template[name]?.options ||
              data.node?.template[name]?.real_time_refresh)
          }
        >
          <div className="mt-2 flex w-full items-center gap-2">
            <div className="flex-1">
              <Dropdown
                disabled={disabled}
                isLoading={isLoading}
                options={data.node!.template[name]?.options}
                onSelect={handleOnNewValue}
                value={data.node!.template[name]?.value}
                id={"dropdown-" + name}
              />
            </div>
            {data.node?.template[name]?.refresh_button && (
              <div className="w-1/6">
                <RefreshButton
                  isLoading={isLoading}
                  disabled={disabled}
                  name={name}
                  data={data}
                  button_text={data.node?.template[name]?.refresh_button_text}
                  handleUpdateValues={handleRefreshButtonPress}
                  id={"refresh-button-" + name}
                />
              </div>
            )}
          </div>
        </Case>
        <Case
          condition={
            type === "str" &&
            !!data.node?.template[name]?.options &&
            !!data.node?.template[name]?.list
          }
        >
          <div className="mt-2 flex w-full items-center">
            <Multiselect
              disabled={disabled}
              options={data?.node?.template?.[name]?.options || []}
              values={data?.node?.template?.[name]?.value || []}
              id={"multiselect-" + name}
              onValueChange={handleOnNewValue}
            />
          </div>
        </Case>

        <Case condition={left === true && type === "code"}>
          <div className="mt-2 w-full">
            <CodeAreaComponent
              readonly={
                data.node?.flow && data.node.template[name]?.dynamic
                  ? true
                  : false
              }
              dynamic={data.node?.template[name]?.dynamic ?? false}
              setNodeClass={handleNodeClass}
              nodeClass={data.node}
              disabled={disabled}
              value={data.node?.template[name]?.value ?? ""}
              onChange={handleOnNewValue}
              id={"code-input-" + name}
            />
          </div>
        </Case>

        <Case condition={left === true && type === "file"}>
          <div className="mt-2 w-full">
            <InputFileComponent
              disabled={disabled}
              value={data.node?.template[name]?.value ?? ""}
              onChange={handleOnNewValue}
              fileTypes={data.node?.template[name]?.fileTypes}
              onFileChange={(filePath: string) => {
                data.node!.template[name].file_path = filePath;
              }}
            ></InputFileComponent>
          </div>
        </Case>

        <Case condition={left === true && type === "int"}>
          <div className="mt-2 w-full">
            <IntComponent
              rangeSpec={data.node?.template[name]?.rangeSpec}
              disabled={disabled}
              value={data.node?.template[name]?.value ?? ""}
              onChange={handleOnNewValue}
              id={"int-input-" + name}
            />
          </div>
        </Case>

        <Case condition={left === true && type === "prompt"}>
          <div className="mt-2 w-full">
            <PromptAreaComponent
              readonly={data.node?.flow ? true : false}
              field_name={name}
              setNodeClass={handleNodeClass}
              nodeClass={data.node}
              disabled={disabled}
              value={data.node?.template[name]?.value ?? ""}
              onChange={handleOnNewValue}
              id={"prompt-input-" + name}
              data-testid={"prompt-input-" + name}
            />
          </div>
        </Case>

        <Case condition={left === true && type === "NestedDict"}>
          <div
            className={"mt-2 w-full" + (disabled ? " cursor-not-allowed" : "")}
          >
            <DictComponent
              disabled={disabled}
              editNode={false}
              value={
                !data.node!.template[name]?.value ||
                !Object.keys(data.node!.template[name]?.value || {}).length
                  ? {}
                  : data.node!.template[name]?.value
              }
              onChange={handleOnNewValue}
              id="div-dict-input"
            />
          </div>
        </Case>

        <Case condition={left === true && type === "dict"}>
          <div className="mt-2 w-full">
            <KeypairListComponent
              disabled={disabled}
              editNode={false}
              value={
                !data.node!.template[name]?.value ||
                !Object.keys(data.node!.template[name]?.value || {}).length
                  ? [{ "": "" }]
                  : convertObjToArray(data.node!.template[name]?.value, type!)
              }
              duplicateKey={errorDuplicateKey}
              onChange={(newValue) => {
                const valueToNumbers = convertValuesToNumbers(newValue);
                setErrorDuplicateKey(hasDuplicateKeys(valueToNumbers));
                // if data.node?.template[name]?.list is true, then the value is an array of objects
                // else we need to get the first object of the array

                if (data.node?.template[name]?.list) {
                  handleOnNewValue(valueToNumbers);
                } else handleOnNewValue(valueToNumbers[0]);
              }}
              isList={data.node?.template[name]?.list ?? false}
            />
          </div>
        </Case>
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
