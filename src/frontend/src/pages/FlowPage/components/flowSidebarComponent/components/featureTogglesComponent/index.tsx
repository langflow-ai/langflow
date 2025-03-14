import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";

const FeatureToggles = ({
  showBeta,
  setShowBeta,
  showLegacy,
  setShowLegacy,
}) => {
  const toggles = [
    {
      label: "Beta",
      checked: showBeta,
      onChange: setShowBeta,
      badgeVariant: "pinkStatic" as const,
      testId: "sidebar-beta-switch",
    },
    {
      label: "Legacy",
      checked: showLegacy,
      onChange: setShowLegacy,
      badgeVariant: "secondaryStatic" as const,
      testId: "sidebar-legacy-switch",
    },
  ];

  return (
    <div className="flex flex-col gap-7 border-b pt-5 pb-7">
      {toggles.map((toggle) => (
        <div key={toggle.label} className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="flex gap-2 text-sm font-medium">
              Show
              <Badge variant={toggle.badgeVariant} size="xq">
                {toggle.label}
              </Badge>
            </span>
          </div>
          <Switch
            checked={toggle.checked}
            onCheckedChange={toggle.onChange}
            data-testid={toggle.testId}
          />
        </div>
      ))}
    </div>
  );
};

export default FeatureToggles;
