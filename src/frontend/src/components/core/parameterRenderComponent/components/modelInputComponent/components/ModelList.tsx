import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { cn } from "@/utils/utils";
import { ModelOption, SelectedModel } from "../types";

interface ModelListProps {
  groupedOptions: Record<string, ModelOption[]>;
  selectedModel: SelectedModel | null;
  onSelect: (modelName: string) => void;
}

const ModelList = ({
  groupedOptions,
  selectedModel,
  onSelect,
}: ModelListProps) => {
  if (Object.keys(groupedOptions).length === 0) {
    return (
      <CommandList className="max-h-[300px] overflow-y-auto">
        <CommandItem
          disabled
          className="w-full px-4 py-2 text-[13px] text-muted-foreground"
        >
          No Models Enabled
        </CommandItem>
      </CommandList>
    );
  }

  return (
    <CommandList className="max-h-[300px] overflow-y-auto">
      {Object.entries(groupedOptions).map(([provider, models]) => (
        <CommandGroup className="p-0" key={provider}>
          <div className="text-xs font-semibold my-2 ml-4 text-muted-foreground flex items-center justify-between pr-4">
            <div className="flex items-center">{provider}</div>
          </div>
          {models.map((data) => {
            const url =
              data.url ||
              (typeof data.metadata?.url === "string"
                ? (data.metadata.url as string)
                : undefined);
            const label = data.display_name || data.name;
            const isSelected = selectedModel?.name === data.name;
            return (
              <CommandItem
                key={data.name}
                value={data.name}
                onSelect={() => onSelect(data.name)}
                className="group w-full items-center rounded-none"
                data-testid={`${data.name}-option`}
              >
                <div className="flex w-full items-center gap-2">
                  <ForwardedIconComponent
                    name={data.icon || "Bot"}
                    className="h-4 w-4 shrink-0 text-primary ml-2"
                  />
                  <div className="truncate text-[13px]" title={data.name}>
                    {label}
                  </div>
                  {url && (
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      onMouseDown={(e) => e.stopPropagation()}
                      data-testid={`${data.name}-external-link`}
                      aria-label={`Open ${label} on its provider page`}
                      title={url}
                      className="opacity-0 group-hover:opacity-100 transition-opacity inline-flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:text-primary"
                    >
                      <ForwardedIconComponent
                        name="ExternalLink"
                        className="h-3.5 w-3.5"
                      />
                    </a>
                  )}
                  <div className="pl-2 ml-auto">
                    <ForwardedIconComponent
                      name="Check"
                      className={cn(
                        "h-4 w-4 shrink-0 text-primary",
                        isSelected ? "opacity-100" : "opacity-0",
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
