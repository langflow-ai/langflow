import { useEffect, useState } from "react";
import {
  PAGINATION_PAGE,
  PAGINATION_ROWS_COUNT,
  PAGINATION_SIZE,
} from "@/constants/constants";
import type { PaginatorComponentType } from "../../../types/components";
import IconComponent from "../../common/genericIconComponent";
import { Button } from "../../ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../ui/select";

export default function PaginatorComponent({
  pageSize = PAGINATION_SIZE,
  pageIndex = PAGINATION_PAGE,
  rowsCount = PAGINATION_ROWS_COUNT,
  totalRowsCount = 0,
  paginate,
  pages,
  isComponent,
}: PaginatorComponentType) {
  const [size, setPageSize] = useState(pageSize);
  const [maxIndex, setMaxPageIndex] = useState(
    Math.ceil(totalRowsCount / pageSize)
  );

  useEffect(() => {
    setMaxPageIndex(pages ?? Math.ceil(totalRowsCount / size));
  }, [totalRowsCount]);

  const disableFirstPage = pageIndex <= 1;
  const disableLastPage = pageIndex === maxIndex;

  const _handleValueChange = (pageSize: string) => {
    setPageSize(Number(pageSize));
    setMaxPageIndex(pages ?? Math.ceil(totalRowsCount / Number(pageSize)));
    paginate(1, Number(pageSize));
  };

  return (
    <div className="flex flex-1 items-center justify-between">
      <p className="flex items-center justify-end text-sm text-primary-font font-medium">
        {`Showing ${(pageIndex - 1) * pageSize + 1} - ${Math.min(
          totalRowsCount,
          (pageIndex - 1) * pageSize + pageSize
        )} `}
        {/* Showing {(pageIndex - 1) * pageSize + 1}-
        {Math.min(totalRowsCount, (pageIndex - 1) * pageSize + pageSize)}{" "} */}
        <span className="ml-1">
          {" "}
          of {totalRowsCount}{" "}
          {isComponent === undefined
            ? "items"
            : isComponent
            ? "components"
            : "flows"}
        </span>
      </p>
      <div className="flex items-center gap-1">
        <div className="flex items-center gap-1 text-mmd text-secondary-foreground">
          <Select
            onValueChange={(value) => paginate(Number(value), size)}
            value={pageIndex.toString()}
          >
            <SelectTrigger
              direction="down"
              className="h-[30px] gap-2 px-3 text-secondary-font border-primary-border bg-background-surface hover:bg-accent-light font-medium rounded-[4px]"
            >
              <SelectValue placeholder="1" />
            </SelectTrigger>
            <SelectContent>
              {Array.from({ length: maxIndex }, (_, i) => i + 1).map((item) => (
                <SelectItem key={item} value={item.toString()}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="text-secondary-font font-medium text-sm ml-1">
            of {maxIndex} pages
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            disabled={disableFirstPage}
            onClick={() => {
              if (pageIndex > 0) {
                paginate(pageIndex - 1, size);
              }
            }}
            className={`text-secondary-font hover:text-menu h-[28px] w-[28px] p-0 ${
              disableFirstPage ? "opacity-10" : ""
            }`}
          >
            <span className="sr-only">Go to previous page</span>
            <IconComponent name="ChevronLeft" className="h-4 w-4" />
          </Button>
          <Button
            disabled={disableLastPage}
            onClick={() => {
              paginate(pageIndex + 1, size);
            }}
            variant="outline"
            size="sm"
            className={`text-secondary-font hover:text-menu h-[28px] w-[28px] p-0 ${
              disableLastPage ? "opacity-10" : ""
            }`}
          >
            <span className="sr-only text-secondary-font font-medium text-sm mx-1">
              Go to next page
            </span>
            <IconComponent name="ChevronRight" className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
