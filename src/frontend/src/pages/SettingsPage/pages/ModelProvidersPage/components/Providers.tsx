import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

type Provider = {
  id: number;
  name: string;
  icon: string;
  metadata?: {
    description: string;
    style: string;
  };
};

const Providers = ({ type }: { type: "enabled" | "available" }) => {
  const MOCK_PROVIDERS: Provider[] = [
    {
      id: 1,
      name: "OpenAI",
      metadata: {
        description: "25 models",
        style: "text-accent-emerald-foreground",
      },
      icon: "OpenAI",
    },
    {
      id: 2,
      name: "Ollama",
      metadata: {
        description: "25 models",
        style: "text-accent-emerald-foreground",
      },
      icon: "Ollama",
    },
  ];

  const MOCK_PROVIDERS_AVAILABLE: Provider[] = [
    {
      id: 1,
      name: "Anthropic",
      icon: "Anthropic",
    },
    {
      id: 2,
      name: "Google",
      icon: "Google",
    },
    {
      id: 3,
      name: "IBM watsonx",
      icon: "WatsonxAI",  
    },
    {
      id: 4,
      name: "Cohere",
      icon: "Cohere",
    },
    {
      id: 5,
      name: "DeepSeek",
      icon: "DeepSeek",
    },
  ];

  return (
    <div>
      <h2 className="text-muted-foreground text-sm--medium">
        {type.charAt(0).toUpperCase() + type.slice(1)}
      </h2>
      {(type === "available" ? MOCK_PROVIDERS_AVAILABLE : MOCK_PROVIDERS).map((provider) => (
        <div key={provider.id} className={cn("flex items-center my-2 py-1 group ", type === "available" && "hover:bg-muted hover:rounded-md cursor-pointer")}>
          <ForwardedIconComponent name={provider.icon} className="w-4 h-4 mx-3" />

          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold pl-1 truncate">{provider.name}</h3>
            {provider?.metadata && (
              <p className={cn(provider?.metadata?.style)}>
                {provider?.metadata?.description}
              </p>
            )}
          </div>
          <div className="flex items-center ml-auto">
            <Button size="icon" variant="ghost" className={cn("p-2", type === "available" && "group-hover:bg-transparent")}>
              <ForwardedIconComponent name={type === "enabled" ? "Ellipsis" : "Plus"} className={cn("text-muted-foreground", type === "available" && "group-hover:text-primary")} />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default Providers;
