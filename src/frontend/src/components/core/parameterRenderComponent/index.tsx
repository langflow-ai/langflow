import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import CodeAreaComponent from "@/components/core/parameterRenderComponent/components/codeAreaComponent";
import DBProviderInputComponent from "@/components/core/parameterRenderComponent/components/dbProviderInputComponent";
import ModelInputComponent from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import SliderComponent from "@/components/core/parameterRenderComponent/components/sliderComponent";
import TableNodeComponent from "@/components/core/parameterRenderComponent/components/TableNodeComponent";
import TabComponent from "@/components/core/parameterRenderComponent/components/tabComponent";
import { TEXT_FIELD_TYPES } from "@/constants/constants";
import CustomConnectionComponent from "@/customization/components/custom-connectionComponent";
import CustomInputFileComponent from "@/customization/components/custom-input-file";
import CustomLinkComponent from "@/customization/components/custom-linkComponent";
import { ENABLE_INSPECTION_PANEL } from "@/customization/feature-flags";
import { useCloudModeStore } from "@/stores/cloudModeStore";
import { useTypesStore } from "@/stores/typesStore";
import type { APIClassType, InputFieldType } from "@/types/api";
import {
  filterCloudCompatibleOptions,
  getCloudFieldOverride,
  getCloudIncompatibleOptions,
  getCloudUiMetadata,
  withCurrentCloudMetadata,
} from "@/utils/cloudMetadataUtils";
import AccordionPromptComponent from "./components/accordionPromptComponent";
import DictComponent from "./components/dictComponent";
import { EmptyParameterComponent } from "./components/emptyParameterComponent";
import FloatComponent from "./components/floatComponent";
import InputListComponent from "./components/inputListComponent";
import IntComponent from "./components/intComponent";
import KeypairListComponent from "./components/keypairListComponent";
import McpComponent from "./components/mcpComponent";
import MultiselectComponent from "./components/multiselectComponent";
import MustachePromptAreaComponent from "./components/mustachePromptComponent";
import PromptAreaComponent from "./components/promptComponent";
import QueryComponent from "./components/queryComponent";
import SortableListComponent from "./components/sortableListComponent";
import { StrRenderComponent } from "./components/strRenderComponent";
import ToolsComponent from "./components/ToolsComponent";
import ToggleShadComponent from "./components/toggleShadComponent";
import type { InputProps, NodeInfoType } from "./types";

