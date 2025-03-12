import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "@/utils/utils";
import { memo, useCallback, useState } from "react";
import { ReactSortable } from "react-sortablejs";
import { InputProps } from "../../types";

type ListComponentProps = {
  tooltip?: string;
  name?: string;
  helperText?: string;
  auth?: boolean;
  showSortable?: boolean;
};

const AuthButtonContent = memo(
  ({ actionData, placeholder }: { actionData: any[]; placeholder: string }) => (
    <div className={cn("flex w-full items-center justify-start text-sm")}>
      {actionData[0]?.icon && (
        <ForwardedIconComponent
          name={actionData[0]?.icon}
          className="mr-3 h-5 w-5"
        />
      )}
      {actionData.length > 0
        ? actionData.map((action) => action.name).join(", ")
        : placeholder}
      <ForwardedIconComponent
        name="ChevronsUpDown"
        className="ml-auto h-5 w-5"
      />
    </div>
  ),
);

const NonAuthButtonContent = memo(
  ({ placeholder }: { placeholder: string }) => (
    <div className={cn("flex items-center text-sm font-semibold")}>
      {placeholder}
    </div>
  ),
);

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

const HelperTextSection = memo(
  ({
    helperText,
    variant = "destructive", // TODO: Remove this default value
    icon = "OctagonAlert", // TODO: Remove this default value
  }: {
    helperText: string;
    variant?: string;
    icon?: string;
  }) => (
    <div className="flex w-full flex-row items-center gap-2">
      {icon && (
        <ForwardedIconComponent
          name={icon}
          className={cn(`h-5 w-5`, variant && `text-${variant}`)}
        />
      )}
      <div
        className={cn(
          "flex w-full flex-col text-xs text-muted-foreground",
          variant && `text-${variant}`,
        )}
      >
        {helperText}
      </div>
    </div>
  ),
);

const ListComponent = ({
  tooltip = "",
  name,
  helperText,
  auth,
  showSortable = true,
  ...baseInputProps
}: InputProps<any, ListComponentProps>) => {
  const { placeholder } = baseInputProps;
  const [open, setOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [actionData, setActionData] = useState<any[]>([]);

  const handleAuthButtonClick = useCallback(() => {
    setIsAuthenticated((prev) => !prev);
    window.open("https://en.wikipedia.org/wiki/DataStax", "_blank");
  }, []);

  const handleOpenDialog = useCallback(() => setOpen(true), []);
  const handleCloseDialog = useCallback(() => setOpen(false), []);

  const createRemoveHandler = useCallback((index: number) => {
    return () => {
      setActionData((current) => current.filter((_, i) => i !== index));
    };
  }, []);

  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex w-full flex-row gap-2">
        <Button
          variant={auth ? "primary" : "default"}
          size="xs"
          role="combobox"
          onClick={handleOpenDialog}
          className="dropdown-component-outline input-edit-node w-full py-2"
        >
          {auth ? (
            <AuthButtonContent
              actionData={actionData}
              placeholder={placeholder || "Select an option"}
            />
          ) : (
            <NonAuthButtonContent
              placeholder={placeholder || "Select option"}
            />
          )}
        </Button>
        {auth && !isAuthenticated && (
          <Button
            size="icon"
            variant="destructive"
            className="h-9 w-10 rounded-md border border-destructive"
            onClick={handleAuthButtonClick}
          >
            <ForwardedIconComponent
              name="unplug"
              className="h-5 w-5 text-destructive"
            />
          </Button>
        )}
      </div>

      {/* TODO: add variant and icon to this */}
      {helperText && <HelperTextSection helperText={helperText} />}

      {showSortable && !auth && actionData.length > 0 && (
        <div className="flex w-full flex-col">
          <ReactSortable
            list={actionData}
            setList={setActionData}
            className="flex w-full flex-col"
          >
            {actionData.map((data, index) => (
              <SortableListItem
                key={data?.id || index}
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
        onClose={handleCloseDialog}
        hasSearch={auth}
        setSelectedAction={setActionData}
        selectedAction={actionData}
        type={!auth}
      />
    </div>
  );
};

export default memo(ListComponent);
