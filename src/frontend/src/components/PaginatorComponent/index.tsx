import { useState } from "react";
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
  pageSize = 10,
  pageIndex = 1,
  rowsCount = [10, 20, 30],
  totalRowsCount = 0,
  paginate,
}: PaginatorComponentType) {
  const [size, setPageSize] = useState(pageSize);
  const [index, setPageIndex] = useState(pageIndex);

  const [maxIndex, setMaxPageIndex] = useState(
    Math.ceil(totalRowsCount / pageSize)
  );

  return (
    <>
      <div className="flex items-center justify-between px-2">
        <div className="flex-1 text-sm text-muted-foreground"></div>
        <div className="flex items-center space-x-6 lg:space-x-8">
          <div className="flex items-center space-x-2">
            <p className="text-sm font-medium">Rows per page</p>
            <Select
              onValueChange={(pageSize: string) => {
                setPageSize(Number(pageSize));
                setMaxPageIndex(Math.ceil(totalRowsCount / Number(pageSize)));
                paginate(Number(pageSize), index);
              }}
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
            Page {index} of {maxIndex}
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              className="hidden h-8 w-8 p-0 lg:flex"
              onClick={() => {
                setPageIndex(1);
                paginate(size, 1);
              }}
            >
              <span className="sr-only">Go to first page</span>
              <IconComponent name="ChevronsLeft" className="h-4 w-4" />
            </Button>
            <Button
              onClick={() => {
                if (index <= 1) {
                  setPageIndex(1);
                  paginate(size, 1);
                } else {
                  {
                    setPageIndex(index - 1);
                    paginate(size, index - 1);
                  }
                }
              }}
              variant="outline"
              className="h-8 w-8 p-0"
            >
              <span className="sr-only">Go to previous page</span>
              <IconComponent name="ChevronLeft" className="h-4 w-4" />
            </Button>
            <Button
              onClick={() => {
                if (index >= maxIndex) {
                  setPageIndex(maxIndex);
                  paginate(size, maxIndex);
                } else {
                  setPageIndex(index + 1);
                  paginate(size, index + 1);
                }
              }}
              variant="outline"
              className="h-8 w-8 p-0"
            >
              <span className="sr-only">Go to next page</span>
              <IconComponent name="ChevronRight" className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              className="hidden h-8 w-8 p-0 lg:flex"
              onClick={() => {
                setPageIndex(maxIndex);
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
