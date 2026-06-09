#!/usr/bin/env python3
"""Diagnostic tool for remote Langflow instances.

Helps debug connection issues and performance problems.
"""

import argparse
import json
import sys
import time
from typing import Any

import httpx


def test_connectivity(host: str) -> dict[str, Any]:
    """Test basic connectivity to the host."""
    print(f"🔗 Testing connectivity to {host}")

    results = {
        "host": host,
        "reachable": False,
        "health_check": False,
        "response_time_ms": None,
        "error": None,
    }

    try:
        start_time = time.time()
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{host}/health")
            end_time = time.time()

            results["reachable"] = True
            results["response_time_ms"] = round((end_time - start_time) * 1000, 2)
            results["health_check"] = response.status_code == 200
            results["status_code"] = response.status_code

            if response.status_code == 200:
                print(f"   ✅ Health check passed ({results['response_time_ms']}ms)")
            else:
                print(f"   ⚠️  Health check failed: {response.status_code}")
                results["error"] = f"HTTP {response.status_code}"

    except Exception as e:
        results["error"] = f"{type(e).__name__}: {e}"
        print(f"   ❌ Connection failed: {results['error']}")

    return results


def test_flow_endpoint(host: str, api_key: str, flow_id: str) -> dict[str, Any]:
    """Test a flow execution request."""
    print("🎯 Testing flow execution")

    results = {
        "success": False,
        "response_time_ms": None,
        "status_code": None,
        "error": None,
        "has_outputs": False,
    }

    try:
        url = f"{host}/api/v1/run/{flow_id}?stream=false"
        payload = {
            "input_value": "Hello, this is a diagnostic test",
            "output_type": "chat",
            "input_type": "chat",
            "tweaks": {},
        }
        headers = {"x-api-key": api_key, "Content-Type": "application/json"}

        start_time = time.time()
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=headers)
            end_time = time.time()

        results["response_time_ms"] = round((end_time - start_time) * 1000, 2)
        results["status_code"] = response.status_code

        if response.status_code == 200:
            try:
                data = response.json()
                results["has_outputs"] = bool(data.get("outputs"))
                results["success"] = results["has_outputs"]

                if results["success"]:
                    print(f"   ✅ Flow execution successful ({results['response_time_ms']}ms)")
                else:
                    print(f"   ⚠️  Flow executed but no outputs ({results['response_time_ms']}ms)")
                    results["error"] = "No outputs in response"

            except Exception as e:
                results["error"] = f"JSON decode error: {e}"
                print(f"   ❌ Invalid JSON response: {e}")
        else:
            results["error"] = f"HTTP {response.status_code}"
            print(f"   ❌ Flow execution failed: {response.status_code}")
            print(f"      Response: {response.text[:200]}...")

    except Exception as e:
        results["error"] = f"{type(e).__name__}: {e}"
        print(f"   ❌ Request failed: {results['error']}")

    return results


def run_load_simulation(host: str, api_key: str, flow_id: str, num_requests: int = 10) -> dict[str, Any]:
    """Run a small load simulation to test performance."""
    print(f"⚡ Running mini load test ({num_requests} requests)")

    results = {
        "total_requests": num_requests,
        "successful_requests": 0,
        "failed_requests": 0,
        "connection_errors": 0,
        "response_times": [],
        "errors": [],
    }

    url = f"{host}/api/v1/run/{flow_id}?stream=false"
    payload = {
        "input_value": "Load test message",
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": {},
    }
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    for i in range(num_requests):
        try:
            start_time = time.time()
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload, headers=headers)
                end_time = time.time()

            response_time = round((end_time - start_time) * 1000, 2)
            results["response_times"].append(response_time)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("outputs"):
                        results["successful_requests"] += 1
                        print(f"   ✅ Request {i + 1}: {response_time}ms")
                    else:
                        results["failed_requests"] += 1
                        results["errors"].append(f"Request {i + 1}: No outputs")
                        print(f"   ⚠️  Request {i + 1}: No outputs ({response_time}ms)")
                except Exception as e:
                    results["failed_requests"] += 1
                    results["errors"].append(f"Request {i + 1}: JSON error - {e}")
                    print(f"   ❌ Request {i + 1}: JSON error ({response_time}ms)")
            else:
                results["failed_requests"] += 1
                results["errors"].append(f"Request {i + 1}: HTTP {response.status_code}")
                print(f"   ❌ Request {i + 1}: HTTP {response.status_code} ({response_time}ms)")

        except Exception as e:
            results["connection_errors"] += 1
            results["errors"].append(f"Request {i + 1}: {type(e).__name__} - {e}")
            print(f"   💥 Request {i + 1}: Connection error - {e}")

    # Calculate statistics
    if results["response_times"]:
        results["avg_response_time"] = round(sum(results["response_times"]) / len(results["response_times"]), 2)
        results["min_response_time"] = min(results["response_times"])
        results["max_response_time"] = max(results["response_times"])

    return results


