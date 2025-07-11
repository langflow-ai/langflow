import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { ChangeEvent, KeyboardEvent } from "react";

type InputSearchComponentProps = {
  loading: boolean;
  divClasses?: string;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  onClick?: () => void;
  value: string;
  onKeyDown: (e: KeyboardEvent<HTMLInputElement>) => void;
};

const InputSearchComponent = ({
  loading,
  divClasses,
  onChange,
  onClick,
  value,
  onKeyDown,
}: InputSearchComponentProps) => {
  const pagePath = window.location.pathname;

  const getSearchPlaceholder = () => {
    if (pagePath.includes("flows")) {
      return "Search Flows";
    } else if (pagePath.includes("components")) {
      return "Search Components";
    } else {
      return "Search Flows and Components";
    }
  };

  return (
    <>
      <div className={`${divClasses ? divClasses : "relative h-12 w-[60%]"}`}>
        <Input
          data-testid="search-store-input"
          disabled={loading}
          placeholder={getSearchPlaceholder()}
          className="h-12 pr-12 pl-5"
          onChange={onChange}
          onKeyDown={onKeyDown}
          value={value}
        />
        <button
          onClick={onClick}
          disabled={loading}
          className="text-muted-foreground absolute top-0 right-4 bottom-0 my-auto h-6 cursor-pointer stroke-1"
          data-testid="search-store-button"
        >
          <ForwardedIconComponent
            name={loading ? "Loader2" : "Search"}
            className={loading ? "animate-spin cursor-not-allowed" : ""}
          />
        </button>
      </div>
    </>
  );
};
export default InputSearchComponent;
