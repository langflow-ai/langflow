import { PDFCheckFlow, PDFLoadErrorTitle } from "../../../constants/constants";
import IconComponent from "../../genericIconComponent";
import { useTranslation } from "react-i18next";

export default function Error(): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
      <div className="chat-alert-box">
        <span className="flex gap-2">
          <IconComponent name="FileX2" />
          <span className="langflow-chat-span">{t(PDFLoadErrorTitle)}</span>
        </span>
        <br />
        <div className="langflow-chat-desc">
          <span className="langflow-chat-desc-span">{t(PDFCheckFlow)} </span>
        </div>
      </div>
    </div>
  );
}
