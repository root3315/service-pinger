#!/usr/bin/env python3
"""
Service Pinger - Check if your services are up and running.
"""

import argparse
import socket
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class ServiceResult:
    """Result of a service health check."""
    name: str
    url: str
    status: str
    response_time_ms: Optional[float]
    status_code: Optional[int]
    error: Optional[str]
    timestamp: str


def parse_service_url(url: str) -> Tuple[str, str, int]:
    """Parse a service URL into protocol, host, and port."""
    parsed = urlparse(url)
    
    if not parsed.scheme:
        url = f"http://{url}"
        parsed = urlparse(url)
    
    scheme = parsed.scheme.lower()
    host = parsed.hostname or "localhost"
    
    if parsed.port:
        port = parsed.port
    elif scheme == "https":
        port = 443
    elif scheme == "http":
        port = 80
    else:
        port = 443 if scheme == "https" else 80
    
    return scheme, host, port


def check_http_service(url: str, timeout: int) -> ServiceResult:
    """Check an HTTP/HTTPS service using requests library."""
    name = urlparse(url).hostname or url
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not HAS_REQUESTS:
        return ServiceResult(
            name=name,
            url=url,
            status="ERROR",
            response_time_ms=None,
            status_code=None,
            error="requests library not installed",
            timestamp=timestamp
        )
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout, verify=True)
        elapsed_ms = (time.time() - start_time) * 1000
        
        if 200 <= response.status_code < 400:
            status = "UP"
        else:
            status = "DEGRADED"
        
        return ServiceResult(
            name=name,
            url=url,
            status=status,
            response_time_ms=round(elapsed_ms, 2),
            status_code=response.status_code,
            error=None,
            timestamp=timestamp
        )
    except requests.exceptions.SSLError as e:
        return ServiceResult(
            name=name,
            url=url,
            status="DOWN",
            response_time_ms=None,
            status_code=None,
            error=f"SSL error: {str(e)}",
            timestamp=timestamp
        )
    except requests.exceptions.ConnectionError as e:
        return ServiceResult(
            name=name,
            url=url,
            status="DOWN",
            response_time_ms=None,
            status_code=None,
            error=f"Connection failed: {str(e)}",
            timestamp=timestamp
        )
    except requests.exceptions.Timeout:
        return ServiceResult(
            name=name,
            url=url,
            status="DOWN",
            response_time_ms=None,
            status_code=None,
            error="Request timed out",
            timestamp=timestamp
        )
    except requests.exceptions.RequestException as e:
        return ServiceResult(
            name=name,
            url=url,
            status="DOWN",
            response_time_ms=None,
            status_code=None,
            error=str(e),
            timestamp=timestamp
        )


def check_tcp_service(host: str, port: int, timeout: int) -> ServiceResult:
    """Check a TCP service by attempting to establish a connection."""
    url = f"{host}:{port}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        elapsed_ms = (time.time() - start_time) * 1000
        sock.close()
        
        if result == 0:
            return ServiceResult(
                name=f"{host}:{port}",
                url=url,
                status="UP",
                response_time_ms=round(elapsed_ms, 2),
                status_code=None,
                error=None,
                timestamp=timestamp
            )
        else:
            return ServiceResult(
                name=f"{host}:{port}",
                url=url,
                status="DOWN",
                response_time_ms=None,
                status_code=None,
                error=f"Connection refused (error code: {result})",
                timestamp=timestamp
            )
    except socket.timeout:
        return ServiceResult(
            name=f"{host}:{port}",
            url=url,
            status="DOWN",
            response_time_ms=None,
            status_code=None,
            error="Connection timed out",
            timestamp=timestamp
        )
    except socket.gaierror as e:
        return ServiceResult(
            name=f"{host}:{port}",
            url=url,
            status="DOWN",
            response_time_ms=None,
            status_code=None,
            error=f"DNS resolution failed: {str(e)}",
            timestamp=timestamp
        )
    except OSError as e:
        return ServiceResult(
            name=f"{host}:{port}",
            url=url,
            status="DOWN",
            response_time_ms=None,
            status_code=None,
            error=str(e),
            timestamp=timestamp
        )


