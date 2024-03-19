import { CHAT_FIRST_INITIAL_TEXT, CHAT_SECOND_INITIAL_TEXT, PDFCheckFlow, PDFLoadErrorTitle } from "../../../constants/constants";
import IconComponent from "../../genericIconComponent";


export default function Error(): JSX.Element {
    return (
        <div className="flex flex-col items-center justify-center h-full w-full bg-muted">
            <div className="chat-alert-box">
                <span className="flex gap-2">
                    <IconComponent name="FileX2" />
                    <span className="langflow-chat-span">{PDFLoadErrorTitle}</span>
                </span>
                <br />
                <div className="langflow-chat-desc">
                    <span className="langflow-chat-desc-span">
                        {PDFCheckFlow}{" "}
                    </span>
                </div>
            </div>

        </div>
    );
}