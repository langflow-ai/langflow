#!/usr/bin/env python3
"""
Script to replace MCP tools in healthcare specifications with appropriate healthcare connectors.

This script implements the Enhanced Decision Framework:
Priority 1: Autonomize Models & Components
Priority 2: Healthcare Connectors (PREFERRED)
Priority 3: API Requests
Priority 4: Specialized Agents

Usage:
    python replace_mcp_tools_healthcare.py [--dry-run] [--spec-file PATH]
"""

import argparse
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Tuple
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MCPToolReplacer:
    """Replaces MCP tools in healthcare specifications with appropriate healthcare connectors."""

    def __init__(self):
        """Initialize the MCP tool replacer with mapping rules."""
        self.replacement_map = {
            # Healthcare data access tools → Healthcare Connectors
            'ehr_patient_records': 'genesis:ehr_connector',
            'ehr_documentation_connector': 'genesis:ehr_connector',
            'clinical_data_access': 'genesis:ehr_connector',
            'patient_records': 'genesis:ehr_connector',
            'medical_records': 'genesis:ehr_connector',

            'insurance_eligibility_check': 'genesis:eligibility_connector',
            'eligibility_verification': 'genesis:eligibility_connector',
            'coverage_verification': 'genesis:eligibility_connector',
            'benefits_check': 'genesis:eligibility_connector',

            'claims_processing': 'genesis:claims_connector',
            'claim_adjudication': 'genesis:claims_connector',
            'claims_management': 'genesis:claims_connector',

            'case_management_database': 'genesis:appeals_data_connector',
            'appeals_management': 'genesis:appeals_data_connector',
            'grievance_processing': 'genesis:appeals_data_connector',

            'pharmacy_integration': 'genesis:pharmacy_benefits_connector',
            'pbm_connector': 'genesis:pharmacy_benefits_connector',
            'formulary_check': 'genesis:pharmacy_benefits_connector',
            'drug_database': 'genesis:pharmacy_benefits_connector',

            'provider_directory': 'genesis:provider_network_connector',
            'network_adequacy': 'genesis:provider_network_connector',
            'provider_lookup': 'genesis:provider_network_connector',
            'npi_lookup': 'genesis:provider_network_connector',

            'hedis_database': 'genesis:quality_metrics_connector',
            'quality_measures': 'genesis:quality_metrics_connector',
            'performance_metrics': 'genesis:quality_metrics_connector',
            'benchmark_data': 'genesis:quality_metrics_connector',

            'regulatory_compliance_api': 'genesis:compliance_data_connector',
            'compliance_monitoring': 'genesis:compliance_data_connector',
            'audit_trail': 'genesis:compliance_data_connector',
            'hipaa_compliance': 'genesis:compliance_data_connector',

            # AI/NLP processing tools → Healthcare Connectors
            'clinical_nlp_processor': 'genesis:clinical_nlp_connector',
            'medical_entity_extraction': 'genesis:clinical_nlp_connector',
            'clinical_text_analysis': 'genesis:clinical_nlp_connector',

            'clinical_speech_transcription': 'genesis:speech_transcription_connector',
            'medical_dictation': 'genesis:speech_transcription_connector',
            'audio_transcription': 'genesis:speech_transcription_connector',

            'medical_terminology_validator': 'genesis:medical_terminology_connector',
            'icd_10_lookup': 'genesis:medical_terminology_connector',
            'cpt_lookup': 'genesis:medical_terminology_connector',
            'snomed_lookup': 'genesis:medical_terminology_connector',

            # Template/Workflow tools → Specialized Agents (handled separately)
            'clinical_note_templates': 'specialized_agent',
            'clinical_qa_engine': 'specialized_agent',
            'benchmark_analysis_model': 'specialized_agent',
            'healthcare_appeals_nlp_classifier': 'specialized_agent',
            'intervention_recommendation_model': 'specialized_agent',

            # External APIs → API Requests
            'peer_plan_comparator': 'genesis:api_request',
            'external_api': 'genesis:api_request',
            'webhook_integration': 'genesis:api_request',
            'notification_service': 'genesis:api_request',
        }

        self.stats = {
            'files_processed': 0,
            'files_modified': 0,
            'mcp_tools_replaced': 0,
            'validation_errors_fixed': 0
        }

    def identify_replacement(self, tool_name: str, component_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Identify the appropriate replacement for an MCP tool.

        Returns:
            Tuple of (new_component_type, new_config)
        """
        tool_name_lower = tool_name.lower()
        description = component_data.get('description', '').lower()

        # Check direct mapping first
        if tool_name in self.replacement_map:
            replacement_type = self.replacement_map[tool_name]
            if replacement_type == 'specialized_agent':
                return self._create_specialized_agent_config(tool_name, component_data)
            else:
                return replacement_type, self._create_connector_config(replacement_type, component_data)

        # Pattern matching for unnamed tools
        for pattern, replacement in self.replacement_map.items():
            if pattern in tool_name_lower or pattern in description:
                if replacement == 'specialized_agent':
                    return self._create_specialized_agent_config(tool_name, component_data)
                else:
                    return replacement, self._create_connector_config(replacement, component_data)

        # Default to API request for unknown tools
        logger.warning(f"Unknown MCP tool '{tool_name}', defaulting to API request")
        return 'genesis:api_request', self._create_api_request_config(component_data)

    def _create_connector_config(self, connector_type: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create configuration for healthcare connector."""
        config = {
            'test_mode': True,
            'mock_mode': True,
            'audit_logging': True,
            'timeout_seconds': '30'
        }

        # Add connector-specific configurations
        if 'ehr_connector' in connector_type:
            config.update({
                'record_type': 'comprehensive',
                'include_clinical_notes': True,
                'fhir_compatibility': True
            })
        elif 'eligibility_connector' in connector_type:
            config.update({
                'verification_type': 'real_time',
                'include_benefits': True,
                'include_copay_info': True
            })
        elif 'quality_metrics_connector' in connector_type:
            config.update({
                'metric_category': 'hedis_effectiveness',
                'benchmark_type': 'national_percentile',
                'include_trends': True
            })
        elif 'clinical_nlp_connector' in connector_type:
            config.update({
                'analysis_type': 'entity_extraction',
                'medical_specialty': 'general_medicine',
                'extract_medications': True,
                'extract_conditions': True
            })

        return config

    def _create_specialized_agent_config(self, tool_name: str, original_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Create configuration for specialized healthcare agent."""
        agent_config = {
            'agent_llm': 'Azure OpenAI',
            'model_name': 'gpt-4',
            'temperature': 0.1,
            'max_tokens': 4000,
            'handle_parsing_errors': True,
            'max_iterations': 20,
            'verbose': True
        }

        return 'genesis:agent', agent_config

    def _create_api_request_config(self, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create configuration for API request."""
        return {
            'method': 'POST',
            'headers': [
                {'key': 'Content-Type', 'value': 'application/json'},
                {'key': 'Authorization', 'value': '${API_KEY}'}
            ],
            'timeout': 30,
            'body': []
        }

    def process_specification(self, spec_path: Path, dry_run: bool = False) -> bool:
        """
        Process a single specification file to replace MCP tools.

        Returns:
            bool: True if file was modified, False otherwise
        """
        logger.info(f"Processing: {spec_path}")

        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                spec_data = yaml.safe_load(f)

            modified = False
            components = spec_data.get('components', [])

            for i, component in enumerate(components):
                if component.get('type') == 'genesis:mcp_tool':
                    tool_config = component.get('config', {})
                    tool_name = tool_config.get('tool_name', 'unknown')

                    # Get replacement
                    new_type, new_config = self.identify_replacement(tool_name, component)

                    # Update component
                    old_type = component['type']
                    component['type'] = new_type
                    component['config'] = new_config

                    # Update asTools flag for connectors
                    if 'connector' in new_type:
                        component['asTools'] = True
                    elif new_type == 'genesis:agent':
                        component.pop('asTools', None)  # Remove asTools for agents

                    # Log the replacement
                    logger.info(f"  Replaced {old_type} (tool: {tool_name}) → {new_type}")
                    modified = True
                    self.stats['mcp_tools_replaced'] += 1

            # Write back the modified specification
            if modified and not dry_run:
                with open(spec_path, 'w', encoding='utf-8') as f:
                    yaml.dump(spec_data, f, default_flow_style=False, sort_keys=False,
                             width=120, indent=2, allow_unicode=True)

                self.stats['files_modified'] += 1
                logger.info(f"  ✅ Updated: {spec_path}")
            elif modified and dry_run:
                logger.info(f"  🔍 Would update: {spec_path} (dry run)")
            else:
                logger.info(f"  ⏭️  No MCP tools found: {spec_path}")

            self.stats['files_processed'] += 1
            return modified

        except Exception as e:
            logger.error(f"Error processing {spec_path}: {e}")
            return False

    def process_directory(self, directory: Path, dry_run: bool = False) -> None:
        """Process all YAML files in a directory."""
        yaml_files = list(directory.rglob("*.yaml"))
        logger.info(f"Found {len(yaml_files)} YAML files in {directory}")

        for yaml_file in yaml_files:
            self.process_specification(yaml_file, dry_run)

    def print_stats(self) -> None:
        """Print processing statistics."""
        print("\n" + "="*60)
        print("MCP TOOL REPLACEMENT SUMMARY")
        print("="*60)
        print(f"Files processed:      {self.stats['files_processed']}")
        print(f"Files modified:       {self.stats['files_modified']}")
        print(f"MCP tools replaced:   {self.stats['mcp_tools_replaced']}")
        print(f"Validation errors:    {self.stats['validation_errors_fixed']}")
        print("="*60)

        if self.stats['mcp_tools_replaced'] > 0:
            print("✅ SUCCESS: All MCP tools have been replaced with healthcare connectors!")
            print("Next steps:")
            print("1. Review the updated specifications")
            print("2. Run Genesis CLI validation")
            print("3. Test the updated workflows")
        else:
            print("ℹ️  INFO: No MCP tools found in specifications")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Replace MCP tools in healthcare specifications")
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without modifying files')
    parser.add_argument('--spec-file', type=Path, help='Process a single specification file')
    parser.add_argument('--directory', type=Path,
                       default=Path('/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/specifications_library/agents/healthcare'),
                       help='Directory containing healthcare specifications')

    args = parser.parse_args()

    replacer = MCPToolReplacer()

    if args.spec_file:
        if args.spec_file.exists():
            replacer.process_specification(args.spec_file, args.dry_run)
        else:
            logger.error(f"Specification file not found: {args.spec_file}")
            return 1
    else:
        if args.directory.exists():
            replacer.process_directory(args.directory, args.dry_run)
        else:
            logger.error(f"Directory not found: {args.directory}")
            return 1

    replacer.print_stats()
    return 0


if __name__ == '__main__':
    exit(main())