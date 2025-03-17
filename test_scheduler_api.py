#!/usr/bin/env python
"""Test script to test the scheduler API."""

import asyncio

import httpx


async def main():
    """Test the scheduler API."""
    print("Testing scheduler API...")

    # Get a valid flow ID
    async with httpx.AsyncClient() as client:
        # Get the first flow
        response = await client.get("http://localhost:7860/api/v1/flows/")
        if response.status_code != 200:
            print(f"Error getting flows: {response.status_code} {response.text}")
            return

        flows = response.json()
        if not flows:
            print("No flows found. Please create a flow first.")
            return

        flow_id = flows[0]["id"]
        print(f"Found flow: {flows[0]['name']} (ID: {flow_id})")

        # Create a scheduler
        scheduler_data = {
            "name": "Test Scheduler API",
            "description": "Test scheduler created via API",
            "flow_id": flow_id,
            "cron_expression": "*/10 * * * *",  # Run every 10 minutes
            "enabled": True
        }

        print(f"Creating scheduler: {scheduler_data}")
        response = await client.post(
            "http://localhost:7860/api/v1/schedulers/",
            json=scheduler_data
        )

        if response.status_code == 201:
            scheduler = response.json()
            print(f"Created scheduler: {scheduler}")

            # Get the scheduler
            scheduler_id = scheduler["id"]
            response = await client.get(f"http://localhost:7860/api/v1/schedulers/{scheduler_id}")
            if response.status_code == 200:
                print(f"Retrieved scheduler: {response.json()}")
            else:
                print(f"Error getting scheduler: {response.status_code} {response.text}")

            # Get all schedulers
            response = await client.get("http://localhost:7860/api/v1/schedulers/")
            if response.status_code == 200:
                print(f"All schedulers: {response.json()}")
            else:
                print(f"Error getting all schedulers: {response.status_code} {response.text}")

            # Update the scheduler
            update_data = {
                "name": "Updated Scheduler",
                "cron_expression": "*/15 * * * *"  # Run every 15 minutes
            }
            response = await client.patch(
                f"http://localhost:7860/api/v1/schedulers/{scheduler_id}",
                json=update_data
            )
            if response.status_code == 200:
                print(f"Updated scheduler: {response.json()}")
            else:
                print(f"Error updating scheduler: {response.status_code} {response.text}")

            # Delete the scheduler
            response = await client.delete(f"http://localhost:7860/api/v1/schedulers/{scheduler_id}")
            if response.status_code == 204:
                print("Scheduler deleted successfully")
            else:
                print(f"Error deleting scheduler: {response.status_code} {response.text}")
        else:
            print(f"Error creating scheduler: {response.status_code} {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
