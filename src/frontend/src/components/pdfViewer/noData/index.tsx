import { CHAT_FIRST_INITIAL_TEXT, CHAT_SECOND_INITIAL_TEXT, PDFErrorTitle, PDFLoadError } from "../../../constants/constants";
import IconComponent from "../../genericIconComponent";


export default function NoDataPdf(): JSX.Element {
    return (
        <div className="flex flex-col items-center justify-center h-full w-full bg-muted">
            <div className="chat-alert-box">
              <span>
              📄 <span className="langflow-chat-span">{~PDFErrorTitle}</span>
              </span>
              <br />
              <div className="langflow-chat-desc">
                <span className="langflow-chat-desc-span">
                  {PDFLoadError}{" "}
                </span>
              </div>
            </div>

        </div>
    );
}