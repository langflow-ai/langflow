import { useState } from 'react';
import { Document, Page } from 'react-pdf'
import { pdfjs } from 'react-pdf';
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";
import IconComponent from "../genericIconComponent";
import LoadingComponent from '../loadingComponent';
import Loading from '../ui/loading';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

export default function PdfViewer(): JSX.Element {

    const [numPages, setNumPages] = useState(-1);
    const [pageNumber, setPageNumber] = useState(1);
    const [scale, setScale] = useState(1);
    const [showControl, setShowControl] = useState(false);

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

    //set handle scale in % to real number
    function handleScaleChange(e) {
        //check if e is a number
        if (isNaN(e) || e<0.1) return;
        // round to 2 decimal places
        e = Math.round(e * 10) / 10;

        setScale(e);
    }

    function zoomIn() {
        handleScaleChange(scale +0.1);
    }
    function zoomOut() {
        if(scale>0.1) handleScaleChange(scale -0.1);
    }

    return (
        <div onMouseEnter={_ => setShowControl(true)} onMouseLeave={_ => setShowControl(false)} className="w-full h-full overflow-clip border-border border rounded-lg flex flex-col justify-end items-center">
            <div className={"w-full h-full min-h-0 overflow-auto custom-scroll"}>
                <Document loading={
                    <div className="w-full h-full flex justify-center items-center align-middle">
                        <Loading />
                    </div>
                } onLoadSuccess={onDocumentLoadSuccess} file="https://vjudge.net/contest/614781/problemPrint/I"
                    className="w-full h-full">
                    <Page scale={scale} renderTextLayer pageNumber={pageNumber} className={"w-full h-full max-h-0"} />
                </Document>

            </div>
            <div className={'absolute z-50 pb-5 ' + ((showControl && numPages>0) ? "" : " hidden")}>
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
                    <p className='px-2'>|</p>
                    <button
                        type="button"
                        onClick={zoomOut}
                    >
                        <IconComponent
                            name={"ZoomOut"}
                            className="h-6 w-6"
                        ></IconComponent>
                    </button>
                    <input type='number' step={0.1} className='w-6 bg-transparent border-b text-center arrow-hide' 
                    onChange={(e)=>handleScaleChange(e.target.value)} value={scale}/>
                    <button
                        type="button"
                        onClick={zoomIn}
                    >
                        <IconComponent
                            name={"ZoomIn"}
                            className="h-6 w-6"
                        ></IconComponent>
                    </button>
                </div>
            </div>
        </div>);
}