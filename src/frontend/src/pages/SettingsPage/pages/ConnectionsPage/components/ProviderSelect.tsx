import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { IntegrationProviderRead } from "@/controllers/API/queries/connections";

/** Provider names and their catalog icons, in both the field and its options. */
export default function ProviderSelect({
  providers,
  value,
  onChange,
}: {
  providers: IntegrationProviderRead[];
  value: string;
  onChange: (providerId: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="connection-provider">
        {t("connections.add.provider")}
      </Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger
          id="connection-provider"
          className="h-9 w-full px-2"
          data-testid="connection-provider"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {providers.map((provider) => (
            <SelectItem
              key={provider.provider_id}
              value={provider.provider_id}
              textValue={provider.display_name}
            >
              <span className="flex items-center gap-2">
                {provider.icon ? (
                  <ForwardedIconComponent
                    name={provider.icon}
                    className="h-4 w-4 shrink-0"
                    ariaHidden
                  />
                ) : (
                  <span
                    aria-hidden="true"
                    className="flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] uppercase"
                  >
                    {provider.display_name.charAt(0)}
                  </span>
                )}
                {provider.display_name}
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
