import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";

const GeneralPageHeaderComponent = () => {
  const { t } = useTranslation();
  return (
    <>
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            {t("settings.generalTitle")}
            <ForwardedIconComponent
              name="SlidersHorizontal"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("settings.generalDescription")}
          </p>
        </div>
      </div>
    </>
  );
};
export default GeneralPageHeaderComponent;
