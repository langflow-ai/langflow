import { useEffect, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { PaginatorComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";

export default function PaginatorComponent({
  pageSize = 12,
  pageIndex = 1,
  rowsCount = [12, 24, 48, 96],
  totalRowsCount = 0,
  paginate,
  storeComponent = false,
}: PaginatorComponentType) {
  const [size, setPageSize] = useState(pageSize);
  const [maxIndex, setMaxPageIndex] = useState(
    Math.ceil(totalRowsCount / pageSize)
  );

  useEffect(() => {
    setMaxPageIndex(Math.ceil(totalRowsCount / size));
  }, [totalRowsCount]);

  return (
    <>
      <div className="flex items-center justify-between px-2">
        <div className="flex-1 text-sm text-muted-foreground"></div>
        <div
          className={
            storeComponent
              ? "flex items-center lg:space-x-8 "
              : "flex items-center space-x-6 lg:space-x-8 "
          }
        >
          <div className="flex items-center space-x-2">
            <p className="text-sm font-medium">Rows per page</p>
            <Select
              onValueChange={(pageSize: string) => {
                setPageSize(Number(pageSize));
                setMaxPageIndex(Math.ceil(totalRowsCount / Number(pageSize)));
                paginate(Number(pageSize), 1);
              }}
              value={pageSize.toString()}
            >
              <SelectTrigger className="w-[100px]">
                <SelectValue placeholder="10" />
              </SelectTrigger>
              <SelectContent>
                {rowsCount.map((item, i) => (
                  <SelectItem key={i} value={item.toString()}>
                    {item}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex w-[100px] items-center justify-center text-sm font-medium">
            Page {pageIndex}
            {!storeComponent && <> of {maxIndex}</>}
          </div>
          <div className="flex items-center space-x-2">
            <Button
              disabled={pageIndex <= 1}
              variant="outline"
              className="hidden h-8 w-8 p-0 lg:flex"
              onClick={() => {
                paginate(size, 1);
              }}
            >
              <span className="sr-only">Go to first page</span>
              <IconComponent name="ChevronsLeft" className="h-4 w-4" />
            </Button>
            <Button
              disabled={pageIndex <= 1}
              onClick={() => {
                if (pageIndex > 0) {
                  paginate(size, pageIndex - 1);
                }
              }}
              variant="outline"
              className="h-8 w-8 p-0"
            >
              <span className="sr-only">Go to previous page</span>
              <IconComponent name="ChevronLeft" className="h-4 w-4" />
            </Button>
            <Button
              disabled={pageIndex === maxIndex}
              onClick={() => {
                paginate(size, pageIndex + 1);
              }}
              variant="outline"
              className="h-8 w-8 p-0"
            >
              <span className="sr-only">Go to next page</span>
              <IconComponent name="ChevronRight" className="h-4 w-4" />
            </Button>
            <Button
              disabled={pageIndex === maxIndex}
              variant="outline"
              className="hidden h-8 w-8 p-0 lg:flex"
              onClick={() => {
                paginate(size, maxIndex);
              }}
            >
              <span className="sr-only">Go to last page</span>
              <IconComponent name="ChevronsRight" className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
