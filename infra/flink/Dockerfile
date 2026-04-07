FROM flink:1.18-scala_2.12

USER root

# Install dependencies
RUN apt-get update && \
    apt-get install -y curl wget && \
    rm -rf /var/lib/apt/lists/*

# Create directories for checkpoints and savepoints
RUN mkdir -p /tmp/flink-checkpoints /tmp/flink-savepoints /tmp/flink-web-uploads /tmp/flink-completed-jobs && \
    chown -R flink:flink /tmp/flink-*

# Download OAuth2/OIDC related JARs (if needed for custom implementation)
# Note: Flink 1.18 has built-in OAuth2 support but may need additional libraries
RUN cd /opt/flink/lib && \
    wget -q https://repo1.maven.org/maven2/com/nimbusds/nimbus-jose-jwt/9.31/nimbus-jose-jwt-9.31.jar && \
    wget -q https://repo1.maven.org/maven2/com/nimbusds/oauth2-oidc-sdk/10.7.1/oauth2-oidc-sdk-10.7.1.jar

# Copy custom configuration
COPY flink-conf.yaml /opt/flink/conf/flink-conf.yaml

USER flink

# Example: add connectors or UDF jars
# COPY ./connectors/ /opt/flink/connectors/
