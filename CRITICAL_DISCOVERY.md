# CRITICAL DISCOVERY: Working Tool → Agent Edge Pattern

## Meeting Notes Agent: Direct Tool → Agent Connection (NO GAP)

### Working Edge Pattern
```json
{
  "source": "NotionSearch-M66HF",
  "sourceHandle": "{œdataTypeœ:œNotionSearchœ,œidœ:œNotionSearch-M66HFœ,œnameœ:œexample_tool_outputœ,œoutput_typesœ:[œToolœ]}",
  "target": "ToolCallingAgent-rVWeq",
  "targetHandle": "{œfieldNameœ:œtoolsœ,œidœ:œToolCallingAgent-rVWeqœ,œinputTypesœ:[œToolœ,œBaseToolœ],œtypeœ:œotherœ}",
  "data": {
    "sourceHandle": {
      "dataType": "NotionSearch",
      "id": "NotionSearch-M66HF",
      "name": "example_tool_output",
      "output_types": ["Tool"]
    },
    "targetHandle": {
      "fieldName": "tools",
      "id": "ToolCallingAgent-rVWeq",
      "inputTypes": ["Tool", "BaseTool"],
      "type": "other"
    }
  },
  "id": "reactflow__edge-NotionSearch-M66HF{...}-ToolCallingAgent-rVWeq{...}"
}
```

## KEY DIFFERENCES IDENTIFIED

### 1. Source Handle Name
- **Working**: `"name": "example_tool_output"`
- **Our Converter**: `"name": "component_as_tool"`

### 2. Target Input Types
- **Working**: `"inputTypes": ["Tool", "BaseTool"]`
- **Our Converter**: `"inputTypes": ["Tool"]`

### 3. Edge ID Format
- **Working**: `"reactflow__edge-"`
- **Our Converter**: `"xy-edge__"` (we changed this)

## HYPOTHESIS

The visual gap is caused by:

1. **Output field name mismatch**: Frontend expects `"example_tool_output"` but we provide `"component_as_tool"`
2. **Input type mismatch**: Frontend expects `["Tool", "BaseTool"]` but we provide `["Tool"]`
3. **Possible edge ID format issue**: Frontend might expect `reactflow__edge-` prefix

## NEXT STEPS

1. Extract the complete NotionSearch node structure to see what makes `example_tool_output` work
2. Extract the complete ToolCallingAgent node structure to see the `["Tool", "BaseTool"]` input definition
3. Compare with our converter's output
4. Test fixes:
   - Change output name to `example_tool_output`
   - Add `BaseTool` to input types
   - Revert edge ID to `reactflow__edge-`

This is the breakthrough we needed!