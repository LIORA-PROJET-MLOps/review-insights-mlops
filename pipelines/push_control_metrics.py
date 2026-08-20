from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from orchestration.control_metrics import (
    push_ingestion_metrics,
    push_release_metrics,
    push_training_metrics,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a completed pipeline report to Pushgateway.")
    parser.add_argument("kind", choices=("ingestion", "training", "release"))
    parser.add_argument("payload", type=Path)
    parser.add_argument("--gateway-url", default="http://pushgateway:9091")
    parser.add_argument("--model-manifest", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    if args.kind == "training":
        payload = dict(payload.get("summary", payload))
        if args.model_manifest is not None:
            manifest = json.loads(args.model_manifest.read_text(encoding="utf-8"))
            payload.setdefault("training_rows", manifest.get("training", {}).get("training_rows", 0))
        pushed = push_training_metrics(payload, gateway_url=args.gateway_url)
    elif args.kind == "release":
        pushed = push_release_metrics(payload, gateway_url=args.gateway_url)
    else:
        pushed = push_ingestion_metrics(payload, gateway_url=args.gateway_url)
    print(json.dumps({"kind": args.kind, "pushed": pushed}, indent=2))
    if not pushed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
