import ConnectionRefComponent from "@/components/core/parameterRenderComponent/components/connectionRefComponent";
import type { ConnectionRefComponentType } from "@/components/core/parameterRenderComponent/components/connectionRefComponent/types";
import type { InputProps } from "@/components/core/parameterRenderComponent/types";

/**
 * Seam for the `connection_ref` field renderer. OSS forwards to the built-in
 * picker; a distribution that ships its own connections UI replaces this file
 * to inject its renderer (for example one that can authorize a new connection
 * without leaving the canvas) without touching `ParameterRenderComponent`.
 */
const CustomConnectionRefComponent = ({
  provider,
  requiredScopes = [],
  conditionalScopes = [],
  inputValues,
  capabilities = [],
  identityKind,
  ...baseInputProps
}: InputProps<string, ConnectionRefComponentType>) => {
  return (
    <ConnectionRefComponent
      {...baseInputProps}
      provider={provider}
      requiredScopes={requiredScopes}
      conditionalScopes={conditionalScopes}
      inputValues={inputValues}
      capabilities={capabilities}
      identityKind={identityKind}
    />
  );
};

export default CustomConnectionRefComponent;
