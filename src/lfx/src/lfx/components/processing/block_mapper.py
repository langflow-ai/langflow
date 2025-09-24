"""Block Mapper - Maps LLM/BERT responses to final structured blocks."""

import json
from collections import defaultdict
from typing import Dict, List

from lfx.custom.custom_component.component import Component
from langflow.inputs import DataInput, HandleInput
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message


class BlockGenerator:
    """Core block generation and mapping logic."""

    @staticmethod
    def merge_blocks_with_spans(blocks: List[Dict], elements_map: Dict) -> List[Dict]:
        """Merge blocks with spans to handle continuous sections."""
        merged_blocks = []
        i = 0
        n = len(blocks)

        current_block_id = None
        current_block_type = None
        current_elements = []

        while i < n:
            block = blocks[i]
            bid = block["block_id"]
            btype = block["block_type"]
            eid = block["elements"]

            if bid:
                # If continuing the same block_id
                if current_block_id == bid:
                    if eid in elements_map:
                        current_elements.append(elements_map[eid])
                else:
                    # Commit previous block
                    if current_block_id is not None:
                        merged_blocks.append(
                            {
                                "name": current_block_id,
                                "type": current_block_type,
                                "content": current_elements,
                            }
                        )

                    # Start new block
                    current_block_id = bid
                    current_block_type = btype
                    current_elements = [elements_map.get(eid, {"element_id": eid})]

                i += 1

            else:  # Empty block_id
                # Check ahead to see if same block_id resumes
                j = i + 1
                found = False
                while j < n:
                    if blocks[j]["block_id"]:
                        if blocks[j]["block_id"] == current_block_id:
                            found = True
                        break
                    j += 1

                if found and current_block_id is not None:
                    # Include empty block in current span
                    if eid in elements_map:
                        current_elements.append(elements_map[eid])
                else:
                    # Commit previous block before handling stand-alone empty block
                    if current_block_id is not None:
                        merged_blocks.append(
                            {
                                "name": current_block_id,
                                "type": current_block_type,
                                "content": current_elements,
                            }
                        )
                        current_block_id = None
                        current_elements = []

                    # Add this empty block as standalone
                    merged_blocks.append(
                        {
                            "name": "",
                            "type": btype,
                            "content": [elements_map.get(eid, {"element_id": eid})],
                        }
                    )

                i += 1

        # Final commit
        if current_block_id is not None and current_elements:
            merged_blocks.append(
                {
                    "name": current_block_id,
                    "type": current_block_type,
                    "content": current_elements,
                }
            )

        return merged_blocks

    @staticmethod
    def extract_hf_structural_blocks(sections: List, elements_map: Dict) -> List[Dict]:
        """Extract header/footer structural blocks."""
        structural_blocks = []

        for section in sections:
            for tag in ["headers", "footers"]:
                if tag in section:
                    for file_name, block_data in section[tag].items():
                        block_id = file_name.replace(".xml", "")
                        block_type = "structural"
                        elements = []

                        for content_item in block_data.get("content", []):
                            if "element_id" in content_item:
                                element = elements_map.get(
                                    content_item["element_id"],
                                    {"element_id": content_item["element_id"]},
                                )
                                elements.append(element)

                        structural_blocks.append(
                            {
                                "name": block_id,
                                "type": block_type,
                                "content": elements,
                            }
                        )

        return structural_blocks

    @staticmethod
    def map_blocks(
        cleaned_original_lines: Dict,
        structural_ids: List,
        empty_ids: List,
        ordered_ids: List,
        parsed_output: Dict,
        file_name: str,
        elements_map: Dict,
    ) -> Dict:
        """Map LLM/BERT output to final block structure."""
        llm_extracted_data = parsed_output
        llm_input_data = cleaned_original_lines

        # Step 1: Build element_id map from llm_input_data
        element_id_map = {
            key: value["element_id"]
            for key, value in llm_input_data.items()
            if isinstance(value, dict) and "element_id" in value
        }

        # Step 2: Replace paragraph references in element_ids with actual values
        for block, block_data in llm_extracted_data.items():
            if "element_ids" in block_data:
                updated_ids = []
                for para in block_data["element_ids"]:
                    # Check if it's a paragraph reference or actual ID
                    if para in element_id_map:
                        updated_ids.append(element_id_map[para])
                    else:
                        updated_ids.append(para)
                block_data["element_ids"] = updated_ids

        # Step 3: Build a mapping from element_id to block_name
        id_to_block = {}
        for block, data in llm_extracted_data.items():
            for eid in data.get("element_ids", []):
                id_to_block[eid] = block

        # Step 4: Determine used_ids and missing_ids
        all_input_ids = set(element_id_map.values())
        used_ids = set(id_to_block.keys())
        structural_set = set(structural_ids)
        empty_set = set(empty_ids)
        missing_ids = all_input_ids - (used_ids | structural_set | empty_set)

        # Create a new approach: directly create blocks from LLM output
        # This maintains the grouping from the LLM/BERT model
        blocks = []
        processed_ids = set()

        # First, add all LLM/BERT identified blocks with all their elements
        for block_name, block_data in llm_extracted_data.items():
            block_elements = []
            element_ids_in_block = block_data.get("element_ids", [])

            # Process each element ID in the block
            for eid in element_ids_in_block:
                # Add to processed set
                processed_ids.add(eid)

                # Try to get element from elements_map
                if eid in elements_map:
                    block_elements.append(elements_map[eid])
                else:
                    # Try to find the element in cleaned_lines by element_id
                    found = False
                    for key, value in llm_input_data.items():
                        if isinstance(value, dict) and value.get("element_id") == eid:
                            # Found it! Create element with content
                            elem = {"element_id": eid, "type": "text", "key": key}
                            if "text" in value:
                                elem["content"] = value["text"]
                                elem["type"] = "text"
                            elif "table" in value:
                                elem["content"] = value["table"]
                                elem["type"] = "table"
                            else:
                                elem["content"] = ""
                            block_elements.append(elem)
                            # Also add to elements_map for future reference
                            elements_map[eid] = elem
                            found = True
                            break

                    if not found:
                        # Element truly not found, create minimal entry
                        block_elements.append(
                            {"element_id": eid, "type": "text", "content": ""}
                        )

            # Always add the block even if some elements weren't found in map
            if block_elements:
                blocks.append(
                    {"name": block_name, "type": "processed", "content": block_elements}
                )

        # Then add any unprocessed elements from ordered_ids
        for eid in ordered_ids:
            if eid not in processed_ids:
                if eid in structural_set:
                    block_type = "structural"
                elif eid in empty_set:
                    block_type = "empty"
                elif eid in missing_ids:
                    block_type = "unknown"
                else:
                    continue

                # Get element with content if available
                elem_content = elements_map.get(eid)
                if not elem_content:
                    # Try to find in cleaned_lines
                    for key, value in llm_input_data.items():
                        if isinstance(value, dict) and value.get("element_id") == eid:
                            elem_content = {
                                "element_id": eid,
                                "type": "text",
                                "key": key,
                            }
                            if "text" in value:
                                elem_content["content"] = value["text"]
                            elif "table" in value:
                                elem_content["content"] = value["table"]
                                elem_content["type"] = "table"
                            else:
                                elem_content["content"] = ""
                            break

                if not elem_content:
                    elem_content = {"element_id": eid}

                blocks.append(
                    {"name": "", "type": block_type, "content": [elem_content]}
                )
                processed_ids.add(eid)

        # Final output JSON
        output_json = {
            "name": file_name,
            "blocks": blocks,
            "statistics": {
                "total_elements": len(ordered_ids),
                "processed_blocks": len(
                    [b for b in blocks if b["type"] == "processed"]
                ),
                "structural_elements": len(structural_set),
                "empty_elements": len(empty_set),
                "unknown_elements": len(missing_ids),
                "grouped_elements": len(processed_ids),
            },
        }

        return output_json


