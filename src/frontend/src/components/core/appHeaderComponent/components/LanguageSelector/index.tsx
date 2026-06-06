import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  SUPPORTED_LANGUAGES,
  type SupportedLanguage,
} from "@/constants/languages";
import { loadLanguage, normalizeLanguage } from "@/i18n";
import { useTypesStore } from "@/stores/typesStore";

type LanguageSelectorProps = {
  className?: string;
  triggerClassName?: string;
};

/**
 * 渲染共享语言选择器，并保持依赖语言的缓存为最新状态。
 * Renders the shared language selector and keeps language-dependent caches fresh.
 *
 * @param props - 选择器触发器的样式选项。 / Styling options for the selector trigger.
 * @returns 手动语言选项选择器。 / The manual language selector.
 */
export const LanguageSelector = ({
  className,
  triggerClassName,
}: LanguageSelectorProps) => {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const setTypes = useTypesStore((state) => state.setTypes);

  const handleChange = async (code: SupportedLanguage) => {
    const normalizedLanguage = await loadLanguage(code);
    await i18n.changeLanguage(normalizedLanguage);
    localStorage.setItem("languagePreference", normalizedLanguage);
    setTypes({});
    queryClient.invalidateQueries({ queryKey: ["useGetTypes"] });
  };

  return (
    <Select
      value={normalizeLanguage(i18n.language)}
      onValueChange={(code) => handleChange(code as SupportedLanguage)}
    >
      <SelectTrigger
        aria-label={t("settings.languageSelectAriaLabel")}
        className={[className, triggerClassName].filter(Boolean).join(" ")}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {SUPPORTED_LANGUAGES.map((lang) => (
          <SelectItem key={lang.code} value={lang.code}>
            {lang.label}
            {lang.code === "en"
              ? ` (${t("settings.languageRecommended")})`
              : ""}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

export default LanguageSelector;
