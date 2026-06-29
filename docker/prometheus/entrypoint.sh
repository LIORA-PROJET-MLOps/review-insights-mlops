#!/bin/sh
set -eu

umask 077
printf '%s' "${API_KEY:-prometheus-no-key-configured}" > /tmp/review_insights_api_key

exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --web.enable-lifecycle
