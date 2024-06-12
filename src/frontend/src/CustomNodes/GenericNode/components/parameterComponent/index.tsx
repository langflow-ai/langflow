import { cloneDeep } from "lodash";
import { ReactNode, useEffect, useRef, useState } from "react";
import { Handle, Position, useUpdateNodeInternals } from "reactflow";
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
import PromptAreaComponent from "../../../../components/promptComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import ToggleShadComponent from "../../../../components/toggleShadComponent";
import { Button } from "../../../../components/ui/button";
import { RefreshButton } from "../../../../components/ui/refreshButton";
import {
  LANGFLOW_SUPPORTED_TYPES,
  TOOLTIP_EMPTY,
} from "../../../../constants/constants";
import { Case } from "../../../../shared/components/caseComponent";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
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
  hasDuplicateKeys,
  isValidConnection,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import { nodeColors } from "../../../../utils/styleUtils";
import {
  classNames,
  groupByFamily,
  isThereModal,
} from "../../../../utils/utils";
import useFetchDataOnMount from "../../../hooks/use-fetch-data-on-mount";
import useHandleOnNewValue from "../../../hooks/use-handle-new-value";
import useHandleNodeClass from "../../../hooks/use-handle-node-class";
import useHandleRefreshButtonPress from "../../../hooks/use-handle-refresh-buttons";
import TooltipRenderComponent from "../tooltipRenderComponent";
import { TEXT_FIELD_TYPES } from "./constants";
import OutputModal from "../outputModal";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import { useHotkeys } from "react-hotkeys-hook";

