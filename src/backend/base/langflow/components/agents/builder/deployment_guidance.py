"""Deployment Guidance Component

Provides deployment instructions and guidance for validated agent specifications.
Helps users understand next steps and deployment requirements.
"""

import json
from typing import Any, Dict, List, Optional

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Data, Text
from langflow.inputs.inputs import MessageTextInput, DictInput, DropdownInput, BoolInput
from langflow.schema.data import Data as DataType
from langflow.template.field.base import Output


class DeploymentGuidanceComponent(Component):
    display_name = "Deployment Guidance"
    description = "Provides deployment instructions and guidance for validated agent specifications"
    documentation = "Helps users understand next steps and deployment requirements"
    icon = "rocket"
    name = "DeploymentGuidance"

    inputs = [
        MessageTextInput(
            name="yaml_specification",
            display_name="YAML Specification",
            info="Validated YAML specification ready for deployment",
            required=True,
        ),
        DictInput(
            name="validation_results",
            display_name="Validation Results",
            info="Results from SpecificationValidatorComponent",
            required=False,
        ),
        DictInput(
            name="test_results",
            display_name="Test Results",
            info="Results from TestExecutorComponent",
            required=False,
        ),
        DropdownInput(
            name="deployment_target",
            display_name="Deployment Target",
            options=["development", "staging", "production", "kubernetes"],
            value="development",
            info="Target environment for deployment",
        ),
        BoolInput(
            name="include_monitoring",
            display_name="Include Monitoring Setup",
            value=True,
            info="Whether to include monitoring and observability guidance",
        ),
    ]

    outputs = [
        Output(display_name="Deployment Instructions", name="instructions", method="generate_deployment_instructions"),
        Output(display_name="Environment Setup", name="environment", method="create_environment_setup"),
        Output(display_name="Configuration Guide", name="configuration", method="generate_configuration_guide"),
        Output(display_name="Monitoring Setup", name="monitoring", method="create_monitoring_setup"),
        Output(display_name="Next Steps", name="next_steps", method="suggest_next_steps"),
    ]

    def generate_deployment_instructions(self) -> DataType:
        """Generate step-by-step deployment instructions"""
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            instructions = self._create_deployment_instructions(spec_dict)
            
            return DataType(value={
                "deployment_target": self.deployment_target,
                "step_by_step_guide": instructions["steps"],
                "prerequisites": instructions["prerequisites"],
                "deployment_checklist": instructions["checklist"],
                "estimated_time": instructions["estimated_time"],
                "complexity_level": instructions["complexity"],
            })
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to generate deployment instructions: {str(e)}"
            })

    def create_environment_setup(self) -> DataType:
        """Create environment setup guidance"""
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            environment_setup = self._generate_environment_setup(spec_dict)
            
            return DataType(value={
                "environment_variables": environment_setup["env_vars"],
                "dependencies": environment_setup["dependencies"],
                "infrastructure_requirements": environment_setup["infrastructure"],
                "security_configuration": environment_setup["security"],
                "networking_requirements": environment_setup["networking"],
            })
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to create environment setup: {str(e)}"
            })

    def generate_configuration_guide(self) -> DataType:
        """Generate configuration guide for deployment"""
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            config_guide = self._create_configuration_guide(spec_dict)
            
            return DataType(value={
                "configuration_files": config_guide["files"],
                "required_settings": config_guide["required"],
                "optional_settings": config_guide["optional"],
                "environment_specific": config_guide["environment_specific"],
                "validation_commands": config_guide["validation"],
            })
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to generate configuration guide: {str(e)}"
            })

    def create_monitoring_setup(self) -> DataType:
        """Create monitoring and observability setup"""
        
        if not self.include_monitoring:
            return DataType(value={"message": "Monitoring setup disabled"})
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            monitoring_setup = self._generate_monitoring_setup(spec_dict)
            
            return DataType(value={
                "metrics_configuration": monitoring_setup["metrics"],
                "logging_setup": monitoring_setup["logging"],
                "alerting_rules": monitoring_setup["alerting"],
                "dashboard_configuration": monitoring_setup["dashboards"],
                "health_checks": monitoring_setup["health_checks"],
            })
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to create monitoring setup: {str(e)}"
            })

    def suggest_next_steps(self) -> DataType:
        """Suggest next steps based on deployment status"""
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            next_steps = self._determine_next_steps(spec_dict)
            
            return DataType(value={
                "immediate_actions": next_steps["immediate"],
                "short_term_goals": next_steps["short_term"],
                "long_term_objectives": next_steps["long_term"],
                "optimization_opportunities": next_steps["optimizations"],
                "maintenance_schedule": next_steps["maintenance"],
            })
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to suggest next steps: {str(e)}"
            })

    def _create_deployment_instructions(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Create detailed deployment instructions"""
        
        agent_name = spec_dict.get("name", "Agent")
        components = spec_dict.get("components", [])
        
        steps = []
        prerequisites = []
        checklist = []
        
        # Prerequisites
        prerequisites.extend([
            "AI Studio platform access",
            "Required environment variables configured",
            "Network connectivity to external services",
            "Appropriate permissions for deployment"
        ])
        
        # Add healthcare-specific prerequisites
        if self._is_healthcare_agent(spec_dict):
            prerequisites.extend([
                "HIPAA compliance verification",
                "Healthcare data access permissions",
                "Audit logging infrastructure"
            ])
        
        # Deployment steps based on target
        if self.deployment_target == "development":
            steps.extend(self._generate_development_steps(spec_dict))
        elif self.deployment_target == "staging":
            steps.extend(self._generate_staging_steps(spec_dict))
        elif self.deployment_target == "production":
            steps.extend(self._generate_production_steps(spec_dict))
        else:  # kubernetes
            steps.extend(self._generate_kubernetes_steps(spec_dict))
        
        # Deployment checklist
        checklist.extend([
            "Specification validated successfully",
            "Test execution completed with >80% success rate",
            "Environment variables configured",
            "Dependencies installed",
            "Network connectivity verified",
            "Monitoring configured",
            "Security settings applied",
            "Backup and rollback plan ready"
        ])
        
        # Estimate deployment time
        complexity = self._assess_deployment_complexity(components)
        time_estimates = {
            "simple": "15-30 minutes",
            "moderate": "30-60 minutes", 
            "complex": "1-2 hours",
            "enterprise": "2-4 hours"
        }
        
        return {
            "steps": steps,
            "prerequisites": prerequisites,
            "checklist": checklist,
            "estimated_time": time_estimates.get(complexity, "1 hour"),
            "complexity": complexity
        }

    def _generate_development_steps(self, spec_dict: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate development environment deployment steps"""
        
        return [
            {
                "step": "1",
                "title": "Prepare Development Environment",
                "description": "Set up local development environment with required dependencies",
                "commands": ["pip install ai-studio-dev", "ai-studio init"]
            },
            {
                "step": "2",
                "title": "Configure Environment Variables",
                "description": "Set up environment variables for development",
                "commands": ["export OPENAI_API_KEY=your_key", "export AI_STUDIO_ENV=development"]
            },
            {
                "step": "3",
                "title": "Deploy Agent Specification",
                "description": "Deploy the agent to development environment",
                "commands": [f"ai-studio deploy {spec_dict.get('name', 'agent')}.yaml --env=development"]
            },
            {
                "step": "4",
                "title": "Verify Deployment",
                "description": "Test the deployed agent with sample requests",
                "commands": ["ai-studio test --agent-id={agent_id} --sample-input"]
            }
        ]

    def _generate_staging_steps(self, spec_dict: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate staging environment deployment steps"""
        
        return [
            {
                "step": "1",
                "title": "Prepare Staging Environment",
                "description": "Ensure staging environment is ready and accessible",
                "commands": ["ai-studio connect --env=staging", "ai-studio health-check"]
            },
            {
                "step": "2",
                "title": "Deploy to Staging",
                "description": "Deploy agent specification to staging environment",
                "commands": [f"ai-studio deploy {spec_dict.get('name', 'agent')}.yaml --env=staging"]
            },
            {
                "step": "3",
                "title": "Run Integration Tests",
                "description": "Execute comprehensive integration tests",
                "commands": ["ai-studio test --integration --env=staging"]
            },
            {
                "step": "4",
                "title": "Performance Validation",
                "description": "Validate performance under staging load",
                "commands": ["ai-studio load-test --duration=10m"]
            }
        ]

    def _generate_production_steps(self, spec_dict: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate production environment deployment steps"""
        
        return [
            {
                "step": "1",
                "title": "Pre-Deployment Checklist",
                "description": "Complete all pre-deployment verification steps",
                "commands": ["ai-studio pre-deploy-check --env=production"]
            },
            {
                "step": "2",
                "title": "Backup Current State",
                "description": "Create backup of current production state",
                "commands": ["ai-studio backup --env=production"]
            },
            {
                "step": "3",
                "title": "Deploy with Blue-Green",
                "description": "Deploy using blue-green deployment strategy",
                "commands": [f"ai-studio deploy {spec_dict.get('name', 'agent')}.yaml --env=production --strategy=blue-green"]
            },
            {
                "step": "4",
                "title": "Validate Production Deployment",
                "description": "Run production validation tests",
                "commands": ["ai-studio validate --env=production"]
            },
            {
                "step": "5",
                "title": "Switch Traffic",
                "description": "Switch traffic to new deployment after validation",
                "commands": ["ai-studio traffic-switch --to=green"]
            },
            {
                "step": "6",
                "title": "Monitor Deployment",
                "description": "Monitor deployment health and metrics",
                "commands": ["ai-studio monitor --duration=1h"]
            }
        ]

    def _generate_kubernetes_steps(self, spec_dict: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate Kubernetes deployment steps"""
        
        return [
            {
                "step": "1",
                "title": "Prepare Kubernetes Manifests",
                "description": "Generate Kubernetes deployment manifests",
                "commands": [f"ai-studio k8s-generate {spec_dict.get('name', 'agent')}.yaml"]
            },
            {
                "step": "2",
                "title": "Create Namespace",
                "description": "Create dedicated namespace for the agent",
                "commands": [f"kubectl create namespace {spec_dict.get('name', 'agent').lower()}"]
            },
            {
                "step": "3",
                "title": "Apply Secrets and ConfigMaps",
                "description": "Deploy configuration and secrets",
                "commands": ["kubectl apply -f secrets.yaml", "kubectl apply -f configmap.yaml"]
            },
            {
                "step": "4",
                "title": "Deploy Application",
                "description": "Deploy the agent application to Kubernetes",
                "commands": ["kubectl apply -f deployment.yaml", "kubectl apply -f service.yaml"]
            },
            {
                "step": "5",
                "title": "Verify Deployment",
                "description": "Check deployment status and pod health",
                "commands": ["kubectl get pods", "kubectl logs -l app={agent_name}"]
            }
        ]

    def _generate_environment_setup(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Generate environment setup requirements"""
        
        components = spec_dict.get("components", [])
        
        # Environment variables
        env_vars = [
            "OPENAI_API_KEY=your_openai_api_key",
            "AI_STUDIO_ENV=" + self.deployment_target,
            "LOG_LEVEL=INFO"
        ]
        
        # Add component-specific environment variables
        tool_components = [c for c in components if "tool" in c.get("type", "") or "mcp" in c.get("type", "")]
        for tool in tool_components:
            tool_name = tool.get("config", {}).get("tool_name", "")
            if "ehr" in tool_name.lower():
                env_vars.extend(["EHR_API_KEY=your_ehr_key", "EHR_BASE_URL=https://ehr.example.com"])
            elif "insurance" in tool_name.lower():
                env_vars.extend(["INSURANCE_API_KEY=your_insurance_key"])
            elif "email" in tool_name.lower():
                env_vars.extend(["EMAIL_API_KEY=your_email_key"])
        
        # Healthcare-specific variables
        if self._is_healthcare_agent(spec_dict):
            env_vars.extend([
                "HIPAA_LOGGING=true",
                "PHI_ENCRYPTION=true",
                "AUDIT_RETENTION_DAYS=7"
            ])
        
        # Dependencies
        dependencies = [
            "ai-studio-runtime>=1.0.0",
            "langflow>=1.0.0",
            "pydantic>=2.0.0",
            "uvicorn>=0.24.0"
        ]
        
        # Infrastructure requirements
        infrastructure = self._determine_infrastructure_requirements(components)
        
        # Security configuration
        security = {
            "authentication": "API key based authentication required",
            "encryption": "TLS 1.3 for data in transit",
            "data_protection": "Encryption at rest for sensitive data",
            "access_control": "Role-based access control (RBAC)"
        }
        
        if self._is_healthcare_agent(spec_dict):
            security.update({
                "hipaa_compliance": "HIPAA audit logging enabled",
                "phi_handling": "PHI data encryption and access controls"
            })
        
        # Networking requirements
        networking = {
            "ingress": "HTTPS ingress with valid SSL certificate",
            "egress": "Outbound connectivity to external APIs",
            "ports": ["8000 (HTTP)", "8443 (HTTPS)"],
            "firewall": "Allow traffic on required ports"
        }
        
        return {
            "env_vars": env_vars,
            "dependencies": dependencies,
            "infrastructure": infrastructure,
            "security": security,
            "networking": networking
        }

    def _create_configuration_guide(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Create configuration guide"""
        
        agent_name = spec_dict.get("name", "agent").lower().replace(" ", "-")
        
        configuration_files = {
            f"{agent_name}-config.yaml": "Main agent configuration file",
            "secrets.yaml": "Kubernetes secrets for API keys",
            "configmap.yaml": "Configuration map for environment settings",
            "deployment.yaml": "Kubernetes deployment manifest"
        }
        
        required_settings = [
            "LLM provider configuration (OpenAI/Azure)",
            "Model selection and parameters",
            "Timeout and retry settings",
            "Authentication credentials",
            "Resource limits and requests"
        ]
        
        optional_settings = [
            "Custom prompt templates",
            "Advanced logging configuration",
            "Performance tuning parameters",
            "Custom error handling",
            "Integration-specific settings"
        ]
        
        environment_specific = {
            "development": ["Debug logging enabled", "Relaxed timeouts", "Mock external services"],
            "staging": ["Comprehensive logging", "Production-like settings", "Integration testing enabled"],
            "production": ["Optimized performance settings", "Security hardening", "Monitoring enabled"]
        }
        
        validation_commands = [
            "ai-studio config validate",
            "ai-studio connectivity-test",
            "ai-studio health-check"
        ]
        
        return {
            "files": configuration_files,
            "required": required_settings,
            "optional": optional_settings,
            "environment_specific": environment_specific,
            "validation": validation_commands
        }

    def _generate_monitoring_setup(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Generate monitoring and observability setup"""
        
        agent_name = spec_dict.get("name", "agent").lower().replace(" ", "-")
        
        # Metrics configuration
        metrics = {
            "prometheus_metrics": [
                "agent_requests_total",
                "agent_request_duration_seconds",
                "agent_errors_total",
                "agent_active_sessions"
            ],
            "business_metrics": [
                "successful_processing_rate",
                "average_response_time",
                "user_satisfaction_score"
            ],
            "resource_metrics": [
                "cpu_utilization",
                "memory_usage",
                "disk_io",
                "network_throughput"
            ]
        }
        
        # Add healthcare-specific metrics
        if self._is_healthcare_agent(spec_dict):
            metrics["compliance_metrics"] = [
                "hipaa_audit_events",
                "phi_access_count",
                "security_violations"
            ]
        
        # Logging setup
        logging = {
            "log_level": "INFO" if self.deployment_target == "production" else "DEBUG",
            "log_format": "JSON structured logging",
            "log_destinations": ["stdout", "file", "centralized_logging"],
            "retention_policy": "30 days for application logs, 7 years for audit logs"
        }
        
        # Alerting rules
        alerting = [
            {
                "alert": "AgentHighErrorRate",
                "condition": "error_rate > 5%",
                "severity": "warning",
                "description": "Agent error rate is above 5%"
            },
            {
                "alert": "AgentHighLatency", 
                "condition": "p95_latency > 10s",
                "severity": "warning",
                "description": "Agent response time p95 is above 10 seconds"
            },
            {
                "alert": "AgentDown",
                "condition": "up == 0",
                "severity": "critical",
                "description": "Agent is not responding"
            }
        ]
        
        # Healthcare-specific alerts
        if self._is_healthcare_agent(spec_dict):
            alerting.extend([
                {
                    "alert": "HIPAAViolation",
                    "condition": "hipaa_violations > 0",
                    "severity": "critical",
                    "description": "HIPAA compliance violation detected"
                }
            ])
        
        # Dashboard configuration
        dashboards = {
            "operational_dashboard": {
                "description": "Real-time operational metrics",
                "panels": ["Request Rate", "Response Time", "Error Rate", "Active Sessions"]
            },
            "business_dashboard": {
                "description": "Business metrics and KPIs",
                "panels": ["Success Rate", "User Satisfaction", "Processing Volume"]
            },
            "infrastructure_dashboard": {
                "description": "Infrastructure and resource metrics",
                "panels": ["CPU Usage", "Memory Usage", "Disk I/O", "Network"]
            }
        }
        
        # Health checks
        health_checks = {
            "liveness_probe": {
                "path": "/health",
                "interval": "30s",
                "timeout": "5s"
            },
            "readiness_probe": {
                "path": "/ready",
                "interval": "10s",
                "timeout": "3s"
            },
            "startup_probe": {
                "path": "/startup",
                "interval": "10s",
                "timeout": "5s",
                "failure_threshold": 30
            }
        }
        
        return {
            "metrics": metrics,
            "logging": logging,
            "alerting": alerting,
            "dashboards": dashboards,
            "health_checks": health_checks
        }

    def _determine_next_steps(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Determine next steps based on deployment status"""
        
        immediate_actions = []
        short_term_goals = []
        long_term_objectives = []
        optimizations = []
        maintenance = []
        
        # Immediate actions based on deployment target
        if self.deployment_target == "development":
            immediate_actions.extend([
                "Test agent with sample data",
                "Verify all integrations work correctly",
                "Review logs for any warnings or errors"
            ])
        elif self.deployment_target == "staging":
            immediate_actions.extend([
                "Run comprehensive integration tests",
                "Validate performance under load",
                "Prepare for production deployment"
            ])
        elif self.deployment_target == "production":
            immediate_actions.extend([
                "Monitor deployment health closely",
                "Validate all metrics are being collected",
                "Ensure alerting is working correctly"
            ])
        
        # Short-term goals (1-2 weeks)
        short_term_goals.extend([
            "Optimize agent performance based on metrics",
            "Implement additional monitoring if needed",
            "Gather user feedback and iterate",
            "Document operational procedures"
        ])
        
        # Long-term objectives (1-3 months)
        long_term_objectives.extend([
            "Implement advanced features based on usage patterns",
            "Scale horizontally if needed",
            "Integrate with additional systems",
            "Develop automated testing and deployment pipelines"
        ])
        
        # Healthcare-specific objectives
        if self._is_healthcare_agent(spec_dict):
            long_term_objectives.extend([
                "Complete formal HIPAA compliance audit",
                "Implement advanced security features",
                "Integrate with additional healthcare systems"
            ])
        
        # Optimization opportunities
        optimizations.extend([
            "Fine-tune LLM parameters for better performance",
            "Implement caching for frequently accessed data",
            "Optimize database queries and external API calls",
            "Consider implementing batching for high-volume operations"
        ])
        
        # Maintenance schedule
        maintenance.extend([
            "Weekly: Review performance metrics and logs",
            "Monthly: Update dependencies and security patches",
            "Quarterly: Review and update configuration",
            "Annually: Comprehensive security and compliance review"
        ])
        
        return {
            "immediate": immediate_actions,
            "short_term": short_term_goals,
            "long_term": long_term_objectives,
            "optimizations": optimizations,
            "maintenance": maintenance
        }

    def _is_healthcare_agent(self, spec_dict: Dict[str, Any]) -> bool:
        """Check if this is a healthcare agent"""
        
        return (spec_dict.get("subDomain") == "healthcare" or
                "healthcare" in str(spec_dict.get("tags", [])).lower() or
                spec_dict.get("securityInfo", {}).get("hipaaCompliant", False))

    def _assess_deployment_complexity(self, components: List[Dict[str, Any]]) -> str:
        """Assess deployment complexity based on components"""
        
        total_components = len(components)
        integration_components = len([c for c in components if "tool" in c.get("type", "") or "mcp" in c.get("type", "")])
        agent_components = len([c for c in components if "agent" in c.get("type", "")])
        
        if total_components > 15 or integration_components > 5:
            return "enterprise"
        elif total_components > 10 or agent_components > 2:
            return "complex"
        elif total_components > 6 or integration_components > 2:
            return "moderate"
        else:
            return "simple"

    def _determine_infrastructure_requirements(self, components: List[Dict[str, Any]]) -> Dict[str, str]:
        """Determine infrastructure requirements"""
        
        complexity = self._assess_deployment_complexity(components)
        
        requirements = {
            "simple": {
                "cpu": "0.5 cores",
                "memory": "1GB",
                "storage": "10GB",
                "network": "Standard bandwidth"
            },
            "moderate": {
                "cpu": "1 core",
                "memory": "2GB",
                "storage": "20GB",
                "network": "Enhanced bandwidth"
            },
            "complex": {
                "cpu": "2 cores",
                "memory": "4GB",
                "storage": "50GB",
                "network": "High bandwidth"
            },
            "enterprise": {
                "cpu": "4 cores",
                "memory": "8GB",
                "storage": "100GB",
                "network": "Premium bandwidth"
            }
        }
        
        return requirements.get(complexity, requirements["simple"])