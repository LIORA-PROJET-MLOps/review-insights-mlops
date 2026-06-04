from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict


@dataclass
class MonitoringStore:
    total_requests: int = 0
    human_review_requests: int = 0
    sentiment_counter: Counter = field(default_factory=Counter)
    theme_counter: Counter = field(default_factory=Counter)
    backend_counter: Counter = field(default_factory=Counter)
    inference_latency_ms: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    http_requests_total: int = 0
    http_error_requests: int = 0
    http_status_counter: Counter = field(default_factory=Counter)
    http_endpoint_counter: Counter = field(default_factory=Counter)
    http_latency_ms: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    _lock: Lock = field(default_factory=Lock)

    def record_prediction(self, result: Dict, backend_name: str, latency_ms: float) -> None:
        with self._lock:
            self.total_requests += 1
            self.backend_counter[backend_name] += 1
            self.inference_latency_ms.append(latency_ms)
            self.sentiment_counter[result.get("global_sentiment", "unknown")] += 1
            if result.get("needs_human_review"):
                self.human_review_requests += 1
            for theme in result.get("themes_detected", []):
                self.theme_counter[theme] += 1

    def record_http_request(self, method: str, path: str, status_code: int, latency_ms: float) -> None:
        endpoint = f"{method.upper()} {path}"
        status_family = f"{int(status_code / 100)}xx"
        with self._lock:
            self.http_requests_total += 1
            if status_code >= 500:
                self.http_error_requests += 1
            self.http_status_counter[str(status_code)] += 1
            self.http_status_counter[status_family] += 1
            self.http_endpoint_counter[endpoint] += 1
            self.http_latency_ms.append(latency_ms)

    def snapshot(self) -> Dict:
        with self._lock:
            human_review_rate = round(self.human_review_requests / self.total_requests, 4) if self.total_requests else 0.0
            sorted_latencies = sorted(self.inference_latency_ms)
            sorted_http_latencies = sorted(self.http_latency_ms)

            def percentile(values: list[float], fraction: float) -> float:
                if not values:
                    return 0.0
                index = min(len(values) - 1, round((len(values) - 1) * fraction))
                return round(values[index], 2)

            http_error_rate = round(self.http_error_requests / self.http_requests_total, 4) if self.http_requests_total else 0.0

            return {
                "total_requests": self.total_requests,
                "human_review_requests": self.human_review_requests,
                "human_review_rate": human_review_rate,
                "inference_latency_ms_avg": round(sum(sorted_latencies) / len(sorted_latencies), 2)
                if sorted_latencies
                else 0.0,
                "inference_latency_ms_p50": percentile(sorted_latencies, 0.5),
                "inference_latency_ms_p95": percentile(sorted_latencies, 0.95),
                "sentiment_distribution": dict(self.sentiment_counter),
                "theme_distribution": dict(self.theme_counter),
                "backend_distribution": dict(self.backend_counter),
                "http_requests_total": self.http_requests_total,
                "http_error_requests": self.http_error_requests,
                "http_error_rate": http_error_rate,
                "http_latency_ms_avg": round(sum(sorted_http_latencies) / len(sorted_http_latencies), 2)
                if sorted_http_latencies
                else 0.0,
                "http_latency_ms_p50": percentile(sorted_http_latencies, 0.5),
                "http_latency_ms_p95": percentile(sorted_http_latencies, 0.95),
                "http_status_distribution": dict(self.http_status_counter),
                "http_endpoint_distribution": dict(self.http_endpoint_counter),
            }
