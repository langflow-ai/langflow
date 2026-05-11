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
          {models.map((data) => (
            <CommandItem
              key={data.name}
              value={data.name}
              onSelect={() => onSelect(data.name)}
              className="w-full items-center rounded-none"
              data-testid={`${data.name}-option`}
            >
              <div className="flex w-full items-center gap-2">
                <ForwardedIconComponent
                  name={data.icon || "Bot"}
                  className="h-4 w-4 shrink-0 text-primary ml-2"
                />
                <div className="truncate text-[13px]">{data.name}</div>
                <div className="pl-2 ml-auto">
                  <ForwardedIconComponent
                    name="Check"
                    className={cn(
                      "h-4 w-4 shrink-0 text-primary",
                      selectedModel?.name === data.name
                        ? "opacity-100"
                        : "opacity-0",
                    )}
                  />
                </div>
              </div>
            </CommandItem>
          ))}
        </CommandGroup>
      ))}
    </CommandList>
  );
};

export default ModelList;
