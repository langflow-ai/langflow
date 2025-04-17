import {
  PDFCheckFlow,
  PDFLoadErrorTitle,
} from "../../../../constants/constants";
import IconComponent from "../../../common/genericIconComponent";

export default function Error(): JSX.Element {
  return (
    <div className="bg-muted flex h-full w-full flex-col items-center justify-center">
      <div className="chat-alert-box">
        <span className="flex gap-2">
          <IconComponent name="FileX2" />
          <span className="langflow-chat-span">{PDFLoadErrorTitle}</span>
        </span>
        <br />
        <div className="langflow-chat-desc">
          <span className="langflow-chat-desc-span">{PDFCheckFlow} </span>
        </div>
      </div>
    </div>
  );
}
