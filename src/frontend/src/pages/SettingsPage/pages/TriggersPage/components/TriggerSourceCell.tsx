import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  sourceIconOf,
  sourceKeyOf,
} from "@/components/core/triggers/helpers/trigger-presentation";
import TriggerTransportLabel from "@/components/core/triggers/TriggerTransportLabel";
import type { TriggerRead } from "@/controllers/API/queries/triggers";

/** Provider (or core kind) plus how events arrive: push, socket, or poll. */
export function TriggerSourceCell({ trigger }: { trigger: TriggerRead }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border bg-muted">
        <ForwardedIconComponent
          name={sourceIconOf(trigger)}
          aria-hidden="true"
          className="h-3.5 w-3.5"
        />
      </span>
      <div className="flex min-w-0 flex-col">
        <span className="truncate">{t(sourceKeyOf(trigger))}</span>
        <span className="text-xs text-muted-foreground">
          <TriggerTransportLabel trigger={trigger} />
        </span>
      </div>
    </div>
  );
}

export default TriggerSourceCell;
