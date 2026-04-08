import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  addProviderOpen: boolean;
  setAddProviderOpen: (open: boolean) => void;
}

function ProvidersLoadingSkeleton() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>URL</TableHead>
          <TableHead>Provider Key</TableHead>
          <TableHead>Created</TableHead>
          <TableHead className="w-10" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: 3 }).map((_, i) => (
          <TableRow key={i}>
            <TableCell>
              <Skeleton className="h-4 w-32" />
            </TableCell>
            <TableCell>
              <Skeleton className="h-4 w-48" />
            </TableCell>
            <TableCell>
              <Skeleton className="h-4 w-24" />
            </TableCell>
            <TableCell>
              <Skeleton className="h-4 w-24" />
            </TableCell>
            <TableCell>
              <Skeleton className="h-6 w-6" />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ProvidersEmptyState({ onAddProvider }: { onAddProvider: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <h3 className="text-lg font-semibold">No Environments</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Add your first environment to start deploying your flows.
      </p>
      <Button
        variant="outline"
        className="mt-4"
        data-testid="add-provider-empty-btn"
        onClick={onAddProvider}
      >
        <ForwardedIconComponent name="Plus" className="h-4 w-4" />
        Add Environment
      </Button>
    </div>
  );
}

export default function ProvidersContent({
  isLoading,
  providers,
  addProviderOpen,
  setAddProviderOpen,
}: ProvidersContentProps) {
  const { mutate: deleteProviderAccount } = useDeleteProviderAccount();

  const providerDelete = useDeleteWithConfirmation(
    deleteProviderAccount,
    buildProviderDeleteParams,
    "Error deleting environment",
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
        onDeleteProvider={providerDelete.requestDelete}
      />
    );
  })();

  return (
    <>
      {content}

      <AddProviderModal open={addProviderOpen} setOpen={setAddProviderOpen} />

      <DeleteConfirmationModal
        open={!!providerDelete.target}
        setOpen={providerDelete.setModalOpen}
        description={`environment "${providerDelete.target?.name}"`}
        onConfirm={providerDelete.confirmDelete}
      />
    </>
  );
}
