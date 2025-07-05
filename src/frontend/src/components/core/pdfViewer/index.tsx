import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import IconComponent from "../../common/genericIconComponent";
import Loading from "../../ui/loading";
import Error from "./Error";
import NoDataPdf from "./noData";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

export default function PdfViewer({ pdf }: { pdf: string }): JSX.Element {
  const [numPages, setNumPages] = useState(-1);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1);
  const [width, setWidth] = useState<number | undefined>(undefined);
  const [showControl, setShowControl] = useState(false);
  const container = useRef<null | HTMLDivElement>(null);

  //shortcuts to change page
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "ArrowLeft") {
        if (pageNumber > 1) previousPage();
      } else if (event.key === "ArrowRight") {
        if (pageNumber < numPages) nextPage();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [pageNumber]);

  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    setPageNumber(1);
  }

  function changePage(offset) {
    setPageNumber((prevPageNumber) => prevPageNumber + offset);
  }

  function previousPage() {
    changePage(-1);
  }

  function nextPage() {
    changePage(1);
  }

  //set handle scale in % to real number
  function handleScaleChange(e) {
    //check if e is a number
    if (isNaN(e) || e < 0.1) return;
    // round to 2 decimal places
    e = Math.round(e * 10) / 10;

    setScale(e);
  }

  function zoomIn() {
    handleScaleChange(scale + 0.1);
  }
  function zoomOut() {
    if (scale > 0.1) handleScaleChange(scale - 0.1);
  }

  function handlePageLoad(page) {
    if (!container.current) return;
    const containerWidth = container.current.clientWidth;
    const pageWidth = page.width;
    if (containerWidth > pageWidth) {
      setWidth(containerWidth - 10);
    }
  }

  return (
    <div
      ref={container}
      onMouseEnter={(_) => setShowControl(true)}
      onMouseLeave={(_) => setShowControl(false)}
      className="flex h-full w-full flex-col items-center justify-end overflow-clip rounded-lg border border-border"
    >
      <div className={"h-full min-h-0 w-full overflow-auto custom-scroll"}>
        <Document
          loading={
            <div className="flex h-full w-full items-center justify-center align-middle">
              <Loading />
            </div>
          }
          onLoadSuccess={onDocumentLoadSuccess}
          file={pdf}
          noData={<NoDataPdf />}
          error={<Error />}
          className="h-full w-full"
        >
          <Page
            width={width}
            onLoadSuccess={handlePageLoad}
            scale={scale}
            renderTextLayer
            pageNumber={pageNumber}
            className={"h-full max-h-0 w-full"}
          />
        </Document>
      </div>
      <div
        className={
          "absolute z-50 pb-5 " + (showControl && numPages > 0 ? "" : " hidden")
        }
      >
        <div className="flex w-min items-center justify-center gap-0.5 rounded-xl bg-muted px-2 align-middle">
          <button
            type="button"
            disabled={pageNumber <= 1}
            onClick={previousPage}
          >
            <IconComponent
              name={"ChevronLeft"}
              className="h-6 w-6"
            ></IconComponent>
          </button>
          <p>
            {pageNumber || (numPages ? 1 : "--")}/{numPages || "--"}
          </p>
          <button
            type="button"
            disabled={pageNumber >= numPages}
            onClick={nextPage}
          >
            <IconComponent
              name={"ChevronRight"}
              className="h-6 w-6"
            ></IconComponent>
          </button>
          <p className="px-2">|</p>
          <button type="button" onClick={zoomOut}>
            <IconComponent name={"ZoomOut"} className="h-6 w-6"></IconComponent>
          </button>
          <input
            type="number"
            step={0.1}
            className="w-6 border-b bg-transparent text-center arrow-hide"
            onChange={(e) => handleScaleChange(e.target.value)}
            value={scale}
          />
          <button type="button" onClick={zoomIn}>
            <IconComponent name={"ZoomIn"} className="h-6 w-6"></IconComponent>
          </button>
        </div>
      </div>
    </div>
  );
}
