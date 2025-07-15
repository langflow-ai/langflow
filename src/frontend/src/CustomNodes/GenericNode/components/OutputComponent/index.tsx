import { useRef } from 'react';
import { ForwardedIconComponent } from '@/components/common/genericIconComponent';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from '@/components/ui/popover';
import useFlowStore from '@/stores/flowStore';
import ShadTooltip from '../../../../components/common/shadTooltipComponent';
import type { outputComponentType } from '../../../../types/components';
import { cn } from '../../../../utils/utils';

export default function OutputComponent({
  selected,
  types,
  frozen = false,
  nodeId,
  outputs,
  idx,
  name,
  proxy,
  isToolMode = false,
  handleSelectOutput,
  outputName,
}: outputComponentType) {
  const nodeType = useFlowStore(
    state => state.nodes.find(node => node.id === nodeId)?.data?.type
  );

  const displayProxy = children => {
    if (proxy) {
      return (
        <ShadTooltip content={<span>{proxy.nodeDisplayName}</span>}>
          {children}
        </ShadTooltip>
      );
    } else {
      return children;
    }
  };

  const singleOutput = displayProxy(
    <span
      className={cn(
        'px-2 py-1 text-[13px] font-medium',
        isToolMode && 'text-secondary',
        frozen ? 'text-ice' : ''
      )}
    >
      {name}
    </span>
  );

  const hasLoopOutput = outputs?.some?.(output => output.allows_loop);
  const isConditionalRouter = nodeType === 'ConditionalRouter';
  const hasOutputs = outputs.length > 1;
  const refButton = useRef<HTMLButtonElement>(null);

  // Check if all outputs have group_outputs: true AND there are multiple outputs
  const allOutputsGrouped = outputs?.every?.(output => output.group_outputs);
  const hasMultipleGroupedOutputs = hasOutputs && allOutputsGrouped;

  const shouldShowDropdown =
    hasMultipleGroupedOutputs && !hasLoopOutput && !isConditionalRouter;

  return (
    <div>
      {shouldShowDropdown ? (
        <Popover>
          <PopoverTrigger asChild>
            <Button
              unstyled
              role="combobox"
              ref={refButton}
              className="no-focus-visible group flex items-center gap-2"
              data-testid={`dropdown-output-${outputName?.toLowerCase()}`}
            >
              <div className="flex items-center gap-1 truncate rounded-md px-2 py-1 text-[13px] font-medium group-hover:bg-primary/10">
                {name}
                <ForwardedIconComponent
                  name="ChevronDown"
                  className="h-4 w-4 text-muted-foreground"
                />
              </div>
            </Button>
          </PopoverTrigger>
          <PopoverContentWithoutPortal
            side="bottom"
            align="end"
            className="noflow nowheel nopan nodelete nodrag w-full min-w-[200px] max-w-[250px] p-0"
          >
            <Command>
              <CommandList>
                <CommandGroup defaultChecked={false} className="p-0">
                  {outputs.map(output => (
                    <CommandItem
                      key={output.name}
                      data-testid={`dropdown-item-output-${outputName?.toLowerCase()}-${output.display_name?.toLowerCase()}`}
                      className="cursor-pointer justify-between rounded-none px-3 py-2"
                      onSelect={() => {
                        handleSelectOutput && handleSelectOutput(output);
                      }}
                      value={output.name}
                    >
                      <span className="truncate text-[13px]">
                        {output.display_name ?? output.name}
                      </span>
                      <span className="ml-4 text-[13px] text-muted-foreground">
                        {output.types.join(', ')}
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContentWithoutPortal>
        </Popover>
      ) : (
        singleOutput
      )}
    </div>
  );
}
