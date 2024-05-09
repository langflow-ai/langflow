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

  const setSearchFlowsComponents = useFlowsManagerStore(
    (state) => state.setSearchFlowsComponents,
  );

  return (
    <>
      <div className="relative h-12 w-[40%]">
        <Input
          data-testid="search-store-input"
          disabled={loading}
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
