import { saveAs } from "file-saver";
import OpenSeadragon from "openseadragon";
import { useEffect, useRef, useState } from "react";
import {
  IMGViewErrorMSG,
  IMGViewErrorTitle,
} from "../../../constants/constants";
import useAlertStore from "../../../stores/alertStore";
import { Separator } from "../../ui/separator";
import ForwardedIconComponent from "../genericIconComponent";

export default function ImageViewer({ image }: { image: string }) {
  const viewerRef = useRef(null);
  const [_errorDownloading, _setErrordownloading] = useState(false);
  const setErrorList = useAlertStore((state) => state.setErrorData);
  const [_initialMsg, _setInicialMsg] = useState("Please build your flow");

  useEffect(() => {
    try {
      if (viewerRef.current) {
        // Initialize OpenSeadragon viewer
        const viewer = OpenSeadragon({
          element: viewerRef.current,
          prefixUrl:
            "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/2.4.2/images/", // Optional: Set the path to OpenSeadragon images
          tileSources: { type: "image", url: image },
          defaultZoomLevel: 1,
          maxZoomPixelRatio: 4,
          showNavigationControl: false,
        });
        const zoomInButton = document.getElementById("zoom-in-button");
        const zoomOutButton = document.getElementById("zoom-out-button");
        const homeButton = document.getElementById("home-button");
        const fullPageButton = document.getElementById("full-page-button");

        zoomInButton!.addEventListener("click", () =>
          viewer.viewport.zoomBy(1.2),
        );
        zoomOutButton!.addEventListener("click", () =>
          viewer.viewport.zoomBy(0.8),
        );
        homeButton!.addEventListener("click", () => viewer.viewport.goHome());
        fullPageButton!.addEventListener("click", () =>
          viewer.setFullScreen(true),
        );

        // Optionally, you can set additional viewer options here

        // Cleanup function
        return () => {
          viewer.destroy();
          zoomInButton!.removeEventListener("click", () =>
            viewer.viewport.zoomBy(1.2),
          );
          zoomOutButton!.removeEventListener("click", () =>
            viewer.viewport.zoomBy(0.8),
          );
          homeButton!.removeEventListener("click", () =>
            viewer.viewport.goHome(),
          );
          fullPageButton!.removeEventListener("click", () =>
            viewer.setFullScreen(true),
          );
        };
      }
    } catch (error) {
      console.error("Error initializing OpenSeadragon:", error);
    }
  }, [image]);

  function download() {
    const imageUrl = image;
    // Fetch the image data
    fetch(imageUrl)
      .then((response) => response.blob())
      .then((blob) => {
        // Save the image using FileSaver.js
        saveAs(blob, "image.jpg");
      })
      .catch((error) => {
        setErrorList({ title: "There was an error downloading your image" });
        console.error("Error downloading image:", error);
      });
  }

  return image === "" ? (
    <div className="align-center flex h-full w-full flex-col justify-center gap-5 rounded-md border border-border bg-muted">
      <div className="align-center flex justify-center gap-2">
        <ForwardedIconComponent name="Image" />
        {IMGViewErrorTitle}
      </div>
      <div className="align-center flex justify-center">
        <div className="langflow-chat-desc align-center flex justify-center">
          <div className="langflow-chat-desc-span">{IMGViewErrorMSG}</div>
        </div>
      </div>
    </div>
  ) : (
    <>
      <div className="align-center my-2 mb-4 flex w-full justify-center">
        <div className="shadow-round-btn-shadow hover:shadow-round-btn-shadow flex w-[50%] items-center justify-center rounded-sm border bg-muted shadow-md transition-all">
          <button
            id="zoom-in-button"
            className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all duration-500 ease-in-out hover:bg-hover"
          >
            <ForwardedIconComponent
              name="ZoomIn"
              className={"h-5 w-5 text-secondary-foreground"}
            />
          </button>
          <div>
            <Separator orientation="vertical" />
          </div>
          <button
            id="zoom-out-button"
            className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all duration-500 ease-in-out hover:bg-hover"
          >
            <ForwardedIconComponent
              name="ZoomOut"
              className={"h-5 w-5 text-secondary-foreground"}
            />
          </button>
          <div>
            <Separator orientation="vertical" />
          </div>
          <button
            id="home-button"
            className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all duration-500 ease-in-out hover:bg-hover"
          >
            <ForwardedIconComponent
              name="RotateCcw"
              className={"h-5 w-5 text-secondary-foreground"}
            />
          </button>
          <div>
            <Separator orientation="vertical" />
          </div>
          <button
            id="full-page-button"
            className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all duration-500 ease-in-out hover:bg-hover"
          >
            <ForwardedIconComponent
              name="Maximize2"
              className={"h-5 w-5 text-secondary-foreground"}
            />
          </button>
          <div>
            <Separator orientation="vertical" />
          </div>

          <button
            onClick={download}
            className="relative inline-flex w-full items-center justify-center px-3 py-3 text-sm font-semibold transition-all duration-500 ease-in-out hover:bg-hover"
          >
            <ForwardedIconComponent
              name="ArrowDownToLine"
              className={"h-5 w-5 text-secondary-foreground"}
            />
          </button>
        </div>
      </div>
      <div id="canvas" ref={viewerRef} className={`h-[90%] w-full`} />
    </>
  );
}
