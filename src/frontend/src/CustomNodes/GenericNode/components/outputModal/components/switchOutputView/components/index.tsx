import { Textarea } from "../../../../../../../components/ui/textarea";
import { useTranslation } from "react-i18next";

export default function ErrorOutput({ value }: { value: string }) {
  const { t } = useTranslation();
  return (
    <Textarea
      className={`h-full w-full text-destructive custom-scroll`}
      placeholder={t("Empty")}
      value={value}
      readOnly
    />
  );
}
