import { PDFErrorTitle, PDFLoadError } from "../../../../constants/constants";

export default function NoDataPdf(): JSX.Element {
  return (
    <div className="bg-muted flex h-full w-full flex-col items-center justify-center">
      <div className="chat-alert-box">
        <span>
          📄 <span className="langflow-chat-span">{PDFErrorTitle}</span>
        </span>
        <br />
        <div className="langflow-chat-desc">
          <span className="langflow-chat-desc-span">{PDFLoadError} </span>
        </div>
      </div>
    </div>
  );
}
