import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import {
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { cn } from "@/utils/utils";
import { ModelOption, SelectedModel } from "../types";

export const getModelOptionTestId = (provider: string, modelName: string) =>
  `${provider}-${modelName}-option`;

interface ModelListProps {
  groupedOptions: Record<string, ModelOption[]>;
  selectedModel: SelectedModel | null;
  onSelect: (modelName: string, provider: string) => void;
}

const ModelList = ({
  groupedOptions,
  selectedModel,
  onSelect,
}: ModelListProps) => {
  const { t } = useTranslation();

  if (Object.keys(groupedOptions).length === 0) {
    return (
      <CommandList
        label={t("model.selectModel")}
        className="max-h-[300px] overflow-y-auto"
      >
        <CommandItem
          disabled
          className="w-full px-4 py-2 text-[13px] text-muted-foreground"
        >
          {t("modelInput.noModelsEnabled")}
        </CommandItem>
      </CommandList>
    );
  }

  const providerEntries = Object.entries(groupedOptions);
  // Options are grouped by provider (a list of lists — one CommandGroup per
  // provider). Screen readers normally announce an option's position
  // ("N of M") automatically, but only within its immediate group, so a
  // model would be announced as e.g. "2 of 3" (position in its provider's
  // group) instead of its real position across the whole list.
  // aria-posinset/aria-setsize would be the spec-correct fix, but several
  // screen readers (VoiceOver included) ignore them for items nested
  // inside a role="group" wrapper — which is exactly what CommandGroup
  // renders — and fall back to the per-group count regardless. Others
  // (NVDA, JAWS) *do* honor them, which would double-announce the position
  // alongside the sr-only string below. So: sr-only text only, no ARIA
  // posinset/setsize — one mechanism, that actually works everywhere.
  const totalCount = providerEntries.reduce(
    (sum, [, models]) => sum + models.length,
    0,
  );
  let position = 0;

  return (
    <CommandList
      label={t("model.selectModel")}
      className="max-h-[300px] overflow-y-auto"
    >
      {providerEntries.map(([provider, models]) => (
        <CommandGroup
          className="p-0 [&_[cmdk-group-heading]]:mx-4 [&_[cmdk-group-heading]]:my-2 [&_[cmdk-group-heading]]:p-0 [&_[cmdk-group-heading]]:font-semibold"
          heading={provider}
          key={provider}
        >
          {models.map((data) => {
            position += 1;
            return (
              <CommandItem
                key={`${provider}-${data.name}`}
                value={`${provider}::${data.name}`}
                onSelect={() => onSelect(data.name, provider)}
                className="w-full items-center rounded-none"
                data-testid={getModelOptionTestId(provider, data.name)}
              >
                <div className="flex w-full items-center gap-2">
                  <ForwardedIconComponent
                    name={data.icon || "Bot"}
                    className="h-4 w-4 shrink-0 text-primary ml-2"
                  />
                  <div className="truncate text-[13px]">{data.name}</div>
                  <span className="sr-only">
                    {t("modelInput.optionPosition", {
                      current: position,
                      total: totalCount,
                    })}
                  </span>
                  {data.metadata?.deprecated ? (
                    <Badge
                      variant="secondaryStatic"
                      size="tag"
                      data-testid={`${data.name}-deprecated-badge`}
                    >
                      Deprecated
                    </Badge>
                  ) : null}
                  <div className="pl-2 ml-auto">
                    <ForwardedIconComponent
                      name="Check"
                      className={cn(
                        "h-4 w-4 shrink-0 text-primary",
                        selectedModel?.name === data.name &&
                          selectedModel?.provider === provider
                          ? "opacity-100"
                          : "opacity-0",
                      )}
                    />
                  </div>
                </div>
              </CommandItem>
            );
          })}
        </CommandGroup>
      ))}
    </CommandList>
  );
};

export default ModelList;
