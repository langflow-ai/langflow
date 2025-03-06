from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

from loguru import logger
from sqlmodel import select

from langflow.services.base import Service
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.subscription.model import Subscription
from langflow.services.database.models.task.model import TaskCreate
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.base.triggers.model import BaseTriggerComponent
    from langflow.services.task_orchestration.service import TaskOrchestrationService
    from langflow.services.triggers.base_trigger import BaseTrigger


class TriggerService(Service):
    """Service responsible for managing triggers and subscriptions."""

    name = "triggers_service"
    _worker_task: asyncio.Task | None = None

    def __init__(self, task_orchestration_service: TaskOrchestrationService):
        """Initialize the trigger service.

        Args:
            task_orchestration_service: Service for creating and managing tasks
        """
        self.task_orchestration_service = task_orchestration_service

    async def start(self) -> None:
        """Start the trigger service and its worker."""
        logger.info("Starting trigger service")
        self._worker_task = asyncio.create_task(self.trigger_worker())
        logger.info("Trigger worker started")

    async def stop(self) -> None:
        """Stop the trigger service and its worker."""
        logger.info("Stopping trigger service")
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                logger.info("Trigger worker cancelled")
        logger.info("Trigger service stopped")

    async def trigger_worker(self) -> None:
        """Worker that periodically checks for events based on subscriptions."""
        while True:
            try:
                await self.check_and_trigger_events()
                await asyncio.sleep(10)  # Check every minute
            except asyncio.CancelledError:
                logger.info("Trigger worker cancelled")
                break
            except Exception as e:  # noqa: BLE001
                logger.error(f"Error in trigger worker: {e}")
                await asyncio.sleep(10)  # Wait before retrying

    async def create_subscriptions_for_flow(self, flow: Flow, session: AsyncSession) -> None:
        """Create subscriptions based on triggers found in the flow.

        Args:
            flow: The flow to create subscriptions for
            session: Database session
        """
        try:
            # Extract trigger components from the flow
            triggers = self._extract_triggers_from_flow(flow.data)

            # Create a subscription for each trigger
            for trigger in triggers:
                subscription = Subscription(
                    flow_id=flow.id,
                    event_type=trigger.event_type,
                    state=trigger.initial_state(),
                )
                session.add(subscription)
                logger.info(f"Created subscription for flow {flow.id} with event type {trigger.event_type}")

            await session.commit()
        except Exception as e:  # noqa: BLE001
            await session.rollback()
            logger.error(f"Error creating subscriptions for flow {flow.id}: {e}")

    async def update_subscriptions_for_flow(self, flow: Flow, session: AsyncSession) -> None:
        """Update subscriptions when a flow is updated.

        Args:
            flow: The flow to update subscriptions for
            session: Database session
        """
        try:
            # Delete existing subscriptions
            await self._delete_subscriptions_for_flow(flow.id, session)

            # Create new subscriptions
            await self.create_subscriptions_for_flow(flow, session)
        except Exception as e:  # noqa: BLE001
            await session.rollback()
            logger.error(f"Error updating subscriptions for flow {flow.id}: {e}")

    async def _delete_subscriptions_for_flow(self, flow_id: UUID, session: AsyncSession) -> None:
        """Delete all subscriptions for a flow.

        Args:
            flow_id: The flow ID to delete subscriptions for
            session: Database session
        """
        from sqlalchemy import delete

        try:
            await session.exec(delete(Subscription).where(Subscription.flow_id == flow_id))
            await session.commit()
            logger.info(f"Deleted subscriptions for flow {flow_id}")
        except Exception as e:  # noqa: BLE001
            await session.rollback()
            logger.error(f"Error deleting subscriptions for flow {flow_id}: {e}")

    async def check_and_trigger_events(self) -> None:
        """Check for events and trigger flows."""
        logger.debug("Checking for events")

        from langflow.services.deps import session_scope

        async with session_scope() as session:
            try:
                # Get all subscriptions that point to existing flows
                query = select(Subscription).join(Flow, Flow.id == Subscription.flow_id)
                result = await session.exec(query)
                subscriptions = result.all()

                for subscription in subscriptions:
                    try:
                        # Get the trigger class for this subscription
                        trigger_class = self._get_trigger_class_for_subscription(subscription)
                        if not trigger_class:
                            logger.warning(f"No trigger class found for subscription: {subscription.id}")
                            continue

                        # Check for events
                        events = await trigger_class.check_events(subscription)

                        # Create tasks for each event
                        for event in events:
                            event["subscription_id"] = subscription.id
                            await self._process_event(event, subscription)

                        # Update the subscription in the database
                        session.add(subscription)
                    except Exception as e:  # noqa: BLE001
                        logger.error(f"Error processing subscription {subscription.id}: {e}")

                await session.commit()
            except Exception as e:  # noqa: BLE001
                await session.rollback()
                logger.error(f"Error checking for events: {e}")

    async def _process_event(self, event: dict[str, Any], subscription: Subscription | None = None) -> None:
        """Process a single event.

        Args:
            event: The event to process
            subscription: The subscription to process the event for
        """
        try:
            if not subscription:
                subscription_id = event.get("subscription_id")
                if not subscription_id:
                    logger.warning("Event has no subscription_id, skipping")
                    return

                # Use the session_scope context manager instead of direct get_session call
                async with session_scope() as session:
                    if isinstance(subscription_id, str):
                        subscription_id = UUID(subscription_id)
                    result = await session.exec(select(Subscription).where(Subscription.id == subscription_id))
                    subscription = result.first()

                    if not subscription:
                        logger.warning(f"Subscription {subscription_id} not found, skipping event")
                        return

            # Create a task for the flow
            await self._create_task_from_event(subscription.flow_id, event)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error processing event: {e}")

    def _get_trigger_class_for_subscription(self, subscription: Subscription) -> type[BaseTrigger] | None:
        """Get the trigger class for a subscription.

        Args:
            subscription: The subscription to get the trigger class for

        Returns:
            The trigger class or None if not found
        """
        # Import all trigger components
        from langflow.components.triggers import (
            gmail_inbox_trigger,
            local_file_watcher,
            schedule_trigger,
            task_category_status_trigger,
        )

        # Map of event types to trigger classes
        event_type_map = {
            "gmail_message_received": gmail_inbox_trigger.GmailTrigger,
            "schedule_triggered": schedule_trigger.ScheduleTrigger,
            "local_file_updated": local_file_watcher.LocalFileWatcherTrigger,
            "task_category_status_updated": task_category_status_trigger.TaskCategoryStatusTrigger,
        }

        return event_type_map.get(subscription.event_type)

    async def _create_task_from_event(self, flow_id: UUID, event: dict[str, Any]) -> None:
        """Create a task from an event.

        Args:
            flow_id: The flow ID to create the task for
            event: The event data
        """
        try:
            trigger_data = event.get("trigger_data", {})

            # Create a task for the flow
            task_create = TaskCreate(
                title=f"Triggered by {trigger_data.get('source', 'external event')}",
                description=f"Event Data: {event}",
                status="pending",
                state="initial",
                author_id=flow_id,  # Using flow_id as author_id
                assignee_id=flow_id,  # Using flow_id as assignee_id
                category="trigger",  # Using "trigger" as the category
                attachments=[json.dumps(event, default=str)],
            )

            await self.task_orchestration_service.create_task(task_create)
            logger.info(f"Created task for flow {flow_id} from trigger event")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error creating task from event: {e}")

    def _extract_triggers_from_flow(self, flow_data: dict[str, Any]) -> list[BaseTrigger]:
        """Extract triggers from a flow.

        Args:
            flow_data: The flow data

        Returns:
            A list of triggers
        """
        triggers: list[BaseTrigger] = []
        if not flow_data or "nodes" not in flow_data:
            return triggers

        for node in flow_data["nodes"]:
            try:
                node_id = node.get("id", "")

                # Try to get the node type from different places
                node_type = node.get("type", "")

                # If not found directly, check in the data
                if not node_type:
                    node_data = node.get("data", {})
                    node_type = node_data.get("type", "")

                    # If still not found, check in the node.data.node structure
                    if not node_type and "node" in node_data:
                        node_type = node_data.get("node", {}).get("type", "")

                # If we still don't have a type, try to extract it from the node ID
                if not node_type and node_id:
                    # Check for common trigger component patterns in the node ID
                    if "GmailInboxTrigger" in node_id:
                        node_type = "GmailInboxTrigger"
                    elif "ScheduleTrigger" in node_id:
                        node_type = "ScheduleTrigger"
                    # Add more trigger types as needed

                    # If the node ID follows the pattern ComponentName-XXXX
                    elif "-" in node_id:
                        potential_type = node_id.split("-")[0]
                        # Check if it ends with "Component" or contains "Trigger"
                        if potential_type.endswith("Component") or "Trigger" in potential_type:
                            node_type = potential_type

                # Log the node type for debugging
                logger.debug(f"Node type: {node_type}, Node ID: {node_id}")

                if not node_type:
                    continue

                # Get the template data
                node_data = node.get("data", {})
                template = node_data.get("node", {}).get("template", {})

                # For Gmail trigger, check if it has the required fields
                if "GmailInboxTrigger" in node_type:
                    from langflow.components.triggers.gmail_inbox_trigger import GmailTrigger

                    # Extract the required fields from the template
                    email_address = template.get("email_address", {}).get("value", "")
                    query = template.get("query", {}).get("value", "is:unread")
                    poll_interval = template.get("poll_interval", {}).get("value", 300)

                    # Create the trigger directly
                    trigger = GmailTrigger(email_address=email_address, query=query, poll_interval=poll_interval)
                    triggers.append(trigger)
                    logger.debug(f"Found Gmail trigger in flow: {node_id}")
                    continue

                # For Schedule trigger, check if it has the required fields
                if "ScheduleTrigger" in node_type:
                    from langflow.components.triggers.schedule_trigger import ScheduleTrigger

                    # Extract the required fields from the template
                    cron_expression = template.get("cron_expression", {}).get("value", "* * * * *")
                    description = template.get("description", {}).get("value", "")

                    # Create the trigger directly
                    trigger = ScheduleTrigger(cron_expression=cron_expression, description=description)
                    triggers.append(trigger)
                    logger.debug(f"Found Schedule trigger in flow: {node_id}")
                    continue

                # Try to get the component class from the code
                component_class = None
                if "code" in template:
                    component_class = self._get_component_class(template["code"])

                # Check if this is a trigger component
                if component_class and self._is_trigger_component(component_class):
                    # Create a component instance
                    component_instance: BaseTriggerComponent = component_class(_id=node_id)

                    # Set the component data
                    for key, value in node_data.items():
                        if hasattr(component_instance, key):
                            setattr(component_instance, key, value)

                    # If the node has a template, set the template values on the component
                    if template:
                        attrs_dict = {
                            key: value_obj["value"]
                            for key, value_obj in template.items()
                            if isinstance(value_obj, dict) and "value" in value_obj
                        }
                        component_instance.set_attributes(attrs_dict)

                    # Get the trigger instance
                    trigger = component_instance.get_trigger_instance()
                    triggers.append(trigger)
                    logger.debug(f"Found trigger in flow: {node_id}")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Error creating trigger from node {node.get('id', '')}: {e}")
                import traceback

                logger.error(traceback.format_exc())

        return triggers

    def _get_component_class(self, code: str | dict) -> type | None:
        """Get the component class for a node type.

        Args:
            code: The code to get the component class for, can be a string or a dictionary with a 'value' key

        Returns:
            The component class or None if not found
        """
        try:
            from langflow.custom.eval import eval_custom_component_code

            # Handle the case when code is a dictionary
            if isinstance(code, dict) and "value" in code:
                code = code["value"]

            if not isinstance(code, str):
                logger.error(f"Invalid code type: {type(code)}, expected string or dict with 'value' key")
                return None

            return eval_custom_component_code(code)

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error getting component class for {code}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return None

    def _is_trigger_component(self, component_class: type) -> bool:
        """Check if a component class is a trigger component.

        Args:
            component_class: The component class to check

        Returns:
            True if the component is a trigger component, False otherwise
        """
        try:
            from langflow.base.triggers import BaseTriggerComponent

            return issubclass(component_class, BaseTriggerComponent)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error checking if component is a trigger: {e}")
            return False

    async def _check_events(self) -> list[dict[str, Any]]:
        """Check for events and return them without processing.

        This method is primarily used for testing.

        Returns:
            List of events that need to be processed
        """
        from sqlalchemy.future import select

        from langflow.services.deps import session_scope

        events = []

        async with session_scope() as session:
            try:
                # Get all subscriptions
                result = await session.exec(select(Subscription))
                subscriptions = result.scalars().all()

                for subscription in subscriptions:
                    try:
                        # Get the trigger class for this subscription
                        trigger_class = self._get_trigger_class_for_subscription(subscription)
                        if not trigger_class:
                            logger.warning(f"No trigger class found for subscription: {subscription.id}")
                            continue

                        # Check for events
                        subscription_events = await trigger_class.check_events(subscription)
                        events.extend(subscription_events)

                    except Exception as e:  # noqa: BLE001
                        logger.error(f"Error checking events for subscription {subscription.id}: {e}")

            except Exception as e:  # noqa: BLE001
                logger.error(f"Error checking for events: {e}")

        return events
