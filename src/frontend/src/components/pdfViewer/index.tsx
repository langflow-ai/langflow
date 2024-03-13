import { useState } from 'react';
import { Document, Page } from 'react-pdf'
import { pdfjs } from 'react-pdf';
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";

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

    return <div className={"w-full h-full min-h-0 overflow-auto custom-scroll"}>
        <Document onLoadSuccess={onDocumentLoadSuccess} file="https://vjudge.net/contest/614781/problemPrint/I" className="w-full h-full max-w-full max-h-full">
            <Page renderTextLayer pageNumber={pageNumber} className={"w-full h-full max-w-full max-h-full"} />
        </Document>
        <div>
            <p>
                Page {pageNumber || (numPages ? 1 : '--')} of {numPages || '--'}
            </p>
            <button
                type="button"
                disabled={pageNumber <= 1}
                onClick={previousPage}
            >
                Previous
            </button>
            <button
                type="button"
                disabled={pageNumber >= numPages}
                onClick={nextPage}
            >
                Next
            </button>
        </div>

    </div>;
}