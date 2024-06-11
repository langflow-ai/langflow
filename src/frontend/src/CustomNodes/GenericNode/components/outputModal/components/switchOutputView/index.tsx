import ForwardedIconComponent from "../../../../../../components/genericIconComponent";
import RecordsOutputComponent from "../../../../../../components/recordsOutputComponent";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../../../../components/ui/alert";
import { Case } from "../../../../../../shared/components/caseComponent";
import TextOutputView from "../../../../../../shared/components/textOutputView";
import useFlowStore from "../../../../../../stores/flowStore";
import ErrorOutput from "./components";

export default function SwitchOutputView(nodeId): JSX.Element {
  const nodeIdentity = nodeId.nodeId;

  const nodes = useFlowStore((state) => state.nodes);
  const flowPool = useFlowStore((state) => state.flowPool);
  const node = nodes.find((node) => node?.id === nodeIdentity);

  const flowPoolNode = (flowPool[nodeIdentity] ?? [])[
    (flowPool[nodeIdentity]?.length ?? 1) - 1
  ];

  const results = flowPoolNode?.data?.logs[0] ?? "";
  const resultType = results?.type;
  let resultMessage = results?.message;
  const RECORD_TYPES = ["record", "object", "array", "message"];
  if (resultMessage.raw) {
    resultMessage = resultMessage.raw;
  }

  return (
    <>
      <Case condition={!resultType || resultType === "unknown"}>
        <div>NO OUTPUT</div>
      </Case>
      <Case condition={resultType === "ValueError"}>
        <ErrorOutput value={resultMessage}></ErrorOutput>
      </Case>

      <Case condition={node && resultType === "text"}>
        <TextOutputView left={false} value={resultMessage} />
      </Case>

      <Case condition={RECORD_TYPES.includes(resultType)}>
        <RecordsOutputComponent
          rows={
            Array.isArray(resultMessage)
              ? (resultMessage as Array<any>).every((item) => item.data)
                ? (resultMessage as Array<any>).map((item) => item.data)
                : resultMessage
              : [resultMessage]
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
  );
}
