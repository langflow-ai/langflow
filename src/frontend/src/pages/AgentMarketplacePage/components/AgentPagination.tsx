import { ChevronLeft, ChevronRight, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface AgentPaginationProps {
  currentPage: number;
  pageSize: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

const PAGE_SIZE_OPTIONS = [12, 24, 48, 96];

export default function AgentPagination({
  currentPage,
  pageSize,
  totalPages,
  onPageChange,
  onPageSizeChange,
}: AgentPaginationProps) {
  const handlePrevious = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  // Format page number with leading zero
  const formattedPage = currentPage.toString().padStart(2, "0");

  return (
    <div className="flex items-center gap-3">
      {/* Navigation Controls */}
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handlePrevious}
          disabled={currentPage === 1}
          className="h-8 w-8 p-0"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        <div className="flex h-8 min-w-[40px] items-center justify-center rounded-md border border-border bg-background px-3 text-sm font-medium">
          {formattedPage}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={handleNext}
          disabled={currentPage === totalPages}
          className="h-8 w-8 p-0"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Page Size Dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-2 px-3">
            <span className="text-sm">{pageSize} / page</span>
            <ChevronDown className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {PAGE_SIZE_OPTIONS.map((size) => (
            <DropdownMenuItem
              key={size}
              onClick={() => onPageSizeChange(size)}
              className={pageSize === size ? "bg-accent" : ""}
            >
              {size} per page
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
