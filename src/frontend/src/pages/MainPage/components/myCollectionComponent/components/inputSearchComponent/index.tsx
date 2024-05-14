import { useState } from "react";
import { Input } from "../../../../../../components/ui/input";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";

type InputSearchComponentProps = {
  loading: boolean;
  isFlowPage: boolean;
};

const InputSearchComponent = ({
  loading,
  isFlowPage,
}: InputSearchComponentProps) => {
  const [inputValue, setInputValue] = useState("");
  const allFlows = useFlowsManagerStore((state) => state.allFlows);

  const setSearchFlowsComponents = useFlowsManagerStore(
    (state) => state.setSearchFlowsComponents
  );

  const searchFlowsComponents = useFlowsManagerStore(
    (state) => state.searchFlowsComponents
  );

  const disableInputSearch =
    loading ||
    !allFlows ||
    (allFlows?.length === 0 && searchFlowsComponents === "");

  return (
    <>
      <div className="relative h-12 w-[40%]">
        <Input
          data-testid="search-store-input"
          disabled={disableInputSearch}
          placeholder={`Search ${isFlowPage ? "flows" : "components"}`}
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
