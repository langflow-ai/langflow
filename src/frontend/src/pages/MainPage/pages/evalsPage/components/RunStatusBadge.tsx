import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import type { RunStatus } from "@/controllers/API/queries/evals/types";

const VARIANT: Record<
  RunStatus,
  "secondaryStatic" | "successStatic" | "errorStatic" | "gray"
> = {
  queued: "gray",
  running: "secondaryStatic",
  completed: "successStatic",
  failed: "errorStatic",
  cancelled: "gray",
};

export default function RunStatusBadge({ status }: { status: RunStatus }) {
  const { t } = useTranslation();
  return (
    <Badge
      variant={VARIANT[status]}
      size="tag"
      data-testid={`run-status-${status}`}
    >
      {t(`evals.status.${status}`)}
    </Badge>
  );
}
