import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";

import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { useEffect, useRef, useState } from "react";
import Sortable from "sortablejs";

type ButtonComponentProps = {
  tooltip?: string;
};

const ButtonComponent = ({ tooltip = "" }: ButtonComponentProps) => {
  const [open, setOpen] = useState(false);
  const sortableRef = useRef(null);

  useEffect(() => {
    if (sortableRef.current) {
      new Sortable(sortableRef.current, {
        animation: 150,
        dragClass: "rounded-none!",
      });
    }
  }, []);

  return (
    <>
      <ShadTooltip content={!(tooltip as string) ? "" : tooltip}>
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
      </ShadTooltip>
      {/* <ul
        id="hs-handle-sortable"
        className="flex w-full flex-col"
        ref={sortableRef}
      >
        <li className="group inline-flex w-full cursor-pointer items-center py-3 text-sm font-medium text-gray-800">
          <ForwardedIconComponent
            name="grid-horizontal"
            className="invisible h-5 w-5 -translate-x-1/2 transform fill-gray-300 text-gray-300 transition-transform duration-200 group-hover:visible group-hover:translate-x-0"
          />

          <div className="absolute left-6 flex w-full transform items-center gap-x-2 transition-transform duration-200 group-hover:translate-x-[25px]">
            <div className="h-5 w-5 items-center justify-center rounded-full bg-gray-400 text-center text-white">
              1
            </div>

            <span className="max-w-48 truncate">Newsletter</span>
          </div>
          <Button
            size="icon"
            variant="ghost"
            className="absolute right-5 h-7 w-7 opacity-0 transition-opacity duration-200 group-hover:bg-red-100 group-hover:opacity-100"
            onClick={() => {
              console.log("clicked");
            }}
          >
            <ForwardedIconComponent name="x" className="h-6 w-6 text-red-500" />
          </Button>
        </li>
        <li className="group inline-flex w-full cursor-pointer items-center py-3 text-sm font-medium text-gray-800">
          <ForwardedIconComponent
            name="grid-horizontal"
            className="invisible h-5 w-5 -translate-x-1/2 transform fill-gray-300 text-gray-300 transition-transform duration-200 group-hover:visible group-hover:translate-x-0"
          />

          <div className="absolute left-6 flex w-full transform items-center gap-x-2 transition-transform duration-200 group-hover:translate-x-[25px]">
            <div className="h-5 w-5 items-center justify-center rounded-full bg-gray-400 text-center text-white">
              2
            </div>

            <span className="max-w-48 truncate">
              Newsletter long text with a lot of text
            </span>
          </div>
          <Button
            size="icon"
            variant="ghost"
            className="absolute right-5 h-7 w-7 opacity-0 transition-opacity duration-200 group-hover:bg-red-100 group-hover:opacity-100"
            onClick={() => {
              console.log("clicked");
            }}
          >
            <ForwardedIconComponent name="x" className="h-6 w-6 text-red-500" />
          </Button>
        </li>
      </ul> */}

      <ListSelectionComponent open={open} onClose={() => setOpen(false)} />
    </>
  );
};

export default ButtonComponent;
