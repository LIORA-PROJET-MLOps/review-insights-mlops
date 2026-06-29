FROM prom/prometheus:v3.5.3

COPY deploy/prometheus/prometheus.yml /etc/prometheus/prometheus.yml
COPY deploy/prometheus/rules /etc/prometheus/rules
COPY docker/prometheus/entrypoint.sh /entrypoint.sh

USER root
RUN chmod 0555 /entrypoint.sh
USER nobody

ENTRYPOINT ["/entrypoint.sh"]
