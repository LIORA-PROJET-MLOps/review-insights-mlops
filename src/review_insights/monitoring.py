from __future__ import annotations

from collections import Counter
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
    _lock: Lock = field(default_factory=Lock)

    def record_prediction(self, result: Dict, backend_name: str) -> None:
        with self._lock:
            self.total_requests += 1
            self.backend_counter[backend_name] += 1
            self.sentiment_counter[result.get("global_sentiment", "unknown")] += 1
            if result.get("needs_human_review"):
                self.human_review_requests += 1
            for theme in result.get("themes_detected", []):
                self.theme_counter[theme] += 1

    def snapshot(self) -> Dict:
        with self._lock:
            human_review_rate = round(self.human_review_requests / self.total_requests, 4) if self.total_requests else 0.0
            return {
                "total_requests": self.total_requests,
                "human_review_requests": self.human_review_requests,
                "human_review_rate": human_review_rate,
                "sentiment_distribution": dict(self.sentiment_counter),
                "theme_distribution": dict(self.theme_counter),
                "backend_distribution": dict(self.backend_counter),
            }