export function ParameterRenderComponent({
  handleOnNewValue,
  name,
  nodeId,
  templateData,
  templateValue,
  editNode,
  showParameter = true,
  inspectionPanel = false,
  handleNodeClass,
  nodeClass,
  nodeType,
  disabled,
  placeholder,
  isToolMode,
  nodeInformationMetadata,
}: {
  handleOnNewValue:
    | handleOnNewValueType
    | ((value: string, key: string) => void);
  name: string;
  nodeId: string;
  templateData: Partial<InputFieldType>;
  templateValue: unknown;
  editNode: boolean;
  showParameter?: boolean;
  inspectionPanel?: boolean;
  handleNodeClass: (value: unknown, code?: string, type?: string) => void;
  nodeClass: APIClassType;
  nodeType?: string;
  disabled: boolean;
  placeholder?: string;
  isToolMode?: boolean;
  nodeInformationMetadata?: NodeInfoType;
}) {
  const cloudOnly = useCloudModeStore((state) => state.cloudOnly);
  const templates = useTypesStore((state) => state.templates);

  const effectiveNodeClass =
    cloudOnly && nodeType
      ? (withCurrentCloudMetadata(
          nodeClass,
          templates[nodeType] as APIClassType | undefined,
        ) ?? nodeClass)
      : nodeClass;

  const id = (
    templateData.type +
    "_" +
    (editNode ? "edit_" : "") +
    templateData.name
  ).toLowerCase();

  const nodeMetadata = getCloudUiMetadata(effectiveNodeClass?.metadata);

  const shouldUseCloudPlaceholder =
    cloudOnly &&
    (templateValue === "" ||
      templateValue === undefined ||
      templateValue === null);

  const cloudOverride = shouldUseCloudPlaceholder
    ? getCloudFieldOverride(nodeMetadata, name)
    : undefined;

  const renderComponent = (): React.ReactElement<InputProps> => {
    const baseInputProps: InputProps = {
      id,
      value: templateValue,
      editNode,
      handleOnNewValue: handleOnNewValue as handleOnNewValueType,
      disabled,
      nodeClass: effectiveNodeClass,
      handleNodeClass,
      nodeId,
      helperText: templateData?.helper_text,
      readonly: templateData.readonly,
      placeholder:
        cloudOverride?.placeholder ?? placeholder ?? templateData?.placeholder,
      isToolMode,
      nodeInformationMetadata,
      hasRefreshButton: templateData.refresh_button,
      showParameter,
      inspectionPanel,
    };

    if (TEXT_FIELD_TYPES.includes(templateData.type ?? "")) {
      if (templateData.list) {
        if (!templateData.options) {
          return (
            <InputListComponent
              {...baseInputProps}
              componentName={name}
              id={`inputlist_${id}`}
              listAddLabel={templateData?.list_add_label}
            />
          );
        }
        if (templateData.options) {
          return (
            <MultiselectComponent
              {...baseInputProps}
              combobox={templateData.combobox}
              options={
                (Array.isArray(templateData.options)
                  ? templateData.options
                  : [templateData.options]) || []
              }
              id={`multiselect_${id}`}
            />
          );
        }
      }
      return (
        <StrRenderComponent
          {...baseInputProps}
          nodeId={nodeId}
          nodeClass={effectiveNodeClass}
          handleNodeClass={handleNodeClass}
          templateData={templateData}
          name={name}
          display_name={templateData.display_name ?? ""}
          editNode={editNode}
        />
      );
    }
    switch (templateData.type) {
      case "NestedDict":
        return (
          <DictComponent
            name={name ?? ""}
            {...baseInputProps}
            id={`dict_${id}`}
          />
        );
      case "dict":
        return (
          <KeypairListComponent
            {...baseInputProps}
            isList={templateData.list ?? false}
            id={`keypair_${id}`}
          />
        );
      case "bool":
        return (
          <ToggleShadComponent
            size="medium"
            {...baseInputProps}
            id={`toggle_${id}`}
          />
        );
      case "link":
        return (
          <CustomLinkComponent
            {...baseInputProps}
            icon={templateData.icon}
            text={templateData.text}
            id={`link_${id}`}
          />
        );
      case "float":
        return (
          <FloatComponent
            {...baseInputProps}
            id={`float_${id}`}
            rangeSpec={templateData.rangeSpec ?? templateData.range_spec}
          />
        );
      case "int":
        return (
          <IntComponent
            {...baseInputProps}
            name={name}
            rangeSpec={templateData.rangeSpec ?? templateData.range_spec}
            id={`int_${id}`}
          />
        );
      case "file":
        return (
          <CustomInputFileComponent
            {...baseInputProps}
            fileTypes={templateData.fileTypes}
            file_path={templateData.file_path}
            isList={templateData.list ?? false}
            tempFile={templateData.temp_file ?? true}
            id={`inputfile_${id}`}
          />
        );
      case "prompt":
        return ENABLE_INSPECTION_PANEL && !baseInputProps.editNode ? (
          <AccordionPromptComponent
            {...baseInputProps}
            readonly={!!effectiveNodeClass.flow}
            field_name={name}
            id={`promptarea_${id}`}
          />
        ) : (
          <PromptAreaComponent
            {...baseInputProps}
            readonly={!!effectiveNodeClass.flow}
            field_name={name}
            id={`promptarea_${id}`}
          />
        );
      case "mustache":
        return ENABLE_INSPECTION_PANEL && !baseInputProps.editNode ? (
          <AccordionPromptComponent
            {...baseInputProps}
            readonly={!!effectiveNodeClass.flow}
            field_name={name}
            id={`mustachepromptarea_${id}`}
            isDoubleBrackets={true}
          />
        ) : (
          <MustachePromptAreaComponent
            {...baseInputProps}
            readonly={!!effectiveNodeClass.flow}
            field_name={name}
            id={`mustachepromptarea_${id}`}
          />
        );
      case "code":
        return <CodeAreaComponent {...baseInputProps} id={`codearea_${id}`} />;
      case "table":
        return (
          <TableNodeComponent
            {...baseInputProps}
            description={templateData.info || "Add or edit data"}
            columns={
              templateData?.table_schema?.columns ?? templateData?.table_schema
            }
            tableTitle={templateData?.display_name ?? "Table"}
            table_options={templateData?.table_options}
            trigger_icon={templateData?.trigger_icon}
            trigger_text={templateData?.trigger_text}
            table_icon={templateData?.table_icon}
          />
        );
      case "tools":
        return (
          <ToolsComponent
            {...baseInputProps}
            description={templateData.info || "Add or edit data"}
            title={effectiveNodeClass?.display_name ?? "Tools"}
            icon={effectiveNodeClass?.icon ?? ""}
            template={effectiveNodeClass?.template}
          />
        );
      case "slider": {
        // Slider uses a narrower value type than the generic base input props.
        // Omit the generic value from the spread so the explicit slider value wins.
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { value: _sliderValue, ...sliderInputProps } = baseInputProps;
        return (
          <SliderComponent
            {...sliderInputProps}
            value={templateValue as string | number | string[] | number[]}
            rangeSpec={templateData.rangeSpec ?? templateData.range_spec}
            minLabel={templateData?.min_label}
            maxLabel={templateData?.max_label}
            minLabelIcon={templateData?.min_label_icon}
            maxLabelIcon={templateData?.max_label_icon}
            sliderButtons={templateData?.slider_buttons}
            sliderButtonsOptions={templateData?.slider_buttons_options}
            sliderInput={templateData?.slider_input}
            id={`slider_${id}`}
          />
        );
      }
      case "sortableList": {
        // Filter out cloud-incompatible options when cloud mode is active
        const cloudIncompatibleOptions = cloudOnly
          ? getCloudIncompatibleOptions(nodeMetadata, name)
          : [];
        const sortableOptions =
          cloudOnly && cloudIncompatibleOptions.length > 0
            ? filterCloudCompatibleOptions(
                templateData?.options,
                cloudIncompatibleOptions,
              )
            : templateData?.options;
        return (
          <SortableListComponent
            {...baseInputProps}
            helperText={templateData?.helper_text}
            helperMetadata={templateData?.helper_text_metadata}
            options={sortableOptions}
            cloudIncompatibleOptions={cloudIncompatibleOptions}
            searchCategory={templateData?.search_category}
            limit={templateData?.limit}
            id={`sortablelist_${id}`}
          />
        );
      }
      case "connect": {
        const connectionOptions = templateData?.options as
          | Array<{ name?: unknown; link?: string }>
          | undefined;
        const link =
          templateData?.options?.find(
            (option: { name?: unknown; link?: unknown }) =>
              option?.name === templateValue,
          )?.link || "";

        return (
          <CustomConnectionComponent
            {...baseInputProps}
            name={name}
            nodeId={nodeId}
            nodeClass={effectiveNodeClass}
            helperText={templateData?.helper_text}
            helperMetadata={templateData?.helper_text_metadata}
            options={templateData?.options}
            searchCategory={templateData?.search_category}
            buttonMetadata={templateData?.button_metadata}
            connectionLink={link as string}
          />
        );
      }
      case "tab":
        return (
          <TabComponent
            {...baseInputProps}
            options={templateData?.options || []}
            id={`tab_${id}`}
          />
        );
      case "query":
        return (
          <QueryComponent
            {...baseInputProps}
            display_name={templateData.display_name ?? ""}
            info={templateData.info ?? ""}
            separator={templateData.separator}
            id={`query_${id}`}
          />
        );
      case "mcp":
        return (
          <McpComponent
            {...baseInputProps}
            id={`mcp_${id}`}
            editNode={editNode}
            disabled={disabled}
            value={templateValue}
          />
        );
      case "model":
        return (
          <ModelInputComponent
            {...baseInputProps}
            options={templateData?.options || []}
            placeholder={templateData?.placeholder}
            externalOptions={templateData?.external_options}
          />
        );
      case "knowledge_backend":
        return (
          <DBProviderInputComponent
            {...baseInputProps}
            id={`dbprovider_${id}`}
          />
        );
      default:
        return <EmptyParameterComponent {...baseInputProps} />;
    }
  };

  return renderComponent();
}
