import RecordsOutputComponent from "../../../../../../components/recordsOutputComponent";
import { Case } from "../../../../../../shared/components/caseComponent";
import TextOutputView from "../../../../../../shared/components/textOutputView";
import useFlowStore from "../../../../../../stores/flowStore";
import { convertToTableRows } from "./helpers/convert-to-table-rows";

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
  const resultMessage = results?.message;

  console.log("results", resultMessage);

  return (
    <>
      <Case condition={!flowPoolNode}>
        <div>NO OUTPUT</div>
      </Case>

      <Case condition={node && resultType === "text"}>
        <TextOutputView left={false} value={resultMessage} />
      </Case>

      <Case condition={resultType === "record"}>
        <RecordsOutputComponent
          rows={[resultMessage] ?? []}
          pagination={true}
          columnMode="union"
        />
      </Case>

      <Case condition={resultType === "object"}>
        <RecordsOutputComponent
          rows={convertToTableRows(resultMessage)}
          pagination={true}
          columnMode="union"
        />
      </Case>
    </>
  );
}
