import { useState } from "react";
import { Button } from "@/components/ui/button";

interface ComboBoxItemProps {
  item: any;
}

const ComboBoxItem = ({ item }: ComboBoxItemProps) => {
  const [isChecked, setIsChecked] = useState(false);

  return (
    <div className="flex flex-row pb-1">
      <div className="inline-flex justify-start">
        <label
          className="relative flex cursor-pointer"
          htmlFor={`check-${item?.name}`}
        >
          <input
            type="checkbox"
            checked={isChecked}
            onChange={() => setIsChecked(!isChecked)}
            className="peer h-5 w-5 cursor-pointer appearance-none rounded border border-border border-muted-foreground shadow transition-all hover:shadow-md"
            id={`check-${item?.name}`}
          />
          <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 transform text-black opacity-0 peer-checked:bg-primary peer-checked:opacity-100">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-3.5 w-3.5"
              viewBox="0 0 20 20"
              fill="currentColor"
              stroke="currentColor"
              stroke-width="1"
            >
              <path
                fill-rule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clip-rule="evenodd"
              ></path>
            </svg>
          </span>
        </label>
        <Button
          unstyled
          className="mx-2 flex w-full justify-start rounded-md hover:bg-accent"
        >
          <label
            className="ml-2 flex w-72 cursor-pointer text-sm font-bold text-primary"
            htmlFor={`check-${item?.name}`}
          >
            <span className="truncate">{item?.name}</span>
          </label>

          <label
            className="flex w-72 cursor-pointer text-sm text-muted-foreground"
            htmlFor={`check-${item?.name}`}
          >
            <span className="truncate">{item?.description}</span>
          </label>
        </Button>
      </div>
    </div>
  );
};
export default ComboBoxItem;
