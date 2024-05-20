import { useState } from "react";
import { Input } from "../../../../../../components/ui/input";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";

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
      <div className="relative h-12 w-[40%]">
        <Input
          data-testid="search-store-input"
          disabled={disableInputSearch}
          placeholder={getSearchPlaceholder()}
          className="absolute h-12 pl-5 pr-7"
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
      </div>
    </>
  );
};
export default InputSearchComponent;
