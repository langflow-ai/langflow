import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { ReactSortable } from "react-sortablejs";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import type { InputProps } from "../../types";
import HelperTextComponent from "../helperTextComponent";

type SortableListComponentProps = {
  tooltip?: string;
  name?: string;
  helperText?: string;
  helperMetadata?: any;
  options?: any[];
  searchCategory?: string[];
  icon?: string;
  limit?: number;
};

const SortableListItem = memo(
  ({
    data,
    index,
    onRemove,
    limit = 1,
  }: {
    data: any;
    index: number;
    onRemove: () => void;
    limit?: number;
  }) => (
    <li
      className={cn(
        "inline-flex h-12 w-full items-center gap-2 text-sm font-medium",
        limit === 1 ? "h-6 rounded-md bg-muted" : "group cursor-grab",
      )}
    >
      {limit !== 1 && (
        <ForwardedIconComponent
          name="GridHorizontal"
          className="h-5 w-5 text-muted-foreground"
        />
      )}

      <div className="flex w-full items-center gap-x-2">
        {limit !== 1 && (
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-border text-center text-mmd text-primary">
            {index + 1}
          </div>
        )}

        <span
          className={cn(
            "truncate text-xxs font-medium text-muted-foreground",
            limit === 1 ? "max-w-56 pl-2" : "max-w-48",
          )}
        >
          {data.name}
        </span>
      </div>
      <Button
        size="icon"
        variant={"ghost"}
        className={cn(
          "ml-auto h-6 w-6 text-muted-foreground opacity-0 transition-opacity duration-200",
          limit === 1
            ? "group pr-1 opacity-100 hover:text-foreground"
            : "hover:text-destructive group-hover:opacity-100",
        )}
        onClick={onRemove}
      >
        <ForwardedIconComponent name="x" className={cn("h-6 w-6")} />
      </Button>
    </li>
  ),
);

const SortableListComponent = ({
  tooltip = "",
  name,
  editNode = false,
  helperText = "",
  helperMetadata = { icon: undefined, variant: "muted-foreground" },
  options = [],
  searchCategory = [],
  limit,
  ...baseInputProps
}: InputProps<any, SortableListComponentProps>) => {
  const { placeholder, handleOnNewValue, value } = baseInputProps;
  const [open, setOpen] = useState(false);

  // Convert value to an array if it exists, otherwise use empty array
  const listData = useMemo(() => (Array.isArray(value) ? value : []), [value]);

  const createRemoveHandler = useCallback(
    (index: number) => () => {
      const newList = listData.filter((_, i) => i !== index);
      handleOnNewValue({ value: newList });
    },
    [listData, handleOnNewValue],
  );

  const setListDataHandler = useCallback(
    (newList: any[]) => {
      handleOnNewValue({ value: newList });
    },
    [handleOnNewValue],
  );

  const handleCloseListSelectionDialog = useCallback(() => {
    setOpen(false);
  }, []);

  const handleOpenListSelectionDialog = useCallback(() => {
    if (helperText) {
      setShowHelperText(true);
    } else {
      setOpen(true);
    }
  }, [helperText]);

  const [showHelperText, setShowHelperText] = useState(false);

  useEffect(() => {
    if (!helperText) {
      setShowHelperText(false);
    }
    if (helperText && open) {
      setOpen(false);
    }
  }, [helperText, open]);

  return (
    <div className="flex w-full flex-col">
      <div className="flex w-full flex-row gap-2">
        {!(limit === 1 && listData.length === 1) && (
          <Button
            variant="default"
            size="xs"
            role="combobox"
            onClick={handleOpenListSelectionDialog}
            className={cn(
              "dropdown-component-outline input-edit-node w-full",
              editNode ? "py-1" : "py-2",
            )}
            data-testid="button_open_list_selection"
          >
            <div
              className={cn(
                "flex items-center",
                editNode ? "text-xs" : "text-sm",
              )}
            >
              {placeholder}
            </div>
          </Button>
        )}
      </div>

      {listData.length > 0 && (
        <div className="flex w-full flex-col">
          <ReactSortable
            list={listData}
            setList={setListDataHandler}
            className={"flex w-full flex-col"}
          >
            {listData.map((data, index) => (
              <SortableListItem
                key={`${data?.name || "item"}-${index}`}
                data={data}
                index={index}
                onRemove={createRemoveHandler(index)}
                limit={limit}
              />
            ))}
          </ReactSortable>
        </div>
      )}

      {helperText && showHelperText && (
        <div className="pt-2">
          <HelperTextComponent
            helperText={helperText}
            helperMetadata={helperMetadata}
          />
        </div>
      )}

      <ListSelectionComponent
        open={open}
        onClose={handleCloseListSelectionDialog}
        searchCategories={searchCategory}
        editNode={editNode}
        setSelectedList={setListDataHandler}
        selectedList={listData}
        options={options}
        limit={limit}
        {...baseInputProps}
        headerSearchPlaceholder=""
      />
    </div>
  );
};

export default memo(SortableListComponent);
