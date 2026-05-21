import { useTranslation } from "react-i18next";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";

export default function LogoIcon() {
  const { t } = useTranslation();
  return (
    <div className="relative flex h-8 w-8 items-center justify-center rounded-md bg-muted">
      <div className="flex h-8 w-8 items-center justify-center">
        <LangflowLogo
          title={t("common.langflowLogo")}
          className="absolute h-[18px] w-[18px]"
        />
      </div>
    </div>
  );
}
