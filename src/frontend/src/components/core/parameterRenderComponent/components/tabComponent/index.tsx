import { useEffect, useState } from "react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs-button";
import { testIdCase } from "@/utils/utils";
import type { InputProps, TabComponentType } from "../../types";

export default function TabComponent({
  id,
  value,
  editNode,
  handleOnNewValue,
  disabled,
  options = [],
  showParameter = true,
  ariaLabelledBy,
  ...baseInputProps
}: InputProps<string, TabComponentType>): JSX.Element | null {
  const [activeTab, setActiveTab] = useState<string>(value || "");

  // Update the active tab when the component props change
  useEffect(() => {
    if (options.length > 0) {
      // If value is one of the options, use it
      if (value && options.includes(value)) {
        setActiveTab(value);
      }
    }
  }, [options, value]);

  // Validate tab values - maximum 3 tabs, each with maximum 20 characters
  const validOptions = options
    .slice(0, 3)
    .map((tab) => (tab.length > 20 ? tab.substring(0, 20) : tab));

  // Radix derives each trigger/content pair's DOM id (and aria-controls,
  // aria-labelledby) directly from the Tabs `value`, with no escaping.
  // aria-controls is a whitespace-separated IDREF list, so option text
  // containing a space (e.g. "Option A") breaks into two dangling
  // references instead of one valid id. Index-based tokens sidestep that;
  // the real option text is still what gets emitted via handleOnNewValue.
  //
  // Don't clamp a miss to 0 — that would make the first tab render as
  // selected even though the stored value doesn't match any option (e.g.
  // it's the 4th+ option, or over the 20-char truncation limit). Radix
  // selecting nothing is the honest state; silently claiming the first
  // tab is selected would let a user "confirm" a value they can't see.
  const activeIndex = validOptions.indexOf(activeTab);
  const tabsValue = activeIndex === -1 ? "" : String(activeIndex);

  const handleTabChange = (indexToken: string) => {
    const tab = validOptions[Number(indexToken)];
    setActiveTab(tab);
    handleOnNewValue({ value: tab }, {});
  };

  if (!showParameter) {
    return null;
  }

  return (
    <div className="w-full">
      <Tabs
        value={tabsValue}
        onValueChange={handleTabChange}
        className={`w-full ${disabled ? "pointer-events-none opacity-70" : ""}`}
      >
        <TabsList className="w-full" aria-labelledby={ariaLabelledBy}>
          {validOptions.map((tab, index) => (
            <TabsTrigger
              key={`${id}_tab_${index}`}
              value={String(index)}
              className="block flex-1 truncate px-2"
              disabled={disabled}
              data-testid={`tab_${index}_${testIdCase(tab)}`}
            >
              {tab}
            </TabsTrigger>
          ))}
        </TabsList>
        {validOptions.map((_tab, index) => (
          <TabsContent
            key={`${id}_tab_content_${index}`}
            value={String(index)}
            className="mt-0"
            tabIndex={-1}
          />
        ))}
      </Tabs>
    </div>
  );
}
