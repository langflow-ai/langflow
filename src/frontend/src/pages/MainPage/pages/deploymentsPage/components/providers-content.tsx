import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useDeleteProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-delete-provider-account";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { useDeleteWithConfirmation } from "../hooks/use-delete-with-confirmation";
import type { ProviderAccount } from "../types";
import AddProviderModal from "./add-provider-modal";
import ProvidersTable from "./providers-table";

const buildProviderDeleteParams = (id: string) => ({ provider_id: id });

interface ProvidersContentProps {
  isLoading: boolean;
  providers: ProviderAccount[];
  deploymentTotalsByProvider: Record<string, number>;
  addProviderOpen: boolean;
  setAddProviderOpen: (open: boolean) => void;
}

function ProvidersLoadingSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i} className="border-border bg-background">
          <CardHeader className="gap-4">
            <div className="flex items-start gap-3">
              <Skeleton className="h-10 w-10 rounded-md" />
              <div className="min-w-0 flex-1 space-y-2">
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-4 w-24" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-full" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-20" />
              </div>
              <div className="space-y-2">
                <Skeleton className="ml-auto h-4 w-24" />
                <Skeleton className="ml-auto h-4 w-8" />
              </div>
            </div>
            <Separator />
          </CardContent>
          <CardFooter className="gap-3">
            <Skeleton className="h-10 flex-1" />
            <Skeleton className="h-10 flex-1" />
          </CardFooter>
        </Card>
      ))}
    </div>
  );
}

function ProvidersEmptyState({ onAddProvider }: { onAddProvider: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <h3 className="text-lg font-semibold">
        {t("deployments.noEnvironments")}
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        {t("deployments.addFirstEnvironment")}
      </p>
      <Button
        variant="outline"
        className="mt-4"
        data-testid="add-provider-empty-btn"
        onClick={onAddProvider}
      >
        <ForwardedIconComponent name="Plus" className="h-4 w-4" />
        {t("deployments.addEnvironment")}
      </Button>
    </div>
  );
}

export default function ProvidersContent({
  isLoading,
  providers,
  deploymentTotalsByProvider,
  addProviderOpen,
  setAddProviderOpen,
}: ProvidersContentProps) {
  const { t } = useTranslation();
  const { mutate: deleteProviderAccount } = useDeleteProviderAccount();
  const [editingProvider, setEditingProvider] =
    useState<ProviderAccount | null>(null);

  const providerDelete = useDeleteWithConfirmation<
    ProviderAccount,
    { provider_id: string }
  >(
    deleteProviderAccount,
    buildProviderDeleteParams,
    t("deployments.errorDeletingEnvironment"),
  );

  const content = (() => {
    if (isLoading) return <ProvidersLoadingSkeleton />;
    if (providers.length === 0)
      return (
        <ProvidersEmptyState onAddProvider={() => setAddProviderOpen(true)} />
      );
    return (
      <ProvidersTable
        providers={providers}
        deletingId={providerDelete.deletingId}
        deploymentTotalsByProvider={deploymentTotalsByProvider}
        onConfigureProvider={setEditingProvider}
        onDeleteProvider={providerDelete.requestDelete}
      />
    );
  })();

  return (
    <>
      {content}

      <AddProviderModal open={addProviderOpen} setOpen={setAddProviderOpen} />
      <AddProviderModal
        open={!!editingProvider}
        setOpen={(open) => !open && setEditingProvider(null)}
        provider={editingProvider}
      />

      <DeleteConfirmationModal
        open={!!providerDelete.target}
        setOpen={providerDelete.setModalOpen}
        description={`environment "${providerDelete.target?.name}"`}
        onConfirm={providerDelete.confirmDelete}
      />
    </>
  );
}
