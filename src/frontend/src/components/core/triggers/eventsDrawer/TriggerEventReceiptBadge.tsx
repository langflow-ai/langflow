import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";

/** Every persisted ledger row confirms receipt, independently of its run. */
export default function TriggerEventReceiptBadge() {
  const { t } = useTranslation();
  return (
    <Badge
      variant="outline"
      size="xq"
      className="w-fit gap-1 border-0 bg-accent-emerald text-accent-emerald-foreground"
      data-testid="trigger-event-receipt"
    >
      <ForwardedIconComponent
        name="CircleCheck"
        aria-hidden="true"
        className="h-3 w-3"
      />
      {t("triggers.events.receiptLabel")}
    </Badge>
  );
}
