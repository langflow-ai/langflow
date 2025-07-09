import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import { testIdCase } from "@/utils/utils";
import { useEffect, useState } from "react";
import type { InputProps, TabComponentType } from "../../types";

export default function TabComponent({
  id,
  value,
  editNode,
  handleOnNewValue,
  disabled,
  options = [],
  ...baseInputProps
}: InputProps<string, TabComponentType>) {
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

  // Handle tab change
  const handleTabChange = (value: string) => {
    setActiveTab(value);
    handleOnNewValue({ value }, {});
  };

  // Validate tab values - maximum 3 tabs, each with maximum 20 characters
  const validOptions = options
    .slice(0, 3)
    .map((tab) => (tab.length > 20 ? tab.substring(0, 20) : tab));

  return (
    <div className="w-full">
      <Tabs
        defaultValue={activeTab}
        value={activeTab}
        onValueChange={handleTabChange}
        className={`w-full ${disabled ? "pointer-events-none opacity-70" : ""}`}
      >
        <TabsList className="w-full">
          {validOptions.map((tab, index) => (
            <TabsTrigger
              key={`${id}_tab_${index}`}
              value={tab}
              className="block flex-1 truncate px-2"
              disabled={disabled}
              data-testid={`tab_${index}_${testIdCase(tab)}`}
            >
              {tab}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  );
}
