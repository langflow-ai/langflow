import { useMemo } from "react";
import JsonOutputViewComponent from "@/components/core/jsonOutputComponent/json-output-view";
import { MAX_TEXT_LENGTH } from "@/constants/constants";
import type { LogsLogType, OutputLogType } from "@/types/api";
import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import DataOutputComponent from "../../../../../../components/core/dataOutputComponent";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../../../../components/ui/alert";
import { Case } from "../../../../../../shared/components/caseComponent";
import TextOutputView from "../../../../../../shared/components/textOutputView";
import useFlowStore from "../../../../../../stores/flowStore";
import ErrorOutput from "./components";

// Define the props type
interface SwitchOutputViewProps {
  nodeId: string;
  outputName: string;
  type: "Outputs" | "Logs";
}

const SwitchOutputView: React.FC<SwitchOutputViewProps> = ({
  nodeId,
  outputName,
  type,
}) => {
  const flowPool = useFlowStore((state) => state.flowPool);
  const nodes = useFlowStore((state) => state.nodes);

  const flowPoolNode = (flowPool[nodeId] ?? [])[
    (flowPool[nodeId]?.length ?? 1) - 1
  ];

  // Get the node to access output configuration
  const currentNode = nodes.find((node) => node.id === nodeId);
  const outputConfig = currentNode?.data?.node?.outputs?.find(
    (output) => output.name === outputName,
  );

  // Check if this is a Tool output
  const isToolOutput =
    outputConfig &&
    (outputConfig.method === "to_toolkit" ||
      (outputConfig.types && outputConfig.types.includes("Tool")));

  const results: OutputLogType | LogsLogType =
    (type === "Outputs"
      ? flowPoolNode?.data?.outputs?.[outputName]
      : flowPoolNode?.data?.logs?.[outputName]) ?? {};
  const resultType = results?.type;
  let resultMessage = results?.message ?? {};
  const RECORD_TYPES = ["array", "message"];
  const JSON_TYPES = ["data", "object"];
  if (resultMessage?.raw) {
    resultMessage = resultMessage.raw;
  }

  const resultMessageMemoized = useMemo(() => {
    if (!resultMessage) return "";

    if (
      typeof resultMessage === "string" &&
      resultMessage.length > MAX_TEXT_LENGTH
    ) {
      return `${resultMessage.substring(0, MAX_TEXT_LENGTH)}...`;
    }
    if (Array.isArray(resultMessage)) {
      return resultMessage.map((item) => {
        if (item?.data && typeof item?.data === "object") {
          const truncatedData = Object.fromEntries(
            Object.entries(item?.data).map(([key, value]) => {
              if (typeof value === "string" && value.length > MAX_TEXT_LENGTH) {
                return [key, `${value.substring(0, MAX_TEXT_LENGTH)}...`];
              }
              return [key, value];
            }),
          );
          return { ...item, data: truncatedData };
        }
        return item;
      });
    }

    return resultMessage;
  }, [resultMessage]);

  // Custom component for Tool output display
  const ToolOutputDisplay = ({ tools }) => {
    if (!Array.isArray(tools) || tools.length === 0) {
      return <div>No tools available</div>;
    }

    return (
      <div className="space-y-4">
        {tools?.map((tool, index) => (
          <div key={index} className="border rounded-lg p-4 bg-muted/20">
            <div
              data-testid="tool_name"
              className={
                "font-medium text-lg" + (tool?.description ? " mb-2" : "")
              }
            >
              {tool.name || `Tool ${index + 1}`}
            </div>
            {tool?.description && (
              <div
                data-testid="tool_description"
                className="text-sm text-muted-foreground mb-3"
              >
                {tool.description}
              </div>
            )}
            {tool?.tags && tool?.tags?.length > 0 && (
              <div data-testid="tool_tags" className="flex flex-wrap gap-2">
                {tool.tags.map((tag, tagIndex) => (
                  <span
                    key={tagIndex}
                    className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-primary/10 text-primary"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return type === "Outputs" ? (
    <>
      <Case condition={isToolOutput && resultMessageMemoized}>
        <ToolOutputDisplay
          tools={
            Array.isArray(resultMessageMemoized)
              ? resultMessageMemoized
              : [resultMessageMemoized]
          }
        />
      </Case>
      <Case
        condition={(!resultType || resultType === "unknown") && !isToolOutput}
      >
        <div>NO OUTPUT</div>
      </Case>
      <Case
        condition={
          (resultType === "error" || resultType === "ValueError") &&
          !isToolOutput
        }
      >
        <ErrorOutput
          value={`${resultMessageMemoized?.errorMessage}\n\n${resultMessageMemoized?.stackTrace}`}
        />
      </Case>

      <Case condition={resultType === "text" && !isToolOutput}>
        <TextOutputView left={false} value={resultMessageMemoized} />
      </Case>

      <Case condition={RECORD_TYPES.includes(resultType) && !isToolOutput}>
        <DataOutputComponent
          rows={
            Array.isArray(resultMessageMemoized)
              ? (resultMessageMemoized as Array<any>).every(
                  (item) => item?.data,
                )
                ? (resultMessageMemoized as Array<any>).map(
                    (item) => item?.data,
                  )
                : resultMessageMemoized
              : Object.keys(resultMessageMemoized)?.length > 0
                ? [resultMessageMemoized]
                : []
          }
          pagination={true}
          columnMode="union"
        />
      </Case>
      <Case condition={JSON_TYPES.includes(resultType) && !isToolOutput}>
        <JsonOutputViewComponent
          nodeId={nodeId}
          outputName={outputName}
          data={resultMessageMemoized}
        />
      </Case>

      <Case condition={resultType === "stream" && !isToolOutput}>
        <div className="flex h-full w-full items-center justify-center align-middle">
          <Alert variant={"default"} className="w-fit">
            <ForwardedIconComponent
              name="AlertCircle"
              className="h-5 w-5 text-primary"
            />
            <AlertTitle>{"Streaming is not supported"}</AlertTitle>
            <AlertDescription>
              {
                "Use the playground to interact with components that stream data"
              }
            </AlertDescription>
          </Alert>
        </div>
      </Case>
    </>
  ) : (
    <DataOutputComponent
      rows={
        Array.isArray(results)
          ? (results as Array<any>).every((item) => item?.data)
            ? (results as Array<any>).map((item) => item?.data)
            : results
          : Object.keys(results)?.length > 0
            ? [results]
            : []
      }
      pagination={true}
      columnMode="union"
    />
  );
};

export default SwitchOutputView;
