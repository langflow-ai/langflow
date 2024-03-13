import { useState } from 'react';
import { Document, Page } from 'react-pdf'
import { pdfjs } from 'react-pdf';
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";
import IconComponent from "../genericIconComponent";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

export default function PdfViewer(): JSX.Element {

    const [numPages, setNumPages] = useState(-1);
    const [pageNumber, setPageNumber] = useState(1);

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages);
        setPageNumber(1);
    }

    function changePage(offset) {
        setPageNumber(prevPageNumber => prevPageNumber + offset);
    }

    function previousPage() {
        changePage(-1);
    }

    function nextPage() {
        changePage(1);
    }

    return (
        <div className="w-full h-full overflow-clip border-border border rounded-lg flex flex-col justify-end items-center">
            <div className={"w-full h-full min-h-0 overflow-auto custom-scroll"}>
                <Document onLoadSuccess={onDocumentLoadSuccess} file="https://vjudge.net/contest/614781/problemPrint/I"
                    className="w-full h-full flex">
                    <Page renderTextLayer pageNumber={pageNumber} className={"w-full h-full max-h-0"} />
                </Document>

            </div>
            <div className='absolute z-50 pb-5'>
                <div className=' bg-secondary w-min gap-0.5 rounded-xl px-2 flex align-middle justify-center items-center'>
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
                        {pageNumber || (numPages ? 1 : '--')}/{numPages || '--'}
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
                </div>
            </div>
        </div>);
}