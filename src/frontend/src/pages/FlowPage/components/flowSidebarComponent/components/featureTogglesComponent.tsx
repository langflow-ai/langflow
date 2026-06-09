import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";

const FeatureToggles = ({
  showBeta,
  setShowBeta,
  showLegacy,
  setShowLegacy,
}) => {
  const { t } = useTranslation();
  const toggles = [
    {
      label: t("sidebar.betaLabel"),
      checked: showBeta,
      onChange: setShowBeta,
      badgeVariant: "purpleStatic" as const,
      testId: "sidebar-beta-switch",
    },
    {
      label: t("sidebar.legacyLabel"),
      checked: showLegacy,
      onChange: setShowLegacy,
      badgeVariant: "secondaryStatic" as const,
      testId: "sidebar-legacy-switch",
    },
  ];

  return (
    <div className="flex flex-col gap-7 pb-3 px-2 pt-5">
      {toggles.map((toggle) => (
        <div key={toggle.label} className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="flex cursor-default gap-2 text-sm font-medium">
              {t("sidebar.show")}
              <Badge variant={toggle.badgeVariant} size="xq">
                {toggle.label}
              </Badge>
            </span>
          </div>
          <Switch
            checked={toggle.checked}
            onCheckedChange={toggle.onChange}
            data-testid={toggle.testId}
            className="scale-90"
          />
        </div>
      ))}
    </div>
  );
};

export default FeatureToggles;
