import { useTranslation } from "react-i18next";
import { Switch } from "@/components/ui/switch";
import type { DBProviderBooleanField } from "@/constants/dbProviderConstants";

export function BooleanFieldRow({
  field,
  value,
  disabled,
  onChange,
}: {
  field: DBProviderBooleanField;
  value: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex items-start justify-between gap-4 rounded-md border border-border bg-muted/20 px-3 py-2">
      <div className="flex min-w-0 flex-col">
        <span className="text-[12px] font-medium">
          {t(`settings.dbProviders.fields.${field.variableKey}.label`, {
            defaultValue: field.label,
          })}
        </span>
        {field.helperText && (
          <span className="pt-0.5 text-[11px] text-muted-foreground">
            {t(`settings.dbProviders.fields.${field.variableKey}.helperText`, {
              defaultValue: field.helperText,
            })}
          </span>
        )}
        <span className="pt-1 text-[11px] text-muted-foreground">
          {t("settings.dbProviders.savedAsGlobalVariable")}{" "}
          <span className="font-mono">{field.variableKey}</span>
        </span>
      </div>
      <Switch
        checked={value}
        onCheckedChange={onChange}
        disabled={disabled}
        aria-label={field.label}
        data-testid={`db-provider-toggle-${field.variableKey}`}
      />
    </div>
  );
}
