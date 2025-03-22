import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "@/utils/utils";
import { memo, useCallback, useState } from "react";
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
};

const SortableListItem = memo(
  ({
    data,
    index,
    onRemove,
  }: {
    data: any;
    index: number;
    onRemove: () => void;
  }) => (
    <li className="group inline-flex h-12 w-full cursor-grab items-center gap-2 text-sm font-medium text-gray-800">
      <ForwardedIconComponent
        name="grid-horizontal"
        className="h-5 w-5 fill-gray-300 text-gray-300"
      />

      <div className="flex w-full items-center gap-x-2">
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-gray-400 text-center text-white">
          {index + 1}
        </div>

        <span className="max-w-48 truncate text-primary">{data.name}</span>
      </div>
      <Button
        size="icon"
        variant="outline"
        className="ml-auto h-7 w-7 opacity-0 transition-opacity duration-200 hover:border hover:border-destructive hover:bg-transparent hover:opacity-100"
        onClick={onRemove}
      >
        <ForwardedIconComponent name="x" className="h-6 w-6 text-red-500" />
      </Button>
    </li>
  ),
);

const SortableListComponent = ({
  tooltip = "",
  name,
  helperText = "",
  helperMetadata = { icon: undefined, variant: "muted-foreground" },
  options = [],
  searchCategory = [],
  ...baseInputProps
}: InputProps<any, SortableListComponentProps>) => {
  const { placeholder, handleOnNewValue } = baseInputProps;
  const [open, setOpen] = useState(false);
  const [listData, setListData] = useState<any[]>([]);

  const createRemoveHandler = useCallback((index: number) => {
    return () => {
      setListData((current) => current.filter((_, i) => i !== index));
    };
  }, []);

  const handleOpenListSelectionDialog = useCallback(() => setOpen(true), []);
  const handleCloseListSelectionDialog = useCallback(() => setOpen(false), []);

  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex w-full flex-row gap-2">
        <Button
          variant="default"
          size="xs"
          role="combobox"
          onClick={handleOpenListSelectionDialog}
          className="dropdown-component-outline input-edit-node w-full py-2"
        >
          <div className={cn("flex items-center text-sm font-semibold")}>
            {placeholder}
          </div>
        </Button>
      </div>

      {helperText && (
        <HelperTextComponent
          helperText={helperText}
          helperMetadata={helperMetadata}
        />
      )}

      {listData.length > 0 && (
        <div className="flex w-full flex-col">
          <ReactSortable
            list={listData}
            setList={setListData}
            className="flex w-full flex-col"
          >
            {listData.map((data, index) => (
              <SortableListItem
                key={data?.name || index}
                data={data}
                index={index}
                onRemove={createRemoveHandler(index)}
              />
            ))}
          </ReactSortable>
        </div>
      )}

      <ListSelectionComponent
        open={open}
        onClose={handleCloseListSelectionDialog}
        searchCategories={searchCategory}
        setSelectedList={setListData}
        selectedList={listData}
        options={options}
        type="multiple"
      />
    </div>
  );
};

export default memo(SortableListComponent);
