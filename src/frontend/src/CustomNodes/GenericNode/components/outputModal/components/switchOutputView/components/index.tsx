import { useTranslation } from "react-i18next";
import { Textarea } from "../../../../../../../components/ui/textarea";

export default function ErrorOutput({ value }: { value: string }) {
  const { t } = useTranslation();
  return (
    <Textarea
      className={`h-full w-full text-destructive custom-scroll`}
      placeholder={t("outputModal.empty")}
      value={value}
      readOnly
    />
  );
}
