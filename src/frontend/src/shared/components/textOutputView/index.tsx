import { Textarea } from "../../../components/ui/textarea";
import { useTranslation } from "react-i18next";

const TextOutputView = ({
  left,
  value,
}: {
  left: boolean | undefined;
  value: any;
}) => {
  if (typeof value === "object" && Object.keys(value).includes("text")) {
    value = value.text;
  }
  const { t } = useTranslation();
  return (
    <Textarea
      className={`w-full custom-scroll ${left ? "min-h-32" : "h-full"}`}
      placeholder={t("Empty")}
      readOnly
      // update to real value on flowPool
      value={value}
    />
  );
};

export default TextOutputView;
