import { PDFErrorTitle, PDFLoadError } from "../../../constants/constants";
import { useTranslation } from "react-i18next";

export default function NoDataPdf(): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
      <div className="chat-alert-box">
        <span>
          📄 <span className="langflow-chat-span">{t(PDFErrorTitle)}</span>
        </span>
        <br />
        <div className="langflow-chat-desc">
          <span className="langflow-chat-desc-span">{t(PDFLoadError)} </span>
        </div>
      </div>
    </div>
  );
}
