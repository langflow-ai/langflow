"""Direct MCP Protocol Stress Test.

Tests MCP servers using the actual MCP Python SDK for protocol compliance.
"""

import asyncio
import statistics
import time
from dataclasses import dataclass, field

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client


@dataclass
class StressTestResults:
    """Results from stress testing."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: list = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successful_requests / max(self.total_requests, 1) * 100

    @property
    def avg_response_time(self) -> float:
        return statistics.mean(self.response_times) if self.response_times else 0

    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]


async def test_mcp_streamable_http(
    base_url: str,
    api_key: str,
    num_requests: int = 100,
    concurrency: int = 10,
) -> StressTestResults:
    """Stress test MCP Streamable HTTP transport."""
    results = StressTestResults()
    semaphore = asyncio.Semaphore(concurrency)

    async def make_request():
        async with semaphore:
            start = time.perf_counter()
            try:
                headers = {"x-api-key": api_key}
                async with streamablehttp_client(
                    f"{base_url}/api/v1/mcp/streamable",
                    headers=headers,
                ) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        
                        results.successful_requests += 1
                        elapsed = time.perf_counter() - start
                        results.response_times.append(elapsed * 1000)  # ms
            except Exception as e:
                results.failed_requests += 1
                print(f"Request failed: {e}")
            finally:
                results.total_requests += 1

    # Run concurrent requests
    tasks = [make_request() for _ in range(num_requests)]
    await asyncio.gather(*tasks)
    return results


async def test_mcp_sse(
    base_url: str,
    api_key: str,
    num_requests: int = 100,
    concurrency: int = 10,
) -> StressTestResults:
    """Stress test MCP SSE transport."""
    results = StressTestResults()
    semaphore = asyncio.Semaphore(concurrency)

    async def make_request():
        async with semaphore:
            start = time.perf_counter()
            try:
                headers = {"x-api-key": api_key}
                async with sse_client(
                    f"{base_url}/api/v1/mcp/sse",
                    headers=headers,
                ) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()

                        results.successful_requests += 1
                        elapsed = time.perf_counter() - start
                        results.response_times.append(elapsed * 1000)
            except Exception as e:
                results.failed_requests += 1
                print(f"SSE request failed: {e}")
            finally:
                results.total_requests += 1

    tasks = [make_request() for _ in range(num_requests)]
    await asyncio.gather(*tasks)
    return results


async def test_project_mcp(
    base_url: str,
    api_key: str,
    project_id: str,
    num_requests: int = 50,
    concurrency: int = 5,
) -> StressTestResults:
    """Stress test project-specific MCP server."""
    results = StressTestResults()
    semaphore = asyncio.Semaphore(concurrency)

    async def make_request():
        async with semaphore:
            start = time.perf_counter()
            try:
                headers = {"x-api-key": api_key}
                url = f"{base_url}/api/v1/mcp/project/{project_id}/streamable"
                async with streamablehttp_client(url, headers=headers) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()

                        # Optionally call a tool
                        if tools.tools:
                            tool = tools.tools[0]
                            await session.call_tool(tool.name, {"input_value": "test"})

                        results.successful_requests += 1
                        elapsed = time.perf_counter() - start
                        results.response_times.append(elapsed * 1000)
            except Exception as e:
                results.failed_requests += 1
                print(f"Project MCP request failed: {e}")
            finally:
                results.total_requests += 1

    tasks = [make_request() for _ in range(num_requests)]
    await asyncio.gather(*tasks)
    return results


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="MCP Server Stress Test")
    parser.add_argument("--host", default="http://localhost:7860")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--project-id", help="Project ID for project-specific tests")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument(
        "--transport",
        choices=["streamable", "sse", "project", "all"],
        default="all",
    )
    args = parser.parse_args()

    print(f"\n🚀 MCP Server Stress Test")
    print(f"   Host: {args.host}")
    print(f"   Requests: {args.requests}")
    print(f"   Concurrency: {args.concurrency}")
    print("=" * 50)

    if args.transport in ("streamable", "all"):
        print("\n📡 Testing Streamable HTTP transport...")
        results = await test_mcp_streamable_http(
            args.host, args.api_key, args.requests, args.concurrency
        )
        print(f"   Success Rate: {results.success_rate:.1f}%")
        print(f"   Avg Response: {results.avg_response_time:.1f}ms")
        print(f"   P95 Response: {results.p95_response_time:.1f}ms")

    if args.transport in ("sse", "all"):
        print("\n📡 Testing SSE transport...")
        results = await test_mcp_sse(
            args.host, args.api_key, args.requests, args.concurrency
        )
        print(f"   Success Rate: {results.success_rate:.1f}%")
        print(f"   Avg Response: {results.avg_response_time:.1f}ms")
        print(f"   P95 Response: {results.p95_response_time:.1f}ms")

    if args.transport in ("project", "all") and args.project_id:
        print(f"\n📡 Testing Project MCP ({args.project_id})...")
        results = await test_project_mcp(
            args.host, args.api_key, args.project_id, args.requests, args.concurrency
        )
        print(f"   Success Rate: {results.success_rate:.1f}%")
        print(f"   Avg Response: {results.avg_response_time:.1f}ms")
        print(f"   P95 Response: {results.p95_response_time:.1f}ms")

    print("\n✅ Stress test complete!")


if __name__ == "__main__":
    asyncio.run(main())