def check_service(url: str, timeout: int) -> ServiceResult:
    """Check a service based on its URL scheme."""
    scheme, host, port = parse_service_url(url)
    
    if scheme in ("http", "https"):
        return check_http_service(url, timeout)
    else:
        return check_tcp_service(host, port, timeout)


def load_services_from_file(filepath: str) -> List[str]:
    """Load service URLs from a file (one per line)."""
    services = []
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    services.append(line)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found")
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    return services


def format_result(result: ServiceResult, verbose: bool = False) -> str:
    """Format a single result for display."""
    status_icons = {
        "UP": "✓",
        "DOWN": "✗",
        "DEGRADED": "!",
        "ERROR": "?"
    }
    
    status_colors = {
        "UP": "\033[92m",
        "DOWN": "\033[91m",
        "DEGRADED": "\033[93m",
        "ERROR": "\033[95m"
    }
    
    reset = "\033[0m"
    icon = status_icons.get(result.status, "?")
    color = status_colors.get(result.status, "")
    
    if result.response_time_ms is not None:
        time_str = f"{result.response_time_ms}ms"
    else:
        time_str = "-"
    
    if result.status_code is not None:
        code_str = f"[{result.status_code}]"
    else:
        code_str = ""
    
    line = f"{color}{icon} {result.name:<30} {result.status:<8} {time_str:>10} {code_str}{reset}"
    
    if verbose and result.error:
        line += f"\n   └─ Error: {result.error}"
    
    return line


def ping_services(services: List[str], timeout: int, workers: int, verbose: bool) -> List[ServiceResult]:
    """Ping all services concurrently."""
    results = []
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {executor.submit(check_service, url, timeout): url for url in services}
        
        for future in as_completed(future_to_url):
            result = future.result()
            results.append(result)
    
    results.sort(key=lambda r: (r.status != "UP", r.name))
    return results


def print_summary(results: List[ServiceResult]) -> None:
    """Print a summary of all results."""
    total = len(results)
    up = sum(1 for r in results if r.status == "UP")
    degraded = sum(1 for r in results if r.status == "DEGRADED")
    down = sum(1 for r in results if r.status == "DOWN")
    error = sum(1 for r in results if r.status == "ERROR")
    
    print()
    print("=" * 60)
    print(f"Summary: {up} up, {degraded} degraded, {down} down, {error} errors")
    print(f"Total: {total} services checked")
    
    if down > 0 or error > 0:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Ping services and check if they are up",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://google.com https://github.com
  %(prog)s -f services.txt
  %(prog)s -f services.txt -t 10 -w 5 -v
        """
    )
    
    parser.add_argument(
        "services",
        nargs="*",
        help="Service URLs to check (http://, https://, or host:port)"
    )
    parser.add_argument(
        "-f", "--file",
        dest="services_file",
        help="File containing service URLs (one per line)"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=5,
        help="Timeout in seconds (default: 5)"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=10,
        help="Number of concurrent workers (default: 10)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed error messages"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )
    
    args = parser.parse_args()
    
    services = list(args.services)
    
    if args.services_file:
        services.extend(load_services_from_file(args.services_file))
    
    if not services:
        parser.print_help()
        print("\nError: No services specified")
        sys.exit(1)
    
    print(f"Pinging {len(services)} service(s) with {args.workers} workers...\n")
    print(f"{'Status':<8} {'Service':<30} {'Response':>10} {'Code':>6}")
    print("-" * 60)
    
    results = ping_services(services, args.timeout, args.workers, args.verbose)
    
    for result in results:
        print(format_result(result, args.verbose))
    
    print_summary(results)


if __name__ == "__main__":
    main()
