import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "../genericIconComponent";
import useFlowStore from "../../stores/flowStore";
import OpenSeadragon from 'openseadragon';
import { Separator } from "../ui/separator";
import { saveAs } from 'file-saver'
import useAlertStore from "../../stores/alertStore";
import { IMGViewErrorMSG, IMGViewErrorTitle } from "../../constants/constants";

export default function ImageViewer({image }) {
  const viewerRef = useRef(null);
  const [errorDownloading, setErrordownloading] = useState(false)
  const setErrorList = useAlertStore(state => state.setErrorData);
  const [initialMsg, setInicialMsg] = useState("Please build your flow");


    useEffect(() => {
        try {
          if (viewerRef.current) {
            // Initialize OpenSeadragon viewer
            const viewer = OpenSeadragon({
              element: viewerRef.current,
              prefixUrl: 'https://cdnjs.cloudflare.com/ajax/libs/openseadragon/2.4.2/images/', // Optional: Set the path to OpenSeadragon images
              tileSources: {type: 'image', url: image},
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
      }, [image]);

      function download() {
        const imageUrl = image;
        // Fetch the image data
        fetch(imageUrl)
            .then(response => response.blob())
            .then(blob => {
                // Save the image using FileSaver.js
                saveAs(blob, 'image.jpg');
            })
            .catch(error => {
              setErrorList({title: "There was an error downloading your image"})
              console.error('Error downloading image:', error)
            });
      }

    return (
        image === "" ? (
          <div className="w-full h-full bg-muted rounded-md flex align-center justify-center flex-col  gap-5 border border-border">
              <div className="flex gap-2 align-center justify-center ">
                <ForwardedIconComponent
                  name="Image"
                />
                {IMGViewErrorTitle}
              </div>
              <div className="flex align-center justify-center">
                <div className="langflow-chat-desc flex align-center justify-center">
                  <div className="langflow-chat-desc-span">
                    {IMGViewErrorMSG}
                  </div>
                </div>
              </div>
          </div>
        ) : (
          <>
          <div className="w-full flex align-center justify-center my-2 mb-4">
            <div className="shadow-round-btn-shadow hover:shadow-round-btn-shadow flex items-center justify-center rounded-sm  border bg-muted shadow-md transition-all w-[50%]">
              <button id="zoom-in-button" className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all w-full transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
                <ForwardedIconComponent
                  name="ZoomIn"
                  className={"text-secondary-foreground w-5 h-5"}
                />
              </button>
              <div>
                <Separator orientation="vertical" />
              </div>
              <button id="zoom-out-button" className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
                <ForwardedIconComponent
                  name="ZoomOut"
                  className={"text-secondary-foreground w-5 h-5"}
                />
              </button>
              <div>
                <Separator orientation="vertical" />
              </div>
              <button id="home-button" className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
                <ForwardedIconComponent
                  name="RotateCcw"
                  className={"text-secondary-foreground w-5 h-5"}
                />
              </button>
              <div>
                <Separator orientation="vertical" />
              </div>
              <button id="full-page-button" className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
                <ForwardedIconComponent
                  name="Maximize2"
                  className={"text-secondary-foreground w-5 h-5"}
                />
              </button>
              <div>
                <Separator orientation="vertical" />
              </div>
              
                <button onClick={download} className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all transition-all duration-500 ease-in-out ease-in-out hover:bg-hover">
                    <ForwardedIconComponent
                    name="ArrowDownToLine"
                    className={"text-secondary-foreground w-5 h-5"}
                    />
                </button>
              
            </div>
          </div>
          <div id="canvas" ref={viewerRef} className={`w-full h-[90%] `} />
          </>
        )
    );
}