def main():
    parser = argparse.ArgumentParser(description="Diagnose remote Langflow instance")
    parser.add_argument("--host", required=True, help="Langflow host URL")
    parser.add_argument("--api-key", help="API key for flow execution")
    parser.add_argument("--flow-id", help="Flow ID for testing")
    parser.add_argument("--load-test", type=int, default=0, help="Number of requests for mini load test")
    parser.add_argument("--output", help="Save results to JSON file")

    args = parser.parse_args()

    print(f"🔍 Diagnosing Langflow instance: {args.host}")
    print("=" * 60)

    # Test basic connectivity
    connectivity_results = test_connectivity(args.host)

    # Test flow execution if credentials provided
    flow_results = None
    if args.api_key and args.flow_id:
        flow_results = test_flow_endpoint(args.host, args.api_key, args.flow_id)
    else:
        print("⚠️  Skipping flow test (no API key or flow ID provided)")

    # Run mini load test if requested
    load_results = None
    if args.load_test > 0 and args.api_key and args.flow_id:
        load_results = run_load_simulation(args.host, args.api_key, args.flow_id, args.load_test)

    # Summary
    print("\n" + "=" * 60)
    print("📋 DIAGNOSTIC SUMMARY")
    print("=" * 60)

    print(f"Host: {args.host}")
    print(f"Connectivity: {'✅ OK' if connectivity_results['reachable'] else '❌ FAILED'}")
    print(f"Health Check: {'✅ OK' if connectivity_results['health_check'] else '❌ FAILED'}")

    if connectivity_results["response_time_ms"]:
        print(f"Health Response Time: {connectivity_results['response_time_ms']}ms")

    if flow_results:
        print(f"Flow Execution: {'✅ OK' if flow_results['success'] else '❌ FAILED'}")
        if flow_results["response_time_ms"]:
            print(f"Flow Response Time: {flow_results['response_time_ms']}ms")

    if load_results:
        success_rate = (load_results["successful_requests"] / load_results["total_requests"]) * 100
        print(
            f"Mini Load Test: {load_results['successful_requests']}/{load_results['total_requests']} ({success_rate:.1f}% success)"
        )
        if load_results.get("avg_response_time"):
            print(f"Average Response Time: {load_results['avg_response_time']}ms")

    # Recommendations
    print("\n🔧 RECOMMENDATIONS:")
    if not connectivity_results["reachable"]:
        print("❌ Cannot reach the host - check URL and network connectivity")
    elif not connectivity_results["health_check"]:
        print("❌ Health check failed - Langflow may not be running properly")
    elif flow_results and not flow_results["success"]:
        print("❌ Flow execution failed - check API key, flow ID, and flow configuration")
    elif load_results and load_results["connection_errors"] > 0:
        print("⚠️  Connection errors detected - instance may be overloaded or unstable")
    elif load_results and load_results.get("avg_response_time", 0) > 10000:
        print("⚠️  Slow response times - consider reducing load or optimizing flow")
    else:
        print("✅ Instance appears healthy for load testing")

    # Save results if requested
    if args.output:
        results = {
            "timestamp": time.time(),
            "host": args.host,
            "connectivity": connectivity_results,
            "flow_execution": flow_results,
            "load_simulation": load_results,
        }

        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {args.output}")


if __name__ == "__main__":
    main()
