import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const SKELETON_ROWS = 3;
const COLUMN_HEADERS = [
  "Name",
  "Type",
  "Status",
  "Health",
  "Attached",
  "Provider",
  "Last Modified",
  "Test",
  "",
];

export default function DeploymentsLoadingSkeleton() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {COLUMN_HEADERS.map((header) => (
            <TableHead key={header}>{header}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: SKELETON_ROWS }).map((_, i) => (
          <TableRow key={i}>
            <TableCell>
              <div className="flex flex-col gap-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-64" />
              </div>
            </TableCell>
            <TableCell>
              <Skeleton className="h-6 w-16" />
            </TableCell>
            <TableCell>
              <Skeleton className="h-6 w-20" />
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <Skeleton className="h-3 w-3 rounded-full" />
                <Skeleton className="h-4 w-16" />
              </div>
            </TableCell>
            <TableCell>
              <Skeleton className="h-4 w-16" />
            </TableCell>
            <TableCell>
              <Skeleton className="h-4 w-28" />
            </TableCell>
            <TableCell>
              <div className="flex flex-col gap-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-3 w-20" />
              </div>
            </TableCell>
            <TableCell>
              <Skeleton className="h-6 w-6" />
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
