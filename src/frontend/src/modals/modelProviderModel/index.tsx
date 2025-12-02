import { Dialog, DialogContent, DialogHeader } from '@/components/ui/dialog';
import BaseModal from '../baseModal';
import { Input } from '@/components/ui/input';
import ProviderList from '@/pages/SettingsPage/pages/ModelProvidersPage/components/provider-list';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import ForwardedIconComponent from '@/components/common/genericIconComponent';
import { useState } from 'react';
import { Provider } from '@/pages/SettingsPage/pages/ModelProvidersPage/components/types';
import { cn } from '@/utils/utils';
import { Switch } from '@/components/ui/switch';

interface ModelProviderModalProps {
  open: boolean;
  onClose: () => void;
}

const ModelProviderModal = ({ open, onClose }: ModelProviderModalProps) => {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null
  );
  const [isEditing, setIsEditing] = useState(false);

  const handleProviderSelect = (provider: Provider) => {
    setSelectedProvider(prev =>
      prev?.provider === provider.provider ? null : provider
    );
  };

  return (
    <Dialog open={open} onOpenChange={isOpen => !isOpen && onClose()}>
      <DialogContent className="flex flex-col overflow-hidden rounded-xl p-0 max-w-[950px] gap-0">
        <DialogHeader className="flex w-full border-b px-4 py-3">
          <div className="flex justify-start items-center gap-3">
            <ForwardedIconComponent name="Brain" className="w-5 h-5" />
            <div className="text-[13px] font-semibold ">Model providers</div>
          </div>
        </DialogHeader>
        <div className="flex flex-row w-full overflow-hidden">
          <div
            className={cn(
              'flex border-r p-2 flex-col transition-all duration-300 ease-in-out',
              selectedProvider ? 'w-1/2' : 'w-full'
            )}
          >
            <ProviderList
              onProviderSelect={handleProviderSelect}
              selectedProviderName={selectedProvider?.provider ?? null}
            />
          </div>
          <div
            className={cn(
              'flex flex-col gap-1 transition-all duration-300 ease-in-out overflow-hidden',
              selectedProvider
                ? 'w-1/2 opacity-100 translate-x-0'
                : 'w-0 opacity-0 translate-x-full'
            )}
          >
            <div className="flex flex-row items-center gap-1 border-b p-4 min-w-[300px]">
              <ForwardedIconComponent
                name={selectedProvider?.icon || 'Bot'}
                className="w-5 h-5 flex-shrink-0"
              />
              <span className="text-[13px] font-semibold pl-2 mr-auto">
                {selectedProvider?.provider || 'Provider Name'}
              </span>
              <Button
                variant="ghost"
                size="icon"
                unstyled
                onClick={() => setIsEditing(!isEditing)}
              >
                <ForwardedIconComponent
                  name={'Pencil'}
                  className={cn(
                    'h-4 w-4',
                    isEditing ? 'text-primary' : 'text-muted-foreground'
                  )}
                />
              </Button>
            </div>

            <div className="relative overflow-x-hidden min-w-[300px] min-h-[460px]">
              <div
                className={cn(
                  'flex flex-col p-4 gap-3 transition-all duration-300 ease-in-out ',
                  isEditing
                    ? 'opacity-0 -translate-x-full absolute inset-0'
                    : 'opacity-100 translate-x-0'
                )}
              >
                <div className="text-[13px] font-semibold text-muted-foreground">
                  LLM
                </div>
                {[1, 2, 3, 4, 5].map(i => (
                  <div
                    key={i}
                    className="flex flex-row items-center justify-between"
                  >
                    <div className="flex flex-row items-center gap-2">
                      <ForwardedIconComponent name="Bot" className="w-5 h-5" />
                      model name
                    </div>
                    <Switch />
                  </div>
                ))}
                <div className="text-[13px] font-semibold text-muted-foreground pt-2">
                  Embedding
                </div>
                {[1, 2, 3].map(i => (
                  <div
                    key={i}
                    className="flex flex-row items-center justify-between"
                  >
                    <div className="flex flex-row items-center gap-2">
                      <ForwardedIconComponent name="Bot" className="w-5 h-5" />
                      model name
                    </div>
                    <Switch />
                  </div>
                ))}
              </div>
              <div
                className={cn(
                  'flex flex-col transition-all duration-300 ease-in-out',
                  isEditing
                    ? 'opacity-100 translate-x-0'
                    : 'opacity-0 translate-x-full absolute inset-0'
                )}
              >
                <div className="flex flex-col gap-4 p-4">
                  <div className="text-[13px] -mb-1">Authorization Name</div>
                  <Input placeholder="Authorization Name" />
                  <div className="text-[13px] -mb-1">API Key</div>
                  <Input placeholder="API Key" />
                  <div className="text-muted-foreground text-xs flex items-center gap-1 -mt-1 hover:underline cursor-pointer w-fit">
                    Find your API key{' '}
                    <ForwardedIconComponent
                      name="external-link"
                      className="w-4 h-4"
                    />
                  </div>
                  <div className="text-[13px] -mb-1">API Base </div>
                  <Input placeholder="Authorization Name" />
                </div>
                <div className="flex flex-col p-4 border-t">
                  <div className="text-[13px]">LLM</div>
                  <div className="flex flex-row gap-2 mt-2">
                    <Badge variant="gray" size="sq">
                      Language
                    </Badge>
                    <Badge variant="gray" size="sq">
                      Embedding
                    </Badge>
                    <Badge variant="gray" size="sq">
                      Image
                    </Badge>
                  </div>
                  <div className="text-[13px] pt-4">Embedding </div>
                  <div className="flex flex-row gap-2 mt-2">
                    <Badge variant="gray" size="sq">
                      Language
                    </Badge>
                    <Badge variant="gray" size="sq">
                      Embedding
                    </Badge>
                    <Badge variant="gray" size="sq">
                      Image
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex justify-end border-t p-4 min-w-[300px]">
              {!isEditing ? (
                <Button variant="ghost" className="w-full">
                  Cancel
                </Button>
              ) : (
                <Button className="w-full">
                  {!isEditing ? 'Update' : 'Configure'}
                </Button>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ModelProviderModal;
