import asyncio
import re

from langflow.custom import Component
from langflow.inputs.inputs import DefaultPromptField
from langflow.io import DropdownInput, MultilineInput, Output
from langflow.schema.message import Message
from loguru import logger

from langflow.services.deps import get_prompt_service


class GenesisPromptComponent(Component):
    display_name: str = "Genesis Prompt Template"
    description: str = "Use published prompts, edit your drafts, or create new prompt templates from the Prompt Library."
    documentation: str = "https://docs.langflow.org/components-prompts"
    icon = "Autonomize"
    trace_type = "genesis_prompt"
    name = "Genesis Prompt Template"
    priority = 1

    inputs = [
        DropdownInput(
            name="saved_prompt",
            display_name="Prompt",
            info="Select a published prompt or one of your drafts. Click refresh to update the list.",
            refresh_button=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="prompt_version",
            display_name="Version",
            info="Select a version. Draft versions can be edited, published versions are read-only.",
            refresh_button=True,
            real_time_refresh=True,
            advanced=True,  # Hidden until a prompt is selected
        ),
        DropdownInput(
            name="message_type",
            display_name="Role",
            info="Select the message role (system or user).",
            options=["system", "user"],
            value="system",
            real_time_refresh=True,
            advanced=True,  # Hidden initially
        ),
        MultilineInput(
            name="template",
            display_name="Content",
            info="Edit the prompt content. Use {{variable}} syntax to define input variables.",
            value="",
            advanced=True,  # Hidden until a prompt template is selected
            real_time_refresh=True,  # Trigger update_build_config to re-process variables
        ),
    ]

    outputs = [
        Output(
            display_name="Prompt Message",
            name="prompt_message",
            method="build_prompt_message",
        ),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self._selected_prompt_id = None
        self._selected_version_data = None
        self._available_versions = []  # Cache versions for the selected prompt
        self._current_variables = []
        self._prompt_metadata = {}  # Map prompt_id -> {name, prompt_id}

    # -----------------------------------------------------
    # Fetch message content based on selected role
    # -----------------------------------------------------
    def _get_message_by_role(self, role: str) -> str:
        version = self._selected_version_data
        if not version:
            return ""

        chain = version.get("message_chain", []) or []

        # First try to find the requested role
        for msg in chain:
            if msg.get("role") == role:
                return msg.get("content", "") or ""

        # If not found and we requested "system", try "user" as fallback
        if role == "system":
            for msg in chain:
                if msg.get("role") == "user":
                    return msg.get("content", "") or ""
        
        # If still not found, return the first message content if any
        if chain:
            return chain[0].get("content", "") or ""

        return ""

    # -----------------------------------------------------
    # Get available roles from message chain
    # -----------------------------------------------------
    def _get_available_roles(self, version: dict | None = None) -> list[str]:
        """Get list of available roles from the version's message chain."""
        ver = version or self._selected_version_data
        if not ver:
            return ["system", "user"]  # Default options
        
        chain = ver.get("message_chain", []) or []
        roles = []
        for msg in chain:
            role = msg.get("role")
            if role and role not in roles:
                roles.append(role)
        
        # Return found roles or default if none found
        return roles if roles else ["system", "user"]

    # -----------------------------------------------------
    # Format version option with status label
    # -----------------------------------------------------
    def _format_version_option(self, version: dict) -> str:
        """Format version for dropdown display with status label."""
        ver_num = version.get("version", 1)
        status = version.get("status", "").upper()
        is_latest = version.get("is_latest", False)
        
        # Build label with version number and status
        label = f"v{ver_num}"
        
        # Add status suffix
        if status == "DRAFT":
            label += " - DRAFT"
        elif status == "PENDING_APPROVAL":
            label += " - PENDING"
        elif status == "PUBLISHED":
            label += " - PUBLISHED"
        elif status == "REJECTED":
            label += " - REJECTED"
        
        # Add latest indicator
        if is_latest:
            label += " (Latest)"
        
        return label

    # -----------------------------------------------------
    # Build version metadata for dropdown
    # -----------------------------------------------------
    def _build_version_metadata(self, version: dict) -> dict:
        """Build metadata for version dropdown option."""
        status = version.get("status", "").upper()
        return {
            "status": status,
            "disabled": status == "REJECTED",  # Disable REJECTED versions
        }

    # -----------------------------------------------------
    # Parse version from formatted option
    # -----------------------------------------------------
    def _parse_version_from_option(self, option: str) -> int | None:
        """Extract version number from formatted option string."""
        if not option:
            return None
        # Extract version number from "v1 (Latest) [Draft]" format
        match = re.match(r"v(\d+)", option)
        return int(match.group(1)) if match else None

    # -----------------------------------------------------
    # Replace {{variables}} in template
    # -----------------------------------------------------
    def _replace_variables(self, content: str) -> str:
        if not content:
            return content

        variables = re.findall(r"\{\{(\w+)\}\}", content)

        for var in variables:
            value = getattr(self, var, "")  # Do NOT use .get()
            content = content.replace(f"{{{{{var}}}}}", str(value))

        return content

    # -----------------------------------------------------
    # Build Message Output
    # -----------------------------------------------------
    async def build_prompt_message(self) -> Message:
        template = getattr(self, "template", "") or ""

        if not template:
            self.status = "No template selected"
            return Message(text="")

        try:
            final = self._replace_variables(template)
            self.status = final
            return Message(text=final)
        except Exception as e:
            logger.exception(f"build_prompt_message failed: {e}")
            self.status = "error"
            return Message(text="")

    # -----------------------------------------------------
    # Handle dynamic {{variable}} fields
    # -----------------------------------------------------
    def _process_template_variables(self, template_content: str, build_config: dict):
        vars_found = sorted(list(set(re.findall(r"\{\{(\w+)\}\}", template_content))))

        # First, remove all old variable fields that are not in the new template
        reserved_fields = [
            "message_type", "saved_prompt", "prompt_version", "template",
            "code", "_token", "_type"
        ]
        keys_to_remove = []
        for key in list(build_config.keys()):
            if key.startswith("_"):
                continue  # Skip internal fields
            if key in reserved_fields:
                continue
            if key in vars_found:
                continue
            # Check if this is a variable field (prompt-field type or has display_name matching key)
            if isinstance(build_config.get(key), dict):
                field_type = build_config[key].get("type", "")
                if field_type == "prompt-field" or field_type == "str":
                    keys_to_remove.append(key)
        
        for key in keys_to_remove:
            build_config.pop(key, None)
            logger.info(f"Removed old variable field: {key}")

        # Now add new variable fields
        for var in vars_found:
            field = DefaultPromptField(name=var, display_name=var)
            field_dict = field.to_dict()
            # Ensure the field is visible
            field_dict["show"] = True
            field_dict["advanced"] = False
            build_config[var] = field_dict
            logger.info(f"Added variable field: {var}")

        return vars_found

    # -----------------------------------------------------
    # Load template content from selected version
    # -----------------------------------------------------
    def _load_version_content(self, build_config: dict):
        """Load template content from the selected version."""
        if not self._selected_version_data:
            logger.warning("No selected version data, clearing template")
            build_config["template"]["value"] = ""
            return

        msg_type = getattr(self, "message_type", "system")
        logger.info(f"Loading content for message_type: {msg_type}")
        
        # Log the message chain for debugging
        message_chain = self._selected_version_data.get("message_chain", [])
        logger.info(f"Message chain: {message_chain}")
        
        content = self._get_message_by_role(msg_type)
        logger.info(f"Content for role '{msg_type}': {content[:100] if content else 'EMPTY'}")
        
        build_config["template"]["value"] = content

        if content:
            self._current_variables = self._process_template_variables(content, build_config)

    # -----------------------------------------------------
    # UI Update Handler (Core Sync Logic)
    # -----------------------------------------------------
    async def update_build_config(self, build_config, field_value, field_name=None):
        logger.info(f"update_build_config: {field_name} → {field_value}")

        # -----------------------------
        # Refresh templates (saved_prompt)
        # -----------------------------
        if field_name == "saved_prompt":
            try:
                ps = get_prompt_service()
                if not ps.ready:
                    build_config["saved_prompt"]["options"] = []
                    return build_config

                # Get token from build_config if available (passed from API layer)
                token = build_config.get("_token")

                # Fetch all prompts in parallel for better performance
                published_response, draft_response, pending_response = await asyncio.gather(
                    ps.get_published_prompts(token=token),
                    ps.get_draft_prompts(token=token),
                    ps.get_pending_prompts(token=token),
                    return_exceptions=True,
                )

                # Process published prompts
                published_versions = []
                if not isinstance(published_response, Exception):
                    published_versions = published_response.get("data", {}).get("versions", []) or []
                    logger.info(f"Published prompts count: {len(published_versions)}")
                else:
                    logger.warning(f"Could not fetch published prompts: {published_response}")

                # Process draft prompts
                draft_prompts = []
                if not isinstance(draft_response, Exception) and not draft_response.get("error"):
                    draft_prompts = draft_response.get("data", {}).get("prompts", []) or []
                    logger.info(f"User's draft prompts count: {len(draft_prompts)}")
                elif isinstance(draft_response, Exception):
                    logger.warning(f"Could not fetch draft prompts: {draft_response}")

                # Process pending prompts
                pending_prompts = []
                if not isinstance(pending_response, Exception) and not pending_response.get("error"):
                    pending_prompts = pending_response.get("data", {}).get("prompts", []) or []
                    logger.info(f"User's pending approval prompts count: {len(pending_prompts)}")
                elif isinstance(pending_response, Exception):
                    logger.warning(f"Could not fetch pending prompts: {pending_response}")

                # Build prompt metadata map and options list
                # Use prompt_id as the display key for consistency
                self._prompt_metadata = {}
                prompt_options = []
                seen_prompt_ids = set()
                
                # Process published versions - use prompt_id as display name
                for v in published_versions:
                    prompt_id = v.get("prompt_id", "")
                    if prompt_id and prompt_id not in seen_prompt_ids:
                        seen_prompt_ids.add(prompt_id)
                        # Use prompt_id as the display name for consistency
                        display_name = prompt_id
                        
                        self._prompt_metadata[display_name] = {
                            "prompt_id": prompt_id,
                            "prompt_name": v.get("prompt_name", "") or v.get("name", "") or prompt_id,
                            "versions": [],
                            "is_draft": False,
                        }
                        prompt_options.append(display_name)
                    
                    # Add version to metadata
                    if prompt_id and prompt_id in seen_prompt_ids:
                        # Find the display_name key for this prompt_id
                        display_name = prompt_id
                        if display_name in self._prompt_metadata:
                            self._prompt_metadata[display_name]["versions"].append(v)
                
                # Process user's draft prompts (from /prompts/versions response)
                for dp in draft_prompts:
                    prompt_id = dp.get("prompt_id", "")
                    if prompt_id and prompt_id not in seen_prompt_ids:
                        seen_prompt_ids.add(prompt_id)
                        # Use prompt_id as display name (same as published)
                        display_name = prompt_id
                        
                        # Convert to version format
                        draft_version = {
                            "version": dp.get("version", 1),
                            "status": dp.get("version_status", "DRAFT"),
                            "message_chain": dp.get("message_chain", []),
                            "prompt_id": prompt_id,
                        }
                        
                        self._prompt_metadata[display_name] = {
                            "prompt_id": prompt_id,
                            "prompt_name": dp.get("name", "") or prompt_id,
                            "versions": [draft_version],
                            "is_draft": True,
                        }
                        prompt_options.append(display_name)

                # Process user's pending approval prompts (from /prompts/versions response)
                for pp in pending_prompts:
                    prompt_id = pp.get("prompt_id", "")
                    if prompt_id and prompt_id not in seen_prompt_ids:
                        seen_prompt_ids.add(prompt_id)
                        display_name = prompt_id
                        
                        # Convert to version format
                        pending_version = {
                            "version": pp.get("version", 1),
                            "status": pp.get("version_status", "PENDING_APPROVAL"),
                            "message_chain": pp.get("message_chain", []),
                            "prompt_id": prompt_id,
                        }
                        
                        self._prompt_metadata[display_name] = {
                            "prompt_id": prompt_id,
                            "prompt_name": pp.get("name", "") or prompt_id,
                            "versions": [pending_version],
                            "is_pending": True,
                        }
                        prompt_options.append(display_name)
                
                # Sort options
                prompt_options.sort()
                
                # Just set options, no metadata needed (only show name)
                build_config["saved_prompt"]["options"] = prompt_options
                logger.info(f"Prompt options (published + drafts + pending): {prompt_options}")

                if field_value:
                    # Set loading state on dependent fields while fetching
                    build_config["prompt_version"]["is_loading"] = True
                    build_config["template"]["is_loading"] = True
                    
                    # field_value is now the prompt_id directly
                    # Get the actual prompt_id from metadata
                    if field_value in self._prompt_metadata:
                        metadata = self._prompt_metadata[field_value]
                        actual_prompt_id = metadata.get("prompt_id", field_value)
                        cached_versions = metadata.get("versions", [])
                        if cached_versions:
                            self._available_versions = cached_versions
                            logger.info(f"Using {len(cached_versions)} cached versions for {field_value}")
                    else:
                        # Fallback: use field_value directly as prompt_id
                        actual_prompt_id = field_value
                    
                    self._selected_prompt_id = actual_prompt_id
                    logger.info(f"Selected prompt: {field_value} -> ID: {actual_prompt_id}")
                    
                    # Optionally try to fetch additional versions (may include drafts for the user)
                    try:
                        versions_response = await ps.get_prompt_versions(actual_prompt_id, token=token)
                        logger.info(f"Versions API response for {actual_prompt_id}: {versions_response}")
                        
                        # Check if we got an error (authentication required)
                        if versions_response.get("error"):
                            logger.warning(f"Versions API error: {versions_response.get('error')}")
                        else:
                            # Handle different response structures
                            versions_data = versions_response.get("data", {})
                            if isinstance(versions_data, dict):
                                fetched_versions = versions_data.get("versions", []) or []
                            elif isinstance(versions_data, list):
                                fetched_versions = versions_data
                            else:
                                fetched_versions = []
                            
                            # If we got versions from API, use those (they may include drafts)
                            if fetched_versions:
                                self._available_versions = fetched_versions
                                logger.info(f"Using {len(fetched_versions)} fetched versions")
                    except Exception as ve:
                        logger.warning(f"Could not fetch versions for {actual_prompt_id}: {ve}")
                    
                    logger.info(f"Available versions count: {len(self._available_versions)}")
                    
                    # Sort versions by version number descending (latest first)
                    if self._available_versions:
                        self._available_versions.sort(key=lambda v: v.get("version", 0), reverse=True)
                        
                        # Build version options with status labels and metadata
                        version_options = [self._format_version_option(v) for v in self._available_versions]
                        version_metadata = [self._build_version_metadata(v) for v in self._available_versions]
                        build_config["prompt_version"]["options"] = version_options
                        build_config["prompt_version"]["options_metadata"] = version_metadata
                        build_config["prompt_version"]["advanced"] = False  # Show version dropdown
                        
                        logger.info(f"Version options: {version_options}")
                        
                        # Select the latest version by default
                        latest = self._available_versions[0]
                        self._selected_version_data = latest
                        build_config["prompt_version"]["value"] = self._format_version_option(latest)
                        logger.info(f"Selected version data keys: {latest.keys() if latest else 'None'}")
                        
                        # Update message_type options based on available roles in the version
                        available_roles = self._get_available_roles(latest)
                        build_config["message_type"]["options"] = available_roles
                        # Set default value to first available role
                        if available_roles:
                            build_config["message_type"]["value"] = available_roles[0]
                        
                        # Reveal message_type and template
                        build_config["message_type"]["advanced"] = False
                        build_config["template"]["advanced"] = False  # Show template field
                        
                        # Add prompt metadata to template field for frontend modal
                        build_config["template"]["prompt_id"] = actual_prompt_id
                        build_config["template"]["prompt_version"] = latest.get("version", 1)
                        build_config["template"]["version_status"] = latest.get("status", "DRAFT")
                        
                        # Load template content
                        self._load_version_content(build_config)
                        template_val = build_config["template"].get("value", "")
                        logger.info(f"Template value (first 100 chars): {template_val[:100] if template_val else 'EMPTY'}")
                        
                        # Clear loading state
                        build_config["prompt_version"]["is_loading"] = False
                        build_config["template"]["is_loading"] = False
                    else:
                        logger.warning(f"No versions available for prompt {field_value}")
                        build_config["prompt_version"]["options"] = []
                        build_config["prompt_version"]["advanced"] = True
                        build_config["prompt_version"]["is_loading"] = False
                        build_config["template"]["is_loading"] = False
                else:
                    self._selected_prompt_id = None
                    self._selected_version_data = None
                    self._available_versions = []
                    
                    # Hide version, message_type, and template fields
                    build_config["prompt_version"]["options"] = []
                    build_config["prompt_version"]["advanced"] = True
                    build_config["prompt_version"]["is_loading"] = False
                    build_config["message_type"]["advanced"] = True
                    build_config["template"]["advanced"] = True  # Hide template field
                    build_config["template"]["value"] = ""
                    build_config["template"]["is_loading"] = False
                    self._current_variables = []

            except Exception as e:
                logger.exception(f"Error refreshing prompts: {e}")
                build_config["saved_prompt"]["options"] = []
                build_config["prompt_version"]["is_loading"] = False
                build_config["template"]["is_loading"] = False

        # -----------------------------
        # Version selection change / refresh
        # -----------------------------
        elif field_name == "prompt_version":
            # Set loading state on template while fetching
            build_config["template"]["is_loading"] = True
            
            # Get token from build_config for authenticated API calls
            token = build_config.get("_token")
            
            # If we have a selected prompt, refresh the versions list
            if self._selected_prompt_id:
                try:
                    ps = get_prompt_service()
                    if ps.ready:
                        # Try to fetch versions from API
                        versions_response = await ps.get_prompt_versions(self._selected_prompt_id, token=token)
                        logger.info(f"Versions refresh response: {versions_response}")
                        
                        if not versions_response.get("error"):
                            versions_data = versions_response.get("data", {})
                            if isinstance(versions_data, dict):
                                fetched_versions = versions_data.get("versions", []) or []
                            elif isinstance(versions_data, list):
                                fetched_versions = versions_data
                            else:
                                fetched_versions = []
                            
                            if fetched_versions:
                                self._available_versions = fetched_versions
                                self._available_versions.sort(key=lambda v: v.get("version", 0), reverse=True)
                                version_options = [self._format_version_option(v) for v in self._available_versions]
                                build_config["prompt_version"]["options"] = version_options
                                logger.info(f"Refreshed version options: {version_options}")
                except Exception as ve:
                    logger.warning(f"Could not refresh versions: {ve}")
            
            # Handle version selection
            if field_value and self._available_versions:
                version_num = self._parse_version_from_option(field_value)
                if version_num:
                    # Find the selected version
                    selected = next(
                        (v for v in self._available_versions if v.get("version") == version_num),
                        None
                    )
                    if selected:
                        self._selected_version_data = selected
                        
                        # Update prompt metadata for the template field
                        build_config["template"]["prompt_version"] = version_num
                        build_config["template"]["version_status"] = selected.get("status", "DRAFT")
                        
                        # Update message_type options based on available roles in the selected version
                        available_roles = self._get_available_roles(selected)
                        build_config["message_type"]["options"] = available_roles
                        # Set default value to first available role if current value not in options
                        current_msg_type = build_config["message_type"].get("value")
                        if current_msg_type not in available_roles and available_roles:
                            build_config["message_type"]["value"] = available_roles[0]
                        
                        self._load_version_content(build_config)
                        
                        # Clear loading state
                        build_config["template"]["is_loading"] = False
            
            # Clear loading if no version selected
            if not field_value or not self._available_versions:
                build_config["template"]["is_loading"] = False

        # -----------------------------
        # Message type switch (system/user)
        # -----------------------------
        elif field_name == "message_type":
            if self._selected_version_data:
                content = self._get_message_by_role(field_value)
                build_config["template"]["value"] = content

                if content:
                    self._current_variables = self._process_template_variables(content, build_config)

        # -----------------------------
        # Template content change (extract variables)
        # -----------------------------
        elif field_name == "template":
            # When template content changes, re-extract variables
            if field_value:
                self._current_variables = self._process_template_variables(field_value, build_config)

        # -----------------------------
        # Sync build_config → component attrs
        # -----------------------------
        for key, val in build_config.items():
            if isinstance(val, dict) and "value" in val:
                setattr(self, key, val["value"])

        return build_config

    # -----------------------------------------------------
    # Fallback for dynamic UI fields
    # -----------------------------------------------------
    def _get_fallback_input(self, **kwargs):
        return DefaultPromptField(**kwargs)