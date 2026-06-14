import type { ProviderAccount } from "../types";
import ProviderCard from "./provider-card";

interface ProvidersTableProps {
  providers: ProviderAccount[];
  deletingId?: string | null;
  deploymentTotalsByProvider?: Record<string, number>;
  onConfigureProvider?: (provider: ProviderAccount) => void;
  onDeleteProvider?: (provider: ProviderAccount) => void;
}

export default function ProvidersTable({
  providers,
  deletingId,
  deploymentTotalsByProvider = {},
  onConfigureProvider,
  onDeleteProvider,
}: ProvidersTableProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {providers.map((provider) => {
        return (
          <ProviderCard
            key={provider.id}
            provider={provider}
            deploymentCount={deploymentTotalsByProvider[provider.id] ?? 0}
            isDeleting={deletingId === provider.id}
            onConfigure={onConfigureProvider}
            onDelete={onDeleteProvider}
          />
        );
      })}
    </div>
  );
}
