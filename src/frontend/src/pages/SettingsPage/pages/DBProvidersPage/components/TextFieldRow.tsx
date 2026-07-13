import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import type { DBProviderTextField } from "@/constants/dbProviderConstants";

const MASKED_VALUE = "••••••••";

export function TextFieldRow({
  field,
  value,
  hasNewValue,
  isEditingSecret,
  existingValue,
  isSecretConfigured,
  disabled,
  onChange,
  onFocus,
  onBlur,
}: {
  field: DBProviderTextField;
  value: string;
  hasNewValue: boolean;
  isEditingSecret: boolean;
  existingValue: string | undefined;
  isSecretConfigured?: boolean;
  disabled: boolean;
  onChange: (value: string) => void;
  onFocus: () => void;
  onBlur: () => void;
}) {
  // Show redacted dots when a secret is configured (variable exists) and
  // the user is neither actively editing nor has typed a new value this
  // session. Use ``isSecretConfigured`` (variable existence) rather than
  // ``existingValue`` (returned API value) because credential-type
  // variables are not exposed in the global-variables API response.
  const { t } = useTranslation();
  const shouldMask =
    field.isSecret &&
    (isSecretConfigured ?? !!existingValue) &&
    !hasNewValue &&
    !isEditingSecret;
  const inputValue = shouldMask ? MASKED_VALUE : value;

  return (
    <label className="flex flex-col gap-1">
      <span className="text-[12px] font-medium text-muted-foreground">
        {t(`settings.dbProviders.fields.${field.variableKey}.label`, {
          defaultValue: field.label,
        })}
        {field.required && <span className="ml-1 text-destructive">*</span>}
      </span>
      <Input
        placeholder={field.placeholder}
        value={inputValue}
        type={field.isSecret ? "password" : "text"}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onFocus={onFocus}
        onBlur={onBlur}
      />
      <span className="text-[11px] text-muted-foreground">
        {t("settings.dbProviders.savedAsGlobalVariable")}{" "}
        <span className="font-mono">{field.variableKey}</span>
      </span>
    </label>
  );
}
