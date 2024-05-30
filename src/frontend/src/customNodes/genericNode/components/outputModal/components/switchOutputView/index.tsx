import RecordsOutputComponent from "../../../../../../components/recordsOutputComponent";
import { Case } from "../../../../../../shared/components/caseComponent";
import TextOutputView from "../../../../../../shared/components/textOutputView";
import useFlowStore from "../../../../../../stores/flowStore";

export default function SwitchOutputView(nodeId): JSX.Element {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const node = nodes.find((node) => node?.id === nodeId?.nodeId);

  const flowPoolNode = (flowPool[node!.id] ?? [])[
    (flowPool[node!.id]?.length ?? 1) - 1
  ];

  const results = flowPoolNode?.data?.logs[0] ?? "";

  const checkType = () => {
    const typeOutput = typeof results;
    return typeOutput;
  };

  return (
    <>
      <Case condition={!flowPoolNode}>
        <div>NO OUTPUT</div>
      </Case>

      <Case condition={node && checkType() === "object"}>
        <TextOutputView left={false} flowPool={flowPool} node={node} vaç />
      </Case>

      <Case condition={node && Array.isArray(results)}>
        <RecordsOutputComponent
          flowPoolObject={flowPoolNode}
          pagination={true}
        />
      </Case>
    </>
  );
}
