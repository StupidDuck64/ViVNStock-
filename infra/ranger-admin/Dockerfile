FROM phusion/baseimage:focal-1.0.0

# --------------------
# ENV & TIMEZONE
# --------------------
ENV TZ=Asia/Tokyo
ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/zulu11

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# --------------------
# BASE PACKAGES
# --------------------
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    sudo \
    wget \
    bc \
    apt-transport-https \
    gnupg \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create symlink for python if needed
RUN ln -sf /usr/bin/python3 /usr/bin/python || true

# --------------------
# ZULU JDK 11
# --------------------
RUN curl -s https://repos.azul.com/azul-repo.key | gpg --dearmor -o /usr/share/keyrings/azul.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/azul.gpg] https://repos.azul.com/zulu/deb stable main" \
    > /etc/apt/sources.list.d/zulu.list && \
    apt-get update && apt-get install -y zulu11-jdk && \
    rm -rf /var/lib/apt/lists/*

# Verify Java installation
RUN java -version

# --------------------
# POSTGRES JDBC (FIX: Download to correct location with proper naming)
# --------------------
RUN mkdir -p /root/ranger-admin/lib && \
    wget -O /root/postgresql.jar \
    https://jdbc.postgresql.org/download/postgresql-42.7.3.jar && \
    cp /root/postgresql.jar /root/ranger-admin/lib/ && \
    chmod 644 /root/postgresql.jar && \
    ls -lh /root/postgresql.jar

# --------------------
# WORKDIR & SOURCE
# --------------------
WORKDIR /root
COPY . /root/ranger-admin
COPY ./ranger-2.7.1-SNAPSHOT-admin.tar.gz /root

# --------------------
# PRE-CREATE VENV and INSTALL REQUIREMENTS
# --------------------
RUN if [ -f /root/ranger-admin/requirements.txt ]; then \
        python3 -m venv /root/ranger-admin/.venv && \
        /root/ranger-admin/.venv/bin/pip install --upgrade pip && \
        /root/ranger-admin/.venv/bin/pip install -r /root/ranger-admin/requirements.txt; \
    fi

# --------------------
# ENTRYPOINT FIX
# --------------------
RUN chmod +x /root/ranger-admin/docker-entrypoint.sh && \
    sed -i 's/\r$//' /root/ranger-admin/docker-entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:6080/ || exit 1

ENTRYPOINT ["bash", "/root/ranger-admin/docker-entrypoint.sh"]