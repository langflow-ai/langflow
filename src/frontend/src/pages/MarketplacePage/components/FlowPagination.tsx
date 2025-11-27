import { ChevronLeft, ChevronRight, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface FlowPaginationProps {
  currentPage: number;
  pageSize: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

const PAGE_SIZE_OPTIONS = [12, 24, 48, 96];

export default function FlowPagination({
  currentPage,
  pageSize,
  totalPages,
  onPageChange,
  onPageSizeChange,
}: FlowPaginationProps) {
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
          variant="link"
          size="sm"
          onClick={handlePrevious}
          disabled={currentPage === 1}
          className={`text-secondary-font hover:text-menu h-[28px] w-[28px] p-0 ${
            currentPage === 1 ? "opacity-10" : ""
          }`}
        >
          <ChevronLeft className="h-6 w-6" />
        </Button>

        <div className="flex h-[28px] min-w-[28px] items-center justify-center rounded-sm border border-primary-border bg-background-surface text-primary-font text-sm font-medium">
          {formattedPage}
        </div>

        <Button
          variant="link"
          size="sm"
          onClick={handleNext}
          disabled={currentPage === totalPages}
          className={`text-secondary-font hover:text-menu h-[28px] w-[28px] p-0 ${
            currentPage === totalPages ? "opacity-10" : ""
          }`}
        >
          <ChevronRight className="h-6 w-6" />
        </Button>
      </div>

      {/* Page Size Dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className="h-[30px] gap-2 px-3 text-secondary-font border-primary-border"
          >
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
