import ForwardedIconComponent from '@/components/common/genericIconComponent';
import { Input } from '@/components/ui/input';

interface ModelProviderEditProps {
  authName: string;
  onAuthNameChange: (value: string) => void;
  apiKey: string;
  onApiKeyChange: (value: string) => void;
  apiBase: string;
  onApiBaseChange: (value: string) => void;
  providerName?: string;
}

const ModelProviderEdit = ({
  authName,
  onAuthNameChange,
  apiKey,
  onApiKeyChange,
  apiBase,
  onApiBaseChange,
  providerName,
}: ModelProviderEditProps) => {
  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="text-[13px] -mb-1 font-medium flex items-center gap-1">
        Authorization Name
        <ForwardedIconComponent
          name="info"
          className="w-4 h-4 text-muted-foreground ml-1"
        />
      </div>
      <Input
        placeholder="Authorization Name"
        value={authName}
        onChange={e => onAuthNameChange(e.target.value)}
      />
      <div className="text-[13px] -mb-1 font-medium flex items-center gap-1">
        API Key <span className="text-red-500">*</span>
        <ForwardedIconComponent
          name="info"
          className="w-4 h-4 text-muted-foreground ml-1"
        />
      </div>
      <Input
        placeholder="Enter your API key"
        type="password"
        value={apiKey}
        required
        onChange={e => onApiKeyChange(e.target.value)}
      />
      <div className="text-muted-foreground text-xs flex items-center gap-1 -mt-1 hover:underline cursor-pointer w-fit">
        Find your API key{' '}
        <ForwardedIconComponent name="external-link" className="w-4 h-4" />
      </div>
      <div className="text-[13px] -mb-1 font-medium flex items-center gap-1">
        API Base
        <ForwardedIconComponent
          name="info"
          className="w-4 h-4 text-muted-foreground ml-1"
        />{' '}
      </div>
      <Input
        placeholder="API Base URL (optional)"
        value={apiBase}
        onChange={e => onApiBaseChange(e.target.value)}
      />
    </div>
  );
};

export default ModelProviderEdit;
