"""Black-box functional and latency probes for a deployed SahelWatch release."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass

import httpx


@dataclass
class ProbeResult:
    case: str
    status: int | None
    latency_ms: float
    probability: float | None = None
    degraded: bool | None = None
    aod_available: bool | None = None
    error: str | None = None


async def request_prediction(client: httpx.AsyncClient, base_url: str, name: str, lat: float, lon: float) -> ProbeResult:
    started = time.perf_counter()
    try:
        response = await client.get(
            f"{base_url}/api/v1/predict/location", params={"lat": lat, "lon": lon}
        )
        elapsed = (time.perf_counter() - started) * 1000
        payload = response.json()
        quality = payload.get("input_quality") or {}
        aod = quality.get("previous_day_aod") or {}
        return ProbeResult(
            case=name,
            status=response.status_code,
            latency_ms=round(elapsed, 1),
            probability=payload.get("probability"),
            degraded=quality.get("degraded"),
            aod_available=aod.get("available"),
            error=payload.get("detail") if response.status_code >= 400 else None,
        )
    except Exception as exc:
        return ProbeResult(
            case=name,
            status=None,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            error=f"{type(exc).__name__}: {exc}",
        )


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * fraction + 0.9999) - 1))
    return ordered[index]


async def fetch_covered_locations(client: httpx.AsyncClient, base_url: str, limit: int) -> list[tuple[str, float, float]]:
    """Discover the deployed catalogue so the probe never carries a stale city list."""
    response = await client.get(f"{base_url}/api/v1/coverage/places", params={"limit": 500})
    response.raise_for_status()
    places = response.json().get("places", [])
    if not places:
        raise RuntimeError("The deployed coverage catalogue is empty")
    selected = places if limit == 0 else places[:limit]
    return [
        (
            f"{place['name']}, {place['country']}",
            float(place.get("forecast_lat", place["lat"])),
            float(place.get("forecast_lon", place["lon"])),
        )
        for place in selected
    ]


async def run(base_url: str, concurrency: int, location_limit: int) -> dict:
    timeout = httpx.Timeout(90)
    limits = httpx.Limits(max_connections=max(concurrency, 20))
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        covered_locations = await fetch_covered_locations(client, base_url, location_limit)
        location_results = await asyncio.gather(*(
            request_prediction(client, base_url, name, lat, lon)
            for name, lat, lon in covered_locations
        ))

        invalid_results = await asyncio.gather(
            request_prediction(client, base_url, "invalid latitude", 9.99, 2.11),
            request_prediction(client, base_url, "invalid longitude", 13.51, 25.01),
        )

        semaphore = asyncio.Semaphore(concurrency)
        shared_name, shared_lat, shared_lon = covered_locations[0]

        async def concurrent_request(index: int) -> ProbeResult:
            async with semaphore:
                return await request_prediction(
                    client, base_url, f"concurrent {shared_name} {index}", shared_lat, shared_lon
                )

        concurrent_results = await asyncio.gather(*(
            concurrent_request(index) for index in range(1, 21)
        ))

    all_success = [item for item in location_results + concurrent_results if item.status == 200]
    latencies = [item.latency_ms for item in all_success]
    return {
        "base_url": base_url,
        "catalogue": {"tested": len(covered_locations), "limit": location_limit},
        "locations": [asdict(item) for item in location_results],
        "invalid_inputs": [asdict(item) for item in invalid_results],
        "concurrency": {
            "requests": len(concurrent_results),
            "successful": sum(item.status == 200 for item in concurrent_results),
            "results": [asdict(item) for item in concurrent_results],
        },
        "latency": {
            "successful_samples": len(latencies),
            "average_ms": round(statistics.fmean(latencies), 1) if latencies else None,
            "p95_ms": round(percentile(latencies, 0.95), 1) if latencies else None,
            "maximum_ms": round(max(latencies), 1) if latencies else None,
        },
    }


async def probe_out_of_distribution_inputs(model_url: str) -> list[dict]:
    """Observe model confidence for plausible and deliberately extreme inputs."""
    cases = {
        "reference": {
            "atmospheric": [[4.0, -2.0, 305.0, 98_000.0, 1_200.0, 0.0, 292.0]] * 72,
            "surface": [0.12, 0.35, 0.25, 13.51, 2.11, -0.5, -0.866],
        },
        "extreme_hot_dry_wind": {
            "atmospheric": [[80.0, -80.0, 350.0, 80_000.0, 8_000.0, 0.0, 250.0]] * 72,
            "surface": [0.0, 0.0, 3.0, 25.0, 25.0, 1.0, 1.0],
        },
        "physically_invalid": {
            "atmospheric": [[-500.0, 500.0, 100.0, -1.0, -100.0, -2.0, 500.0]] * 72,
            "surface": [-1.0, -1.0, -1.0, 90.0, 180.0, 2.0, 2.0],
        },
    }
    results = []
    async with httpx.AsyncClient(timeout=90) as client:
        for name, payload in cases.items():
            started = time.perf_counter()
            try:
                response = await client.post(model_url, json=payload)
                body = response.json()
                results.append({
                    "case": name,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    "probability": body.get("probability"),
                    "risk_level": body.get("risk_level"),
                    "detail": body.get("detail"),
                })
            except Exception as exc:
                results.append({
                    "case": name,
                    "status": None,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    "error": f"{type(exc).__name__}: {exc}",
                })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default="https://saheldust-backend.onrender.com"
    )
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument(
        "--location-limit", type=int, default=12,
        help="Number of API-discovered places to probe; use 0 to test the complete catalogue",
    )
    parser.add_argument("--output", default="functional-probe-results.json")
    parser.add_argument(
        "--model-url",
        help="Optional model endpoint for non-persistent out-of-distribution probes",
    )
    args = parser.parse_args()

    report = asyncio.run(run(
        args.base_url.rstrip("/"), max(1, args.concurrency), max(0, args.location_limit)
    ))
    if args.model_url:
        report["out_of_distribution"] = asyncio.run(
            probe_out_of_distribution_inputs(args.model_url)
        )
    rendered = json.dumps(report, indent=2)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
