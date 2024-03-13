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

  useEffect(() => {
    try {
      if (viewerRef.current) {
        // Initialize OpenSeadragon viewer
        const viewer = OpenSeadragon({
          element: viewerRef.current,
          prefixUrl: 'https://cdnjs.cloudflare.com/ajax/libs/openseadragon/2.4.2/images/', // Optional: Set the path to OpenSeadragon images
          tileSources: {type: 'image', url: 'https://sm.ign.com/t/ign_br/screenshot/default/gojo-1_tmqy.1200.jpg'},
          defaultZoomLevel: 1,
          maxZoomPixelRatio: 4,
          showNavigationControl: false,
        });

        const zoomInButton = document.getElementById('zoom-in-button');
    const zoomOutButton = document.getElementById('zoom-out-button');
    const homeButton = document.getElementById('home-button');
    const fullPageButton = document.getElementById('full-page-button');

    zoomInButton!.addEventListener('click', () => viewer.viewport.zoomBy(1.2));
    zoomOutButton!.addEventListener('click', () => viewer.viewport.zoomBy(0.8));
    homeButton!.addEventListener('click', () => viewer.viewport.goHome());
    fullPageButton!.addEventListener('click', () => viewer.setFullScreen(true));
  
        // Optionally, you can set additional viewer options here
  
        // Cleanup function
        return () => {
          viewer.destroy();
          zoomInButton!.removeEventListener('click', () => viewer.viewport.zoomBy(1.2));
    zoomOutButton!.removeEventListener('click', () => viewer.viewport.zoomBy(0.8));
    homeButton!.removeEventListener('click', () => viewer.viewport.goHome());
    fullPageButton!.removeEventListener('click', () => viewer.setFullScreen(true));
        };
      }
    } catch (error) {
      console.error('Error initializing OpenSeadragon:', error);
    }
  }, [imageMock]);

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
          <>
          <div ref={viewerRef} className="w-full h-full" />
          <div className="shadow-round-btn-shadow hover:shadow-round-btn-shadow flex items-center justify-center rounded-sm  border bg-muted shadow-md transition-all">
            <button id="zoom-in-button" className="relative inline-flex w-full items-center justify-center px-5 py-3 text-sm font-semibold transition-all w-full transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
              <ForwardedIconComponent
                name="ZoomIn"
                className={"text-secondary-foreground w-5 h-5"}
              />
            </button>
            <div>
              <Separator orientation="vertical" />
            </div>
            <button id="zoom-out-button" className="relative inline-flex w-full items-center justify-center px-5 py-3 text-sm font-semibold transition-all transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
              <ForwardedIconComponent
                name="ZoomOut"
                className={"text-secondary-foreground w-5 h-5"}
              />
            </button>
            <div>
              <Separator orientation="vertical" />
            </div>
            <button id="home-button" className="relative inline-flex w-full items-center justify-center px-5 py-3 text-sm font-semibold transition-all transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
              <ForwardedIconComponent
                name="RotateCcw"
                className={"text-secondary-foreground w-5 h-5"}
              />
            </button>
            <div>
              <Separator orientation="vertical" />
            </div>
            <button id="full-page-button" className="relative inline-flex w-full items-center justify-center px-5 py-3 text-sm font-semibold transition-all transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
              <ForwardedIconComponent
                name="Maximize2"
                className={"text-secondary-foreground w-5 h-5"}
              />
            </button>
            <div>
              <Separator orientation="vertical" />
            </div>
            <button id="full-page-button" className="relative inline-flex w-full items-center justify-center px-5 py-3 text-sm font-semibold transition-all transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
              <ForwardedIconComponent
                name="ArrowDownToLine"
                className={"text-secondary-foreground w-5 h-5"}
              />
            </button>

          </div>
          </>
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
