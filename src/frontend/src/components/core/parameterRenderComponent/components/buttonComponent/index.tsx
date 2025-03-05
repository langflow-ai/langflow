import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";

import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { cn } from "@/utils/utils";
import { useEffect, useRef, useState } from "react";
import Sortable from "sortablejs";

type ButtonComponentProps = {
  tooltip?: string;
  type: "tool_name" | "actions" | undefined;
};

const ButtonComponent = ({ tooltip = "", type }: ButtonComponentProps) => {
  const [open, setOpen] = useState(false);
  const sortableRef = useRef(null);

  useEffect(() => {
    if (sortableRef?.current) {
      new Sortable(sortableRef.current, {
        animation: 150,
        dragClass: "rounded-none!",
      });
    }
  }, []);

  const actionData = [
    {
      name: "Accept a repository invitation",
      id: 1,
    },
    {
      name: "Add an email address for the repository",
      id: 2,
    },
    {
      name: "Add assignee to an issue",
      id: 3,
    },
  ];

  return (
    <>
      {type === "tool_name" ? (
        <div className="flex w-full flex-row gap-2">
          <Button
            variant="outline"
            size="xs"
            onClick={() => setOpen(true)}
            className="w-full py-2"
          >
            <div className="flex w-full items-center justify-start text-sm">
              Select a tool...
              <ForwardedIconComponent
                name="ChevronsUpDown"
                className="ml-auto h-5 w-5"
              />
            </div>
          </Button>
          <Button
            size="icon"
            className="h-9 w-10 bg-yellow-600 hover:bg-yellow-800"
            onClick={() => setOpen(true)}
          >
            <ForwardedIconComponent name="lock" className="h-5 w-5" />
          </Button>
        </div>
      ) : (
        <div className="flex w-full flex-col gap-2">
          <div className="flex w-full flex-row gap-2">
            <Button
              variant="default"
              size="xs"
              onClick={() => setOpen(true)}
              className="w-full py-2"
            >
              <div className="flex items-center text-sm font-semibold">
                Select action
              </div>
            </Button>
          </div>
          <div className="flex w-full flex-col">
            <ul className="flex w-full flex-col" ref={sortableRef}>
              {actionData.map((data, index) => (
                <li
                  key={data?.id}
                  className="group inline-flex h-12 w-full cursor-grab items-center text-sm font-medium text-gray-800"
                >
                  <ForwardedIconComponent
                    name="grid-horizontal"
                    className="h-5 w-5 fill-gray-300 text-gray-300"
                  />

                  <div className="absolute left-12 flex w-full items-center gap-x-2">
                    <div className="h-5 w-5 items-center justify-center rounded-full bg-gray-400 text-center text-white">
                      {index + 1}
                    </div>

                    <span className="max-w-48 truncate">{data.name}</span>
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="absolute right-5 h-7 w-7 opacity-0 transition-opacity duration-200 hover:bg-red-100 hover:opacity-100"
                    onClick={() => {
                      console.log("clicked");
                    }}
                  >
                    <ForwardedIconComponent
                      name="x"
                      className="h-6 w-6 text-red-500"
                    />
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <ListSelectionComponent open={open} onClose={() => setOpen(false)} />
    </>

    // <ListSelectionComponent open={open} onClose={() => setOpen(false)} />
  );
};

export default ButtonComponent;
