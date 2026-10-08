import { useTranslation } from "react-i18next";
import { Label } from "@/components/ui/label";

export interface RegistrationSelectProps {
  /** The registrations that can start this connection's consent. */
  registrationIds: string[];
  value: string | null;
  onChange: (registrationId: string) => void;
}

/** Which OAuth registration to consent through, when there is a choice. */
export function RegistrationSelect({
  registrationIds,
  value,
  onChange,
}: RegistrationSelectProps) {
  const { t } = useTranslation();
  if (registrationIds.length < 2) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="connection-registration">
        {t("connections.add.registration")}
      </Label>
      <select
        id="connection-registration"
        className="h-9 rounded-md border border-border bg-background px-2 text-sm"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      >
        {registrationIds.map((id) => (
          <option key={id} value={id}>
            {id}
          </option>
        ))}
      </select>
    </div>
  );
}

export default RegistrationSelect;
