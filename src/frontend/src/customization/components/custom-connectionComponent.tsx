import ConnectionComponent, {
  type ConnectionComponentProps,
} from "@/components/core/parameterRenderComponent/components/connectionComponent";
import type { InputProps } from "@/components/core/parameterRenderComponent/types";

const CustomConnectionComponent = ({
  tooltip = "",
  name,
  helperText = "",
  helperMetadata = { icon: undefined, variant: "muted-foreground" },
  options = [],
  searchCategory = [],
  buttonMetadata = { variant: "destructive", icon: "unplug" },
  connectionLink = "",
  ...baseInputProps
}: InputProps<any, ConnectionComponentProps>) => {
  return (
    <ConnectionComponent
      {...baseInputProps}
      name={name}
      helperMetadata={helperMetadata}
      options={options}
      searchCategory={searchCategory}
      buttonMetadata={buttonMetadata}
      connectionLink={connectionLink}
    />
  );
};

export default CustomConnectionComponent;
