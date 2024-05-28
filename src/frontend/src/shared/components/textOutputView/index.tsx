import { Textarea } from "../../../components/ui/textarea";

const TextOutputView = ({ left, node, flowPool }) => {
  return (
    <>
      <Textarea
        className={`w-full custom-scroll ${left ? " min-h-32" : " h-full"}`}
        placeholder={"Empty"}
        // update to real value on flowPool
        value={
          (flowPool[node.id] ?? [])[(flowPool[node.id]?.length ?? 1) - 1]?.data
            .results.result ?? ""
        }
        readOnly
      />
    </>
  );
};

export default TextOutputView;
