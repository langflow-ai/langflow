import { MAX_TEXT_LENGTH } from "@/constants/constants";
import { LogsLogType, OutputLogType } from "@/types/api";
import { useMemo } from "react";
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
  const flowPoolNode = (flowPool[nodeId] ?? [])[
    (flowPool[nodeId]?.length ?? 1) - 1
  ];
  let results: OutputLogType | LogsLogType =
    (type === "Outputs"
      ? flowPoolNode?.data?.outputs[outputName]
      : flowPoolNode?.data?.logs[outputName]) ?? {};
  const resultType = results?.type;
  let resultMessage = results?.message ?? {};
  const RECORD_TYPES = ["data", "object", "array", "message"];
  if (resultMessage?.raw) {
    resultMessage = resultMessage.raw;
  }

  const resultMessageMemoized = useMemo(() => {
    if (
      typeof resultMessage === "string" &&
      resultMessage.length > MAX_TEXT_LENGTH
    ) {
      resultMessage = `${resultMessage.substring(0, MAX_TEXT_LENGTH)}...`;
    }

    if (Array.isArray(resultMessage)) {
      resultMessage = resultMessage.map((item) => {
        if (item && typeof item.data === "object") {
          const truncatedData = Object.fromEntries(
            Object.entries(item.data).map(([key, value]) => {
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

  return type === "Outputs" ? (
    <>
      <Case condition={!resultType || resultType === "unknown"}>
        <div>NO OUTPUT</div>
      </Case>
      <Case condition={resultType === "error" || resultType === "ValueError"}>
        <ErrorOutput
          value={`${resultMessageMemoized.errorMessage}\n\n${resultMessageMemoized.stackTrace}`}
        ></ErrorOutput>
      </Case>

      <Case condition={resultType === "text"}>
        <TextOutputView left={false} value={resultMessageMemoized} />
      </Case>

      <Case condition={RECORD_TYPES.includes(resultType)}>
        <DataOutputComponent
          rows={
            Array.isArray(resultMessageMemoized)
              ? (resultMessageMemoized as Array<any>).every((item) => item.data)
                ? (resultMessageMemoized as Array<any>).map((item) => item.data)
                : resultMessageMemoized
              : Object.keys(resultMessageMemoized).length > 0
                ? [resultMessageMemoized]
                : []
          }
          pagination={true}
          columnMode="union"
        />
      </Case>

      <Case condition={resultType === "stream"}>
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
          ? (results as Array<any>).every((item) => item.data)
            ? (results as Array<any>).map((item) => item.data)
            : results
          : Object.keys(results).length > 0
            ? [results]
            : []
      }
      pagination={true}
      columnMode="union"
    />
  );
};

export default SwitchOutputView;
