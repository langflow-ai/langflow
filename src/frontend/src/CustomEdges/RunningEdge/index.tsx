import { BezierEdge, EdgeProps } from "reactflow";

export default function SelfConnecting(props: EdgeProps) {
  return <BezierEdge {...props} />;
}
