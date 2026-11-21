import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface CopyFieldProps {
  id: string;
  label: string;
  value: string;
  copyLabel: string;
  testId: string;
}

/** A read-only value with a copy button that confirms in place. */
export function CopyField({
  id,
  label,
  value,
  copyLabel,
  testId,
}: CopyFieldProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          readOnly
          value={value}
          className="font-mono text-xs"
          onFocus={(event) => event.currentTarget.select()}
          data-testid={testId}
        />
        <Button
          variant="outline"
          size="iconMd"
          onClick={() => void copy()}
          aria-label={copyLabel}
          data-testid={`${testId}-copy`}
        >
          <ForwardedIconComponent
            name={copied ? "Check" : "Copy"}
            aria-hidden="true"
            className="h-4 w-4"
          />
        </Button>
        <span className="sr-only" role="status">
          {copied ? t("triggers.common.copied") : ""}
        </span>
      </div>
    </div>
  );
}

export default CopyField;
