import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Loading from "@/components/ui/loading";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils/utils";
import type { ProviderAccount } from "../types";

interface ProvidersTableProps {
  providers: ProviderAccount[];
  deletingId?: string | null;
  onDeleteProvider?: (provider: ProviderAccount) => void;
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function ProvidersTable({
  providers,
  deletingId,
  onDeleteProvider,
}: ProvidersTableProps) {
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
        {providers.map((provider) => {
          const isDeleting = deletingId === provider.id;
          return (
            <TableRow
              key={provider.id}
              data-testid={`provider-row-${provider.id}`}
              className={cn(isDeleting && "pointer-events-none opacity-50")}
            >
              <TableCell>
                <span className="font-medium">{provider.name}</span>
              </TableCell>
              <TableCell>
                <span className="max-w-[300px] truncate text-sm text-muted-foreground">
                  {typeof provider.provider_data?.url === "string"
                    ? provider.provider_data.url
                    : "—"}
                </span>
              </TableCell>
              <TableCell>
                <span className="text-sm">{provider.provider_key}</span>
              </TableCell>
              <TableCell>
                <span className="text-sm">
                  {formatDate(provider.created_at)}
                </span>
              </TableCell>
              <TableCell>
                {isDeleting ? (
                  <div className="flex h-8 w-8 items-center justify-center">
                    <Loading size={16} className="text-muted-foreground" />
                  </div>
                ) : (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        data-testid={`actions-provider-${provider.id}`}
                        aria-label={`Actions for ${provider.name}`}
                      >
                        <ForwardedIconComponent
                          name="EllipsisVertical"
                          className="h-4 w-4"
                        />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => onDeleteProvider?.(provider)}
                      >
                        <ForwardedIconComponent
                          name="Trash2"
                          className="mr-2 h-4 w-4"
                        />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
