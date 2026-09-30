import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import Loading from "@/components/ui/loading";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/utils/utils";
import type { ProviderAccount } from "../types";

interface ProviderCardProps {
  provider: ProviderAccount;
  deploymentCount: number;
  isDeleting: boolean;
  onConfigure?: (provider: ProviderAccount) => void;
  onDelete?: (provider: ProviderAccount) => void;
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatProviderLabel(providerKey: string) {
  return providerKey
    .split("-")
    .map((part) => {
      if (part.toLowerCase() === "watsonx") return "watsonx";
      return part.charAt(0).toUpperCase() + part.slice(1);
    })
    .join(" ");
}

function getProviderEndpoint(provider: ProviderAccount) {
  return typeof provider.provider_data?.url === "string"
    ? provider.provider_data.url
    : "—";
}

export default function ProviderCard({
  provider,
  deploymentCount,
  isDeleting,
  onConfigure,
  onDelete,
}: ProviderCardProps) {
  const endpoint = getProviderEndpoint(provider);
  const lastUpdated = formatDate(provider.updated_at ?? provider.created_at);

  return (
    <Card
      data-testid={`provider-row-${provider.id}`}
      className={cn(
        "border-border bg-background",
        isDeleting && "pointer-events-none opacity-50",
      )}
    >
      <CardHeader className="flex-row items-start justify-between space-y-0 gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-muted">
            <ForwardedIconComponent
              name="Cloud"
              className="h-5 w-5 text-foreground"
            />
          </div>
          <div className="min-w-0">
            <CardTitle className="truncate text-xl">{provider.name}</CardTitle>
            <p className="pt-1 text-sm text-muted-foreground">
              {formatProviderLabel(provider.provider_key)}
            </p>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">Endpoint</p>
          <p className="break-all text-sm text-foreground" title={endpoint}>
            {endpoint}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">Last Updated</p>
            <p className="text-sm text-foreground">{lastUpdated}</p>
          </div>
          <div className="space-y-1 text-right">
            <p className="text-sm text-muted-foreground">Deployments</p>
            <p className="text-sm text-foreground">{deploymentCount}</p>
          </div>
        </div>

        <Separator />
      </CardContent>

      <CardFooter className="gap-3">
        <Button
          variant="secondary"
          className="flex-1"
          data-testid={`configure-provider-${provider.id}`}
          onClick={() => onConfigure?.(provider)}
          disabled={isDeleting}
        >
          <ForwardedIconComponent name="Settings" className="h-4 w-4" />
          Configure
        </Button>
        <Button
          variant="outline"
          className="flex-1"
          data-testid={`delete-provider-${provider.id}`}
          onClick={() => onDelete?.(provider)}
          disabled={isDeleting}
        >
          {isDeleting ? (
            <Loading size={16} className="text-muted-foreground" />
          ) : (
            <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
          )}
          Delete
        </Button>
      </CardFooter>
    </Card>
  );
}
