import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "@/utils/utils";
import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { ReactSortable } from "react-sortablejs";
import { InputProps } from "../../types";
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
        limit === 1 ? "bg-muted h-6 rounded-md" : "group cursor-grab",
      )}
    >
      {limit !== 1 && (
        <ForwardedIconComponent
          name="GridHorizontal"
          className="text-muted-foreground h-5 w-5"
        />
      )}

      <div className="flex w-full items-center gap-x-2">
        {limit !== 1 && (
          <div className="bg-border text-mmd text-primary flex h-5 w-5 items-center justify-center rounded-full text-center">
            {index + 1}
          </div>
        )}

        <span
          className={cn(
            "text-xxs text-muted-foreground truncate font-medium",
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
          "text-muted-foreground ml-auto h-6 w-6 opacity-0 transition-opacity duration-200",
          limit === 1
            ? "group hover:text-foreground pr-1 opacity-100"
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
      />
    </div>
  );
};

export default memo(SortableListComponent);
