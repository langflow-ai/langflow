import { ForwardedIconComponent } from '@/components/common/genericIconComponent';
import { cn } from '@/utils/utils';
import { Provider } from './types';

interface ProviderListItemProps {
  provider: Provider;
  isSelected?: boolean;
  onSelect: (provider: Provider) => void;
}

const ProviderListItem = ({
  provider,
  isSelected,
  onSelect,
}: ProviderListItemProps) => {
  const hasModels = provider.model_count && provider.model_count > 0;
  const isEnabled = provider.is_enabled;

  return (
    <div
      className={cn(
        'flex items-center justify-between rounded-lg px-2 py-3 transition-colors hover:bg-muted/50',
        hasModels ? 'cursor-pointer' : 'cursor-not-allowed opacity-60',
        isSelected && 'bg-muted/50'
      )}
      onClick={() => onSelect(provider)}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <ForwardedIconComponent
          name={provider.icon || 'Bot'}
          className={cn(
            'h-5 w-5 flex-shrink-0 transition-all',
            !isEnabled && 'opacity-50 grayscale'
          )}
        />
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className="truncate text-sm font-medium">
            {provider.provider}
          </span>
          {provider.model_count !== undefined && isEnabled && (
            <span className="text-xs text-accent-emerald-foreground">
              {provider.model_count}{' '}
              {provider.model_count === 1 ? 'model' : 'models'}
            </span>
          )}
        </div>
      </div>
      <ForwardedIconComponent
        name={isEnabled ? 'ellipsis' : 'Plus'}
        className="h-4 w-4"
      />
    </div>
  );
};

export default ProviderListItem;
