import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { IS_MAC } from "@/constants/constants";
import { cn } from "@/utils/utils";

export default function RenderKey({
  value,
  tableRender,
}: {
  value: string;
  tableRender?: boolean;
}): JSX.Element {
  const { t } = useTranslation();
  const check = value.toLowerCase().trim();
  return (
    <div>
      {check === "shift" ? (
        <>
          <ForwardedIconComponent
            name="ArrowBigUp"
            className={cn(tableRender ? "h-5 w-5" : "h-4 w-4")}
          />
          <span className="sr-only">{t("shortcuts.key.shift")}</span>
        </>
      ) : check === "ctrl" && IS_MAC ? (
        <>
          <span aria-hidden="true">⌃</span>
          <span className="sr-only">{t("shortcuts.key.ctrl")}</span>
        </>
      ) : check === "mod" && !IS_MAC ? (
        <span>Ctrl</span>
      ) : check === "alt" && IS_MAC ? (
        <>
          <ForwardedIconComponent
            name="OptionIcon"
            className={cn(tableRender ? "h-4 w-4" : "h-3 w-3")}
          />
          <span className="sr-only">{t("shortcuts.key.option")}</span>
        </>
      ) : (check === "mod" && IS_MAC) || check === "cmd" ? (
        <>
          <ForwardedIconComponent
            name="Command"
            className={cn(tableRender ? "h-4 w-4" : "h-3 w-3")}
          />
          <span className="sr-only">{t("shortcuts.key.command")}</span>
        </>
      ) : (
        <span>{value?.toUpperCase()}</span>
      )}
    </div>
  );
}
