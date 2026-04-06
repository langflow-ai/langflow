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
  return (
    <>
      <DialogHeader>
        <DialogTitle>Select Provider</DialogTitle>
        <DialogDescription>
          Choose a provider environment to deploy to, or create a new deployment
          from scratch.
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
                {provider.url}
              </span>
            </Label>
          </div>
        ))}
      </RadioGroup>

      <div className="flex items-center justify-between pt-4">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={onContinue}>Continue</Button>
      </div>
    </>
  );
}
