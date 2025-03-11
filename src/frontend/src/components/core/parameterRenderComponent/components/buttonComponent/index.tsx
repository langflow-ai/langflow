import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";

import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "@/utils/utils";
import { useEffect, useRef, useState } from "react";
import { ReactSortable } from "react-sortablejs";

type ButtonComponentProps = {
  tooltip?: string;
  type: "tool_name" | "actions" | undefined;
  name?: string;
};

const ButtonComponent = ({
  tooltip = "",
  type,
  name,
}: ButtonComponentProps) => {
  const isDropdown = type !== "actions";
  const [open, setOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const helperIcon = "OctagonAlert";

  const handleAuthButtonClick = () => {
    setIsAuthenticated(!isAuthenticated);

    window.open("https://en.wikipedia.org/wiki/DataStax", "_blank");
  };

  const [actionData, setActionData] = useState<any[]>([]);

  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex w-full flex-row gap-2">
        <Button
          variant={isDropdown ? "primary" : "default"}
          size="xs"
          role="combobox"
          onClick={() => {
            if (!isAuthenticated && !isDropdown) {
              setIsAuthenticated(!isAuthenticated);
            } else {
              setOpen(true);
            }
          }}
          className="dropdown-component-outline input-edit-node w-full py-2"
        >
          {isDropdown ? (
            <div
              className={cn("flex w-full items-center justify-start text-sm")}
            >
              {actionData[0]?.icon && (
                <ForwardedIconComponent
                  name={actionData[0]?.icon}
                  className="mr-3 h-5 w-5"
                />
              )}
              {actionData.length > 0
                ? actionData.map((action) => action.name).join(", ")
                : "Select a tool..."}
              <ForwardedIconComponent
                name="ChevronsUpDown"
                className="ml-auto h-5 w-5"
              />
            </div>
          ) : (
            <div className={cn("flex items-center text-sm font-semibold")}>
              {name || "Select action"}
            </div>
          )}
        </Button>
        {isDropdown && !isAuthenticated && (
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
      {!isDropdown && !isAuthenticated && (
        <div className="flex w-full flex-row items-center gap-2">
          <ForwardedIconComponent
            name={helperIcon ? helperIcon : "AlertCircle"}
            className={cn("h-5 w-5", !isAuthenticated && "text-destructive")}
          />
          <div
            className={cn(
              "flex w-full flex-col text-xs text-muted-foreground",
              !isAuthenticated && "text-destructive",
            )}
          >
            Please connect before selecting tools
          </div>
        </div>
      )}

      {!isDropdown && (
        <div className="flex w-full flex-col">
          <ReactSortable
            list={actionData}
            setList={setActionData}
            className="flex w-full flex-col"
          >
            {actionData.map((data, index) => (
              <li
                key={data?.id}
                className="group inline-flex h-12 w-full cursor-grab items-center gap-2 text-sm font-medium text-gray-800"
              >
                <ForwardedIconComponent
                  name="grid-horizontal"
                  className="h-5 w-5 fill-gray-300 text-gray-300"
                />

                <div className="flex w-full items-center gap-x-2">
                  <div className="flex h-5 w-5 items-center justify-center rounded-full bg-gray-400 text-center text-white">
                    {index + 1}
                  </div>

                  <span className="max-w-48 truncate text-primary">
                    {data.name}
                  </span>
                </div>
                <Button
                  size="icon"
                  variant="outline"
                  className="ml-auto h-7 w-7 opacity-0 transition-opacity duration-200 hover:border hover:border-destructive hover:bg-transparent hover:opacity-100"
                  onClick={() => {
                    setActionData(actionData.filter((_, i) => i !== index));
                  }}
                >
                  <ForwardedIconComponent
                    name="x"
                    className="h-6 w-6 text-red-500"
                  />
                </Button>
              </li>
            ))}
          </ReactSortable>
        </div>
      )}

      <ListSelectionComponent
        open={open}
        onClose={() => setOpen(false)}
        hasSearch={isDropdown}
        setSelectedAction={setActionData}
        selectedAction={actionData}
        type={!isDropdown}
      />
    </div>
  );
};

export default ButtonComponent;
