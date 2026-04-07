# Optional custom Keycloak image (extends official)

FROM quay.io/keycloak/keycloak:23.0

USER root

# Copy realm for auto import
COPY data-platform.json /opt/keycloak/data/import/data-platform.json

# Copy vault entrypoint to fetch secrets before Keycloak boots
COPY vault-entrypoint.sh /vault-entrypoint.sh
RUN chmod +x /vault-entrypoint.sh

USER keycloak

ENTRYPOINT ["/vault-entrypoint.sh"]

