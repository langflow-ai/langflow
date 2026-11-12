import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";

export default function PassedBadge({ passed }: { passed: boolean | null }) {
  const { t } = useTranslation();
  if (passed === null) {
    return (
      <Badge variant="gray" size="tag">
        {t("evals.results.notScored")}
      </Badge>
    );
  }
  return (
    <Badge variant={passed ? "successStatic" : "errorStatic"} size="tag">
      {passed ? t("evals.results.passed") : t("evals.results.failed")}
    </Badge>
  );
}
