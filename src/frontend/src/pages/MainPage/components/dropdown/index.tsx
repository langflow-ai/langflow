import ForwardedIconComponent from "@/components/genericIconComponent";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";

const DropdownComponent = () => {
  return (
    <>
      <DropdownMenuItem onClick={() => {}} className="cursor-pointer">
        <ForwardedIconComponent
          name="square-pen"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        Edit details
      </DropdownMenuItem>
      <DropdownMenuItem onClick={() => {}} className="cursor-pointer">
        <ForwardedIconComponent
          name="download"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        Download JSON
      </DropdownMenuItem>
      <DropdownMenuItem onClick={() => {}} className="cursor-pointer">
        <ForwardedIconComponent
          name="copy-plus"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        Duplicate
      </DropdownMenuItem>
      <DropdownMenuItem
        onClick={() => {}}
        className="cursor-pointer text-red-500"
      >
        <ForwardedIconComponent
          name="trash"
          aria-hidden="true"
          className="mr-2 h-4 w-4"
        />
        Delete
      </DropdownMenuItem>
    </>
  );
};

export default DropdownComponent;
