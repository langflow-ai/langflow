import { useTranslation } from "react-i18next";
import { Textarea } from "../../../components/ui/textarea";

const TextOutputView = ({
  left,
  value,
}: {
  left: boolean | undefined;
  value: any;
}) => {
  const { t } = useTranslation();
  if (typeof value === "object" && Object.keys(value).includes("text")) {
    value = value.text;
  }

  const isTruncated = value?.length > 20000;

  return (
    <>
      {" "}
      <Textarea
        className={`w-full resize-none custom-scroll ${left ? "min-h-32" : "h-full"}`}
        placeholder={t("common.empty")}
        readOnly
        value={value}
      />
      {isTruncated && (
        <div className="mt-2 text-xs text-muted-foreground">
          This output has been truncated due to its size.
        </div>
      )}
    </>
  );
};

export default TextOutputView;
