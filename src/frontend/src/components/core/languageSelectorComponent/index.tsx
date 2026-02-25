import { useTranslation } from "react-i18next";
import i18n from "@/i18n/index";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

const LANGUAGES = [
    { value: "zh-CN", label: "中文（简体）" },
    { value: "en", label: "English" },
];

export default function LanguageSelector() {
    const { t } = useTranslation();

    const handleLanguageChange = (lang: string) => {
        i18n.changeLanguage(lang);
        localStorage.setItem("langflow-lang", lang);
    };

    return (
        <div className="flex flex-col gap-2">
            <label className="text-sm font-medium">
                {t("settings.languageLabel", "界面语言")}
            </label>
            <Select value={i18n.language} onValueChange={handleLanguageChange}>
                <SelectTrigger className="w-48">
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {LANGUAGES.map((lang) => (
                        <SelectItem key={lang.value} value={lang.value}>
                            {lang.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}
