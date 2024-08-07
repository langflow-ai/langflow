import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { ParameterRenderComponent } from "@/components/parameterRenderComponent";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { ReactNode, useEffect, useRef, useState } from "react";
import { default as IconComponent } from "../../../../components/genericIconComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import { LANGFLOW_SUPPORTED_TYPES } from "../../../../constants/constants";
import useFlowStore from "../../../../stores/flowStore";
import { useTypesStore } from "../../../../stores/typesStore";
import {
  NodeInputFieldComponentType,
  ParameterComponentType,
} from "../../../../types/components";
import { scapedJSONStringfy } from "../../../../utils/reactflowUtils";
import useFetchDataOnMount from "../../../hooks/use-fetch-data-on-mount";
import useHandleOnNewValue from "../../../hooks/use-handle-new-value";
import HandleRenderComponent from "../handleRenderComponent";

export default function NodeInputField({
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
}: NodeInputFieldComponentType): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const infoHtml = useRef<HTMLDivElement & ReactNode>(null);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const myData = useTypesStore((state) => state.data);
  const postTemplateValue = usePostTemplateValue({
    node: data.node!,
    nodeId: data.id,
    parameterId: name,
  });
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  const { handleNodeClass } = useHandleNodeClass(data.id);

  let disabled =
    edges.some(
      (edge) =>
        edge.targetHandle === scapedJSONStringfy(proxy ? { ...id, proxy } : id),
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

  useEffect(() => {
    if (optionalHandle && optionalHandle.length === 0) {
      optionalHandle = null;
    }
  }, [optionalHandle]);

  const displayHandle =
    !LANGFLOW_SUPPORTED_TYPES.has(type ?? "") || optionalHandle;

  return !showNode ? (
    displayHandle ? (
      <HandleRenderComponent
        left={true}
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
    ) : (
      <></>
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
        <div className="flex w-full items-center truncate text-sm">
          {proxy ? (
            <ShadTooltip content={<span>{proxy.id}</span>}>
              {<span>{title}</span>}
            </ShadTooltip>
          ) : (
            <div className="flex gap-2">
              <span>{<span>{title}</span>}</span>
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

        {displayHandle && (
          <HandleRenderComponent
            left={true}
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
      </>
    </div>
  );
}
