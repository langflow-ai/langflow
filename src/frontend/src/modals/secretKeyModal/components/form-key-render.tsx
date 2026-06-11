import * as Form from "@radix-ui/react-form";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ModalConfigProps } from "../index";

function toDateInputValue(date: Date): string {
  // Use local date parts so UTC+ users don't see yesterday's date.
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

const EXPIRY_PRESETS = [
  { labelKey: "apiKey.expiry.1week", fallback: "1 week from today", days: 7 },
  {
    labelKey: "apiKey.expiry.1month",
    fallback: "1 month from today",
    months: 1,
  },
  { labelKey: "apiKey.expiry.1year", fallback: "1 year from today", years: 1 },
] as const;

function calcPresetDate(preset: (typeof EXPIRY_PRESETS)[number]): string {
  const d = new Date();
  if ("days" in preset) d.setDate(d.getDate() + preset.days);
  if ("months" in preset) d.setMonth(d.getMonth() + preset.months);
  if ("years" in preset) d.setFullYear(d.getFullYear() + preset.years);
  return toDateInputValue(d);
}

export const FormKeyRender = ({
  modalProps,
  apiKeyName,
  inputRef,
  setApiKeyName,
  expiresAt,
  setExpiresAt,
}: {
  modalProps: ModalConfigProps | undefined;
  apiKeyName: string;
  inputRef: React.RefObject<HTMLInputElement>;
  setApiKeyName: (value: string) => void;
  expiresAt: string;
  setExpiresAt: (value: string) => void;
}) => {
  const { t } = useTranslation();
  const today = toDateInputValue(new Date());

  return (
    <div className="flex flex-col gap-4">
      <Form.Field name="apikey">
        {modalProps?.inputLabel && (
          <Form.Label asChild className="mb-2">
            <Label className="relative bottom-1">
              {modalProps?.inputLabel as React.ReactNode}
            </Label>
          </Form.Label>
        )}

        <div className="flex items-center justify-between gap-2">
          <Form.Control asChild>
            <Input
              id="primary-input"
              value={apiKeyName}
              ref={inputRef}
              onChange={({ target: { value } }) => {
                setApiKeyName(value);
              }}
              placeholder={modalProps?.inputPlaceholder}
            />
          </Form.Control>
        </div>
      </Form.Field>

      <Form.Field name="expires_at">
        <Form.Label asChild className="mb-2">
          <Label className="relative bottom-1">
            {t("apiKey.expirationDate", "Expiration date")}{" "}
            <span className="text-muted-foreground">
              ({t("common.optional", "optional")})
            </span>
          </Label>
        </Form.Label>
        <Form.Control asChild>
          <Input
            type="date"
            id="expires-at-input"
            value={expiresAt}
            min={today}
            onChange={({ target: { value } }) => {
              setExpiresAt(value);
            }}
            className="[color-scheme:light] dark:[&::-webkit-calendar-picker-indicator]:invert dark:[&::-webkit-calendar-picker-indicator]:opacity-80"
          />
        </Form.Control>
        <div className="mt-2 flex items-center gap-1.5">
          {EXPIRY_PRESETS.map((preset) => {
            const value = calcPresetDate(preset);
            const active = expiresAt === value;
            return (
              <button
                key={preset.labelKey}
                type="button"
                onClick={() => setExpiresAt(active ? "" : value)}
                className={
                  "rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors " +
                  (active
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background text-muted-foreground hover:border-primary hover:text-primary")
                }
              >
                {t(preset.labelKey, preset.fallback)}
              </button>
            );
          })}
        </div>
      </Form.Field>
    </div>
  );
};