class BlockMapperComponent(Component):
    """Block Mapper Component for final block assembly."""

    display_name = "Block Mapper"
    category: str = "processing"
    description = "Map LLM/BERT responses to final structured blocks"
    documentation = ""
    icon = "git-branch"
    name = "BlockMapper"

    inputs = [
        DataInput(
            name="text_data",
            display_name="Text Data",
            info="Extracted text data from TemplateTextExtractor",
            required=True,
        ),
        HandleInput(
            name="llm_response",
            display_name="LLM/BERT Response",
            info="Block assignments from LLM or BERT (accepts Message or Data)",
            required=True,
            input_types=["Message", "Data"],  # Accept both Message and Data
        ),
        DataInput(
            name="document_json",
            display_name="Document JSON (Optional)",
            info="Original document JSON for element mapping",
            required=False,
        ),
        MessageTextInput(
            name="file_name",
            display_name="File Name",
            value="document",
            info="Document file name for output",
        ),
    ]

    outputs = [
        Output(
            display_name="Mapped Blocks",
            name="mapped_blocks",
            method="map_blocks_output",
        ),
        Output(
            display_name="Section Blocks",
            name="section_blocks",
            method="get_section_blocks",
        ),
        Output(display_name="Statistics", name="statistics", method="get_statistics"),
    ]

    def _build_elements_map(self, cleaned_lines: Dict) -> Dict:
        """Build elements map from cleaned lines."""
        elements_map = {}

        for key, value in cleaned_lines.items():
            if isinstance(value, dict) and "element_id" in value:
                elem_id = value["element_id"]
                elements_map[elem_id] = {
                    "element_id": elem_id,
                    "type": "text",  # Default type
                    "key": key,  # Store the original key for reference
                }

                if "text" in value:
                    elements_map[elem_id]["content"] = value["text"]
                    elements_map[elem_id]["type"] = "text"
                elif "table" in value:
                    elements_map[elem_id]["content"] = value["table"]
                    elements_map[elem_id]["type"] = "table"
                elif "content" in value:
                    elements_map[elem_id]["content"] = value["content"]

        return elements_map

    def _extract_elements_map_from_document(self, document_json: Dict) -> Dict:
        """Extract elements map from original document JSON."""
        elements_map = {}

        # Check for letter_type_elements in docx_data
        if "docx_data" in document_json:
            letter_elements = document_json["docx_data"].get("letter_type_elements", {})
        else:
            letter_elements = document_json.get("letter_type_elements", {})

        # Build map from letter_type_elements
        for elem_id, elem_data in letter_elements.items():
            elements_map[elem_id] = {
                "element_id": elem_id,
                "type": elem_data.get("type", "unknown"),
                "json_type": elem_data.get("json_type", "element"),
                "properties": elem_data.get("properties", {}),
                "condition": elem_data.get("condition", ""),
                "content": elem_data.get("content", []),
            }

        return elements_map

    def map_blocks_output(self) -> Data:
        """Map blocks and return the result."""
        try:
            # Handle Data object inputs
            text_data = self.text_data
            if hasattr(text_data, "value"):
                text_data = text_data.value
            elif hasattr(text_data, "data"):
                text_data = text_data.data

            llm_response = self.llm_response

            # Handle different input types for llm_response
            if isinstance(llm_response, Message):
                # Handle Message object from Azure OpenAI
                try:
                    # Check if the message has text content
                    if not llm_response.text:
                        return Data(
                            value={
                                "error": "Azure OpenAI returned empty message",
                                "status": "failed",
                            }
                        )

                    # Clean the response - remove markdown code blocks if present
                    text_to_parse = llm_response.text.strip()

                    # Remove ```json and ``` markers if present
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:]  # Remove ```json
                    elif text_to_parse.startswith("```"):
                        text_to_parse = text_to_parse[3:]  # Remove ```

                    if text_to_parse.endswith("```"):
                        text_to_parse = text_to_parse[:-3]  # Remove trailing ```

                    text_to_parse = text_to_parse.strip()

                    # Log the actual content for debugging
                    self.status = f"Parsing LLM response: {text_to_parse[:100]}..."

                    # Try to parse the JSON
                    llm_response = json.loads(text_to_parse)
                except json.JSONDecodeError as e:
                    # Provide more detailed error with the actual content
                    return Data(
                        value={
                            "error": f"Failed to parse JSON from Message: {str(e)}",
                            "received_text": (
                                llm_response.text[:500]
                                if llm_response.text
                                else "Empty"
                            ),
                            "status": "failed",
                        }
                    )
            elif hasattr(llm_response, "value"):
                llm_response = llm_response.value
            elif hasattr(llm_response, "data"):
                llm_response = llm_response.data
            elif isinstance(llm_response, str):
                # Handle string JSON input
                try:
                    llm_response = json.loads(llm_response)
                except json.JSONDecodeError as e:
                    return Data(
                        value={
                            "error": f"Failed to parse JSON string: {str(e)}",
                            "status": "failed",
                        }
                    )

            # Extract required data
            cleaned_lines = text_data.get("cleaned_lines", {})
            ordered_ids = text_data.get("ordered_ids", [])
            structural_ids = text_data.get("structural_ids", [])
            empty_ids = text_data.get("empty_ids", [])

            # Build or extract elements map
            if hasattr(self, "document_json") and self.document_json:
                document_json = self.document_json
                if hasattr(document_json, "value"):
                    document_json = document_json.value
                elif hasattr(document_json, "data"):
                    document_json = document_json.data
                elements_map = self._extract_elements_map_from_document(document_json)
            else:
                elements_map = self._build_elements_map(cleaned_lines)

            # Store for other outputs
            self.elements_map = elements_map

            # Log for debugging
            self.status = f"Processing {len(llm_response)} blocks from LLM/BERT"

            # Perform mapping
            generator = BlockGenerator()
            result = generator.map_blocks(
                cleaned_lines,
                structural_ids,
                empty_ids,
                ordered_ids,
                llm_response,
                self.file_name,
                elements_map,
            )

            # Store result for other outputs
            self.mapped_result = result

            self.status = f"Mapped {len(result['blocks'])} blocks"

            return Data(value=result)

        except Exception as e:
            self.status = f"Error: {str(e)}"
            return Data(value={"error": str(e), "status": "failed"})

    def get_section_blocks(self) -> Data:
        """Extract section blocks (headers/footers) if available."""
        if not hasattr(self, "mapped_result"):
            return Data(value={"error": "No mapping performed yet"})

        try:
            section_blocks = []

            # Check if document has sections
            if hasattr(self, "document_json") and self.document_json:
                document_json = self.document_json
                if hasattr(document_json, "value"):
                    document_json = document_json.value
                elif hasattr(document_json, "data"):
                    document_json = document_json.data

                sections = []
                if "docx_data" in document_json:
                    sections = document_json["docx_data"].get("sections", [])
                else:
                    sections = document_json.get("sections", [])

                if sections and self.elements_map:
                    generator = BlockGenerator()
                    section_blocks = generator.extract_hf_structural_blocks(
                        sections, self.elements_map
                    )

            return Data(
                value={"section_blocks": section_blocks, "count": len(section_blocks)}
            )

        except Exception as e:
            return Data(value={"error": str(e)})

    def get_statistics(self) -> Data:
        """Get mapping statistics."""
        if not hasattr(self, "mapped_result"):
            return Data(value={"error": "No mapping performed yet"})

        stats = self.mapped_result.get("statistics", {})

        # Add block type breakdown
        block_types = defaultdict(int)
        for block in self.mapped_result.get("blocks", []):
            block_types[block.get("type", "unknown")] += 1

        stats["block_types"] = dict(block_types)

        # Add block name analysis
        named_blocks = [
            b for b in self.mapped_result.get("blocks", []) if b.get("name")
        ]
        stats["named_blocks"] = len(named_blocks)
        stats["unnamed_blocks"] = len(self.mapped_result.get("blocks", [])) - len(
            named_blocks
        )

        return Data(value=stats)
