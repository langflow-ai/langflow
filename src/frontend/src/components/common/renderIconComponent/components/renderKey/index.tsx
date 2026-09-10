import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { IS_MAC } from "@/constants/constants";
import { cn } from "@/utils/utils";

// Spoken name for a single shortcut key token, mirroring the visual branches
// below. Used to build an explicit aria-label on shortcut wrappers: WebKit
// drops visually-clipped (sr-only) text from grid cell values, so relying on
// hidden text next to the icons leaves the modifiers unannounced in
// Safari/VoiceOver (LE-2041 QA).
export function shortcutKeyLabel(
  value: string,
  t: (key: string) => string,
): string {
  const check = value.toLowerCase().trim();
  if (check === "shift") return t("shortcuts.key.shift");
  if (check === "ctrl" || (check === "mod" && !IS_MAC)) {
    return t("shortcuts.key.ctrl");
  }
  if (check === "alt" && IS_MAC) return t("shortcuts.key.option");
  if (check === "mod" || check === "cmd") return t("shortcuts.key.command");
  return value.toUpperCase();
}

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
