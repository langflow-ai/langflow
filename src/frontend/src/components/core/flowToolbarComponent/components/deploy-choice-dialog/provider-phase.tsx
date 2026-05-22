import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { ProviderAccount } from "@/pages/MainPage/pages/deploymentsPage/types";

interface ProviderPhaseContentProps {
  providers: ProviderAccount[];
  selectedProviderId: string;
  onSelectProvider: (id: string) => void;
  onContinue: () => void;
  onCancel: () => void;
}

export default function ProviderPhaseContent({
  providers,
  selectedProviderId,
  onSelectProvider,
  onContinue,
  onCancel,
}: ProviderPhaseContentProps) {
  const { t } = useTranslation();
  return (
    <>
      <DialogHeader>
        <DialogTitle>{t("deployments.selectProvider")}</DialogTitle>
        <DialogDescription>
          {t("deployments.chooseProviderDesc")}
        </DialogDescription>
      </DialogHeader>

      <RadioGroup value={selectedProviderId} onValueChange={onSelectProvider}>
        {providers.map((provider) => (
          <div
            key={provider.id}
            className="flex items-center gap-3 rounded-lg border p-3"
          >
            <RadioGroupItem
              value={provider.id}
              id={`provider-${provider.id}`}
            />
            <Label
              htmlFor={`provider-${provider.id}`}
              className="flex flex-1 cursor-pointer flex-col gap-0.5"
            >
              <span className="text-sm font-medium">{provider.name}</span>
              <span className="text-xs text-muted-foreground">
                {typeof provider.provider_data?.url === "string"
                  ? provider.provider_data.url
                  : "—"}
              </span>
            </Label>
          </div>
        ))}
      </RadioGroup>

      <div className="flex items-center justify-between pt-4">
        <Button variant="ghost" onClick={onCancel}>
          {t("deployments.cancel")}
        </Button>
        <Button onClick={onContinue}>{t("deployments.continue")}</Button>
      </div>
    </>
  );
}