export default function ParameterComponent({
  left,
  id,
  data,
  tooltipTitle,
  title,
  color,
  type,
  name = "",
  required = false,
  optionalHandle = null,
  info = "",
  proxy,
  showNode,
  index = "",
  selected,
}: ParameterComponentType): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const refHtml = useRef<HTMLDivElement & ReactNode>(null);
  const infoHtml = useRef<HTMLDivElement & ReactNode>(null);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNode = useFlowStore((state) => state.setNode);
  const myData = useTypesStore((state) => state.data);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const [isLoading, setIsLoading] = useState(false);
  const updateNodeInternals = useUpdateNodeInternals();
  const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);
  const flow = currentFlow?.data?.nodes ?? null;
  const groupedEdge = useRef(null);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const [openOutputModal, setOpenOutputModal] = useState(false);
  const flowPool = useFlowStore((state) => state.flowPool);

  const displayOutputPreview =
    !!flowPool[data.id] &&
    flowPool[data.id][flowPool[data.id].length - 1]?.valid;

  const unknownOutput = !!(
    flowPool[data.id] &&
    flowPool[data.id][flowPool[data.id].length - 1]?.data?.logs[0]?.type ===
      "unknown"
  );

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
    renderTooltips,
    setIsLoading,
  );

  const { handleNodeClass: handleNodeClassHook } = useHandleNodeClass(
    data,
    name,
    takeSnapshot,
    setNode,
    updateNodeInternals,
    renderTooltips,
  );

  const { handleRefreshButtonPress: handleRefreshButtonPressHook } =
    useHandleRefreshButtonPress(setIsLoading, setNode, renderTooltips);

  let disabled =
    edges.some(
      (edge) =>
        edge.targetHandle === scapedJSONStringfy(proxy ? { ...id, proxy } : id),
    ) ?? false;

  const handleRefreshButtonPress = async (name, data) => {
    handleRefreshButtonPressHook(name, data);
  };

  useFetchDataOnMount(
    data,
    name,
    handleUpdateValues,
    setNode,
    renderTooltips,
    setIsLoading,
  );

  const handleOnNewValue = async (
    newValue: string | string[] | boolean | Object[],
    skipSnapshot: boolean | undefined = false,
  ): Promise<void> => {
    handleOnNewValueHook(newValue, skipSnapshot);
  };

  const handleNodeClass = (newNodeClass: APIClassType, code?: string): void => {
    handleNodeClassHook(newNodeClass, code);
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

  function renderTooltips() {
    let groupedObj: any = groupByFamily(myData, tooltipTitle!, left, flow!);
    groupedEdge.current = groupedObj;

    if (groupedObj && groupedObj.length > 0) {
      //@ts-ignore
      refHtml.current = groupedObj.map((item, index) => {
        return <TooltipRenderComponent index={index} item={item} left={left} />;
      });
    } else {
      //@ts-ignore
      refHtml.current = (
        <span data-testid={`empty-tooltip-filter`}>{TOOLTIP_EMPTY}</span>
      );
    }
  }

  // If optionalHandle is an empty list, then it is not an optional handle
  if (optionalHandle && optionalHandle.length === 0) {
    optionalHandle = null;
  }

  useEffect(() => {
    renderTooltips();
  }, [tooltipTitle, flow]);

  return !showNode ? (
    left && LANGFLOW_SUPPORTED_TYPES.has(type ?? "") && !optionalHandle ? (
      <></>
    ) : (
      <Button className="h-7 truncate bg-muted p-0 text-sm font-normal text-black hover:bg-muted">
        <div className="flex">
          <ShadTooltip
            styleClasses={"tooltip-fixed-width custom-scroll nowheel"}
            delayDuration={1000}
            content={refHtml.current}
            side={left ? "left" : "right"}
          >
            <Handle
              data-test-id={`handle-${title.toLowerCase()}-${
                left ? "target" : "source"
              }`}
              type={left ? "target" : "source"}
              position={left ? Position.Left : Position.Right}
              key={
                proxy
                  ? scapedJSONStringfy({ ...id, proxy })
                  : scapedJSONStringfy(id)
              }
              id={
                proxy
                  ? scapedJSONStringfy({ ...id, proxy })
                  : scapedJSONStringfy(id)
              }
              isValidConnection={(connection) =>
                isValidConnection(connection, nodes, edges)
              }
              className={classNames(
                left ? "my-12 -ml-0.5 " : " my-12 -mr-0.5 ",
                "h-3 w-3 rounded-full border-2 bg-background",
                !showNode ? "mt-0" : "",
              )}
              style={{
                borderColor: color ?? nodeColors.unknown,
              }}
              onClick={() => {
                setFilterEdge(groupedEdge.current);
              }}
            ></Handle>
          </ShadTooltip>
        </div>
      </Button>
    )
  ) : (
    <div
      ref={ref}
      className={
        "relative mt-1 flex w-full flex-wrap items-center justify-between bg-muted px-5 py-2" +
        ((name === "code" && type === "code") ||
        (name.includes("code") && proxy)
          ? " hidden "
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
          <Case condition={!left && data.node?.frozen}>
            <div className="pr-1">
              <IconComponent className="h-5 w-5 text-ice" name={"Snowflake"} />
            </div>
          </Case>

          {proxy ? (
            <ShadTooltip content={<span>{proxy.id}</span>}>
              <span className={!left && data.node?.frozen ? " text-ice" : ""}>
                {title}
              </span>
            </ShadTooltip>
          ) : (
            <div className="flex gap-2">
              <span className={!left && data.node?.frozen ? " text-ice" : ""}>
                {title}
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
                    variant="none"
                    size="none"
                    disabled={!displayOutputPreview || unknownOutput}
                    onClick={() => setOpenOutputModal(true)}
                    data-testid={`output-inspection-${title.toLowerCase()}`}
                  >
                    <IconComponent
                      className={classNames(
                        "h-5 w-5 rounded-md",
                        displayOutputPreview && !unknownOutput
                          ? " hover:bg-secondary-foreground/5 hover:text-medium-indigo"
                          : " cursor-not-allowed text-muted-foreground",
                      )}
                      name={"ScanEye"}
                    />
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
          <Button className="h-7 truncate bg-muted p-0 text-sm font-normal text-black hover:bg-muted">
            <div className="flex">
              <ShadTooltip
                styleClasses={"tooltip-fixed-width custom-scroll nowheel"}
                delayDuration={1000}
                content={refHtml.current}
                side={left ? "left" : "right"}
              >
                <Handle
                  data-test-id={`handle-${title.toLowerCase()}-${
                    left ? "left" : "right"
                  }`}
                  type={left ? "target" : "source"}
                  position={left ? Position.Left : Position.Right}
                  key={scapedJSONStringfy(proxy ? { ...id, proxy } : id)}
                  id={scapedJSONStringfy(proxy ? { ...id, proxy } : id)}
                  isValidConnection={(connection) =>
                    isValidConnection(connection, nodes, edges)
                  }
                  className={classNames(
                    left ? "-ml-0.5" : "-mr-0.5",
                    "h-3 w-3 rounded-full border-2 bg-background",
                  )}
                  style={{ borderColor: color ?? nodeColors.unknown }}
                  onClick={() => setFilterEdge(groupedEdge.current)}
                />
              </ShadTooltip>
            </div>
          </Button>
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
                  "flex-grow"
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
              <div className="mt-2 flex w-full flex-col ">
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
                    setDb={(value) => {
                      setNode(data.id, (oldNode) => {
                        let newNode = cloneDeep(oldNode);
                        newNode.data = {
                          ...newNode.data,
                        };
                        newNode.data.node.template[name].load_from_db = value;
                        return newNode;
                      });
                    }}
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
          <div className="mt-2 w-full">
            <DictComponent
              disabled={disabled}
              editNode={false}
              value={
                !data.node!.template[name]?.value ||
                data.node!.template[name]?.value?.toString() === "{}"
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
                data.node!.template[name]?.value?.length === 0 ||
                !data.node!.template[name]?.value
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
            nodeId={data.id}
            setOpen={setOpenOutputModal}
          />
        )}
      </>
    </div>
  );
}
