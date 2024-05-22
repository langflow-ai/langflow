import { useState } from "react";
import { Input } from "../../../../../../components/ui/input";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";
import ForwardedIconComponent from "../../../../../../components/genericIconComponent";

type InputSearchComponentProps = {
  loading: boolean;
};

const InputSearchComponent = ({ loading }: InputSearchComponentProps) => {
  const pagePath = window.location.pathname;

  const [inputValue, setInputValue] = useState("");
  const allFlows = useFlowsManagerStore((state) => state.allFlows);

  const setSearchFlowsComponents = useFlowsManagerStore(
    (state) => state.setSearchFlowsComponents,
  );

  const searchFlowsComponents = useFlowsManagerStore(
    (state) => state.searchFlowsComponents,
  );

  const disableInputSearch =
    loading ||
    !allFlows ||
    (allFlows?.length === 0 && searchFlowsComponents === "");

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
      <div className="relative h-12 w-[60%]">
        <Input
          data-testid="search-store-input"
          disabled={disableInputSearch}
          placeholder={getSearchPlaceholder()}
          className="absolute h-12 pl-5 pr-12"
          onChange={(e) => {
            setSearchFlowsComponents(e.target.value);
            setInputValue(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setSearchFlowsComponents(inputValue);
            }
          }}
          value={inputValue}
        />
        <button
          disabled={loading}
          className="absolute bottom-0 right-4 top-0 my-auto h-6 cursor-pointer stroke-1 text-muted-foreground"
          data-testid="search-store-button"
        >
          <ForwardedIconComponent
            name={loading ? "Loader2" : "Search"}
            className={loading ? " animate-spin cursor-not-allowed" : ""}
          />
        </button>
      </div>
    </>
  );
};
export default InputSearchComponent;
