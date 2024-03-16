import { cloneDeep } from "lodash";
import useFlowStore from "../../stores/flowStore";
import { IOOutputProps } from "../../types/components";
import { Textarea } from "../ui/textarea";
import OpenSeadragon from 'openseadragon';
import { useEffect, useRef } from "react";
import imageMock from "./mocks/image.png";
import { element } from "prop-types";
import { style } from "d3-selection";
import ForwardedIconComponent from "../genericIconComponent";
import { Separator } from "../ui/separator";
import ImageViewer from "../ImageViewer";

const buttonStyles = {
  backgroundColor: 'blue-500',
  color: 'white',
  padding: '2',
  borderRadius: 'rounded',
  cursor: 'pointer',
};

export default function IOOutputView({
  outputType,
  outputId,
  left,
}: IOOutputProps): JSX.Element | undefined {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const node = nodes.find((node) => node.id === outputId);
  const buttonClasses = 'bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded';
  const viewerRef = useRef(null);

  function handleOutputType() {
    if (!node) return <>"No node found!"</>;
    switch (outputType) {
      case "TextOutput":
        return (
          <Textarea
            className={`w-full custom-scroll ${left ? "" : " h-full"}`}
            placeholder={"Empty"}
            // update to real value on flowPool
            value={
              (flowPool[node.id] ?? [])[(flowPool[node.id]?.length ?? 1) - 1]
                ?.params ?? ""
            }
            readOnly
          />
        );

      case "ImageOutput":
        return (
          left ? (
            <div>Expand the view to see the image</div>
          ) : (
            <ImageViewer image={"https://sm.ign.com/t/ign_br/screenshot/default/gojo-1_tmqy.1200.jpg"} />
          )
        ) 

      default:
        return (
          <Textarea
            className="w-full custom-scroll"
            placeholder={"Enter text..."}
            value={node.data.node!.template["input_value"]}
            onChange={(e) => {
              e.target.value;
              if (node) {
                let newNode = cloneDeep(node);
                newNode.data.node!.template["input_value"].value =
                  e.target.value;
                setNode(node.id, newNode);
              }
            }}
          />
        );
    }
  }
  return handleOutputType();
}
