FROM trinodb/trino:436

# Copy config files
COPY ./config/catalog /etc/trino/catalog
COPY ./config/access-control.properties /etc/trino/access-control.properties

# Run Trino directly (bypass Ranger plugin — Ranger service not running)
USER trino
CMD ["/usr/lib/trino/bin/run-trino"]