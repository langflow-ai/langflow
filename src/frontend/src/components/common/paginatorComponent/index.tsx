import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const [size, setPageSize] = useState(pageSize);
  const [maxIndex, setMaxPageIndex] = useState(
    Math.max(1, Math.ceil(totalRowsCount / pageSize)),
  );

  useEffect(() => {
    setMaxPageIndex(pages ?? Math.max(1, Math.ceil(totalRowsCount / size)));
  }, [totalRowsCount]);

  const disableFirstPage = pageIndex <= 1;
  const disableLastPage = pageIndex >= maxIndex;

  const _handleValueChange = (pageSize: string) => {
    setPageSize(Number(pageSize));
    setMaxPageIndex(
      pages ?? Math.max(1, Math.ceil(totalRowsCount / Number(pageSize))),
    );
    paginate(1, Number(pageSize));
  };

  const itemLabel =
    isComponent === undefined ? "items" : isComponent ? "components" : "flows";
  const isEmpty = totalRowsCount === 0;
  const rangeStart = (pageIndex - 1) * pageSize + 1;
  const rangeEnd = Math.min(
    totalRowsCount,
    (pageIndex - 1) * pageSize + pageSize,
  );

  return (
    <div className="flex flex-1 items-center justify-between px-6">
      <div className="flex items-center justify-end gap-1 text-mmd text-secondary-foreground">
        {isEmpty ? (
          <span className="text-muted-foreground">
            {isComponent === undefined
              ? t("paginator.ofItems", { total: 0 })
              : isComponent
                ? t("paginator.ofComponents", { total: 0 })
                : t("paginator.ofFlows", { total: 0 })}
          </span>
        ) : (
          <>
            {rangeStart}-{rangeEnd}{" "}
            <span className="text-muted-foreground">
              of{" "}
              {isComponent === undefined
                ? t("paginator.ofItems", { total: totalRowsCount })
                : isComponent
                  ? t("paginator.ofComponents", { total: totalRowsCount })
                  : t("paginator.ofFlows", { total: totalRowsCount })}
            </span>
          </>
        )}
      </div>
      <div className={"flex items-center gap-2"}>
        <div className="flex items-center gap-1 text-mmd text-secondary-foreground">
          <Select
            onValueChange={(value) => paginate(Number(value), size)}
            value={pageIndex.toString()}
          >
            <SelectTrigger
              direction="up"
              className="h-7 w-fit gap-1 border-none p-1 pl-1.5 text-mmd focus:border-none focus:ring-0 focus:!ring-offset-0"
            >
              <SelectValue placeholder={t("paginator.placeholder")} />
            </SelectTrigger>
            <SelectContent>
              {Array.from({ length: maxIndex }, (_, i) => i + 1).map((item) => (
                <SelectItem key={item} value={item.toString()}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="text-muted-foreground">
            {t("paginator.ofPages", { maxIndex })}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            disabled={disableFirstPage}
            onClick={() => {
              if (pageIndex > 0) {
                paginate(pageIndex - 1, size);
              }
            }}
            variant="ghost"
            size={"iconMd"}
          >
            <span className="sr-only">{t("paginator.previousPage")}</span>
            <IconComponent name="ChevronLeft" className="h-4 w-4" />
          </Button>
          <Button
            disabled={disableLastPage}
            onClick={() => {
              paginate(pageIndex + 1, size);
            }}
            variant="ghost"
            size={"iconMd"}
          >
            <span className="sr-only">{t("paginator.nextPage")}</span>
            <IconComponent name="ChevronRight" className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
