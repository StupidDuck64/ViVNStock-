# DOC DETAIL - Phan tich sieu chi tiet theo tung file Python/YAML/XML

## 1. Tong quan
- Tong so file duoc phan tich: 103
- Python: 61
- YAML/YML: 29
- XML: 13
- So service co dependency map tu compose: 40

## 2. Dependency map tong hop tu docker-compose
- airflow-apiserver -> redis, postgres, airflow-init
- airflow-dag-processor -> redis, postgres, airflow-init
- airflow-init -> redis, postgres
- airflow-scheduler -> redis, postgres, airflow-init
- airflow-triggerer -> redis, postgres, airflow-init
- airflow-worker -> airflow-apiserver, redis, postgres, airflow-init
- clickhouse-01 -> keeper-1, keeper-2, keeper-3
- clickhouse-02 -> keeper-1, keeper-2, keeper-3
- datahub-actions -> datahub-gms
- datahub-frontend-react -> datahub-gms
- datahub-gms -> datahub-upgrade
- datahub-ingestion -> datahub-gms
- datahub-upgrade -> elasticsearch-setup, kafka-setup, postgres-setup, kafka, schema-registry
- debezium -> kafka, postgres, schema-registry
- debezium-ui -> debezium
- elasticsearch-setup -> elasticsearch
- execute-migrate-all -> elasticsearch, postgres
- flink-nginx-proxy -> keycloak, flink-jobmanager
- flink-taskmanager -> flink-jobmanager
- hive-metastore -> postgres
- ingestion -> elasticsearch, postgres, openmetadata-server
- kafka-setup -> kafka
- kafka-ui -> kafka, schema-registry
- keycloak -> keycloak-db
- keycloak-init -> keycloak
- lakehouse-portal -> oauth2-proxy, keycloak
- oauth2-proxy -> keycloak
- openmetadata-server -> elasticsearch, postgres, execute-migrate-all, keycloak
- postgres-setup -> postgres
- ranger-admin -> postgres, hive-metastore
- ranger-usersync -> keycloak, ranger-admin
- schema-registry -> kafka
- spark-master -> minio, hive-metastore, kafka
- spark-thriftserver -> minio, hive-metastore, spark-master
- spark-worker-1 -> spark-master
- spark-worker-2 -> spark-master
- superset -> postgres, redis, trino
- superset-worker -> redis, superset
- vault-init -> vault
- vault-setup -> vault

## 3. Chi tiet tung file
### 3.1 File: .gitlab-ci.yml
- Loai: .yml
- Service suy luan: N/A
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (0):

### 3.2 File: .gitlab/ci/build.yml
- Loai: .yml
- Service suy luan: N/A
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: debezium, hive-metastore, ingestion, kafka-ui, keycloak, openmetadata-server, ranger-admin, schema-registry, spark-thriftserver, superset
- Top-level keys (1):
  - build

### 3.3 File: .gitlab/ci/deploy.yml
- Loai: .yml
- Service suy luan: N/A
- Bien env phat hien: DEPLOY_HOST, DEPLOY_PATH, DEPLOY_USER
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (2):
  - deploy
  - stop

### 3.4 File: .gitlab/ci/lint.yml
- Loai: .yml
- Service suy luan: N/A
- Bien env phat hien: LINT_FAILED, dockerfile, script
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (1):
  - lint

### 3.5 File: .gitlab/ci/publish.yml
- Loai: .yml
- Service suy luan: N/A
- Bien env phat hien: CI_COMMIT_REF_SLUG, DOCKERHUB_REPO, DOCKERHUB_TOKEN, DOCKERHUB_USERNAME, IMAGE_TAG, SERVICES, SOURCE, TARGET_BRANCH, TARGET_LATEST, svc
- Dependency map:
  - Service name references in file: debezium, hive-metastore, ingestion, kafka-ui, keycloak, openmetadata-server, ranger-admin, schema-registry, spark-thriftserver, superset
- Top-level keys (1):
  - publish

### 3.6 File: .gitlab/ci/security.yml
- Loai: .yml
- Service suy luan: N/A
- Bien env phat hien: DOCKERFILE, TRIVY_SEVERITY, service
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (4):
  - include
  - sast
  - secret_detection
  - security

### 3.7 File: .gitlab/ci/templates.yml
- Loai: .yml
- Service suy luan: N/A
- Bien env phat hien: BUILD_CONTEXT, CI_COMMIT_REF_SLUG, CI_PROJECT_DIR, COMPOSE_PROFILES, DOCKERFILE_PATH, DOCKERHUB_REPO, DOCKERHUB_TOKEN, DOCKERHUB_USERNAME, IMAGE_NAME, IMAGE_TAG
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (2):
  - .kaniko-build
  - .deploy-base

### 3.8 File: .gitlab/ci/test.yml
- Loai: .yml
- Service suy luan: N/A
- Bien env phat hien: ERRORS, dag_file, py_file
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (1):
  - test

### 3.9 File: .hadolint.yaml
- Loai: .yaml
- Service suy luan: N/A
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (2):
  - ignored
  - trustedRegistries

### 3.10 File: add_aud_mapper.py
- Loai: .py
- Service suy luan: N/A
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: keycloak, lakehouse-portal
- Imports (1):
  - json
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.11 File: append_portal_client.py
- Loai: .py
- Service suy luan: N/A
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: keycloak, lakehouse-portal
- Imports (1):
  - json
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.12 File: docker-compose.yml
- Loai: .yml
- Service suy luan: compose-root
- Bien env phat hien: ACTIONS_CONFIG, ACTIONS_EXTRA_PACKAGES, AIRFLOW_ADMIN_EMAIL, AIRFLOW_ADMIN_FIRSTNAME, AIRFLOW_ADMIN_LASTNAME, AIRFLOW_ADMIN_PASSWORD, AIRFLOW_ADMIN_USERNAME, AIRFLOW_API_SECRET_KEY, AIRFLOW_AUTH_MANAGER, AIRFLOW_CELERY_BROKER_URL, AIRFLOW_CELERY_RESULT_BACKEND, AIRFLOW_DAGS_ARE_PAUSED_AT_CREATION, AIRFLOW_DATABASE_SQL_ALCHEMY_CONN, AIRFLOW_DB, AIRFLOW_DB_HOST, AIRFLOW_DB_PASSWORD, AIRFLOW_DB_PORT, AIRFLOW_DB_PROPERTIES, AIRFLOW_DB_SCHEME, AIRFLOW_DB_USER, AIRFLOW_EXECUTION_API_SERVER_URL, AIRFLOW_EXECUTOR, AIRFLOW_FERNET_KEY, AIRFLOW_LOAD_EXAMPLES, AIRFLOW_PASSWORD, AIRFLOW_SCHEDULER_ENABLE_HEALTH_CHECK, AIRFLOW_TIMEOUT, AIRFLOW_TRUST_STORE_PASSWORD, AIRFLOW_TRUST_STORE_PATH, AIRFLOW_UID, AIRFLOW_UI_PORT, AIRFLOW_USERNAME, AIRFLOW__API_AUTH__JWT_SECRET_KEY, AIRFLOW__WEBSERVER__BASE_URL, AUTHENTICATION_AUTHORITY, AUTHENTICATION_CALLBACK_URL, AUTHENTICATION_CLIENT_ID, AUTHENTICATION_CLIENT_TYPE, AUTHENTICATION_ENABLE_SELF_SIGNUP, AUTHENTICATION_JWT_PRINCIPAL_CLAIMS, AUTHENTICATION_JWT_PRINCIPAL_CLAIMS_MAPPING, AUTHENTICATION_LDAP_ALLOWED_HOSTNAMES, AUTHENTICATION_LDAP_ALLOW_WILDCARDS, AUTHENTICATION_LDAP_EXAMINE_VALIDITY_DATES, AUTHENTICATION_LDAP_HOST, AUTHENTICATION_LDAP_KEYSTORE_PASSWORD, AUTHENTICATION_LDAP_POOL_SIZE, AUTHENTICATION_LDAP_PORT, AUTHENTICATION_LDAP_SSL_ENABLED, AUTHENTICATION_LDAP_SSL_KEY_FORMAT, AUTHENTICATION_LDAP_SSL_VERIFY_CERT_HOST, AUTHENTICATION_LDAP_TRUSTSTORE_PATH, AUTHENTICATION_LDAP_TRUSTSTORE_TYPE, AUTHENTICATION_LOOKUP_ADMIN_DN, AUTHENTICATION_LOOKUP_ADMIN_PWD, AUTHENTICATION_PROVIDER, AUTHENTICATION_PUBLIC_KEYS, AUTHENTICATION_RESPONSE_TYPE, AUTHENTICATION_USER_LOOKUP_BASEDN, AUTHENTICATION_USER_MAIL_ATTR, AUTHORIZER_ADMIN_PRINCIPALS, AUTHORIZER_ALLOWED_DOMAINS, AUTHORIZER_ALLOWED_REGISTRATION_DOMAIN, AUTHORIZER_CLASS_NAME, AUTHORIZER_ENABLE_SECURE_SOCKET, AUTHORIZER_ENABLE_SMTP, AUTHORIZER_ENFORCE_PRINCIPAL_DOMAIN, AUTHORIZER_INGESTION_PRINCIPALS, AUTHORIZER_PRINCIPAL_DOMAIN, AUTHORIZER_REQUEST_FILTER, AUTH_OIDC_BASE_URL, AUTH_OIDC_CLIENT_AUTHENTICATION_METHOD, AUTH_OIDC_CLIENT_ID, AUTH_OIDC_CLIENT_SECRET, AUTH_OIDC_DISCOVERY_URI, AUTH_OIDC_ENABLED, AUTH_OIDC_EXTRACT_GROUPS_ENABLED, AUTH_OIDC_EXTRACT_JWT_ACCESS_TOKEN_CLAIMS, AUTH_OIDC_GROUPS_CLAIM, AUTH_OIDC_JIT_PROVISIONING_ENABLED, AUTH_OIDC_PREFERRED_JWS_ALGORITHM, AUTH_OIDC_PRE_PROVISIONING_REQUIRED, AUTH_OIDC_READ_TIMEOUT, AUTH_OIDC_RESPONSE_MODE, AUTH_OIDC_RESPONSE_TYPE, AUTH_OIDC_SCOPE, AUTH_OIDC_USER_NAME_CLAIM, AUTH_OIDC_USER_NAME_CLAIM_REGEX, AUTH_OIDC_USE_NONCE, CLICKHOUSE_DB, CLICKHOUSE_PASSWORD, CLICKHOUSE_USER, CUSTOM_OIDC_AUTHENTICATION_PROVIDER_NAME, DATAHUB_DB_NAME, DATAHUB_MAPPED_FRONTEND_PORT, DATAHUB_MAPPED_GMS_PORT, DATAHUB_PRECREATE_TOPICS, DATAHUB_SERVER_TYPE, DATAHUB_TELEMETRY_ENABLED, DATA_GEN_P_CUSTOMER_INTERACTION, DATA_GEN_P_INVENTORY_EVENT, DATA_GEN_RATE_MPS, DATA_GEN_SEED_PRODUCTS, DATA_GEN_SEED_SUPPLIERS, DATA_GEN_SEED_USERS, DATA_GEN_SEED_WAREHOUSES, DATA_GEN_TOPIC_CUSTOMER_INTERACTIONS, DATA_GEN_TOPIC_INVENTORY_CHANGES, DATA_GEN_TOPIC_ORDERS, DATA_GEN_TOPIC_PAYMENTS, DATA_GEN_TOPIC_SHIPMENTS, DB_DRIVER_CLASS, DB_HOST, DB_PARAMS, DB_PORT, DB_SCHEME, DB_USER, DB_USER_PASSWORD, DEBEZIUM_CONFIG_STORAGE_TOPIC, DEBEZIUM_GROUP_ID, DEBEZIUM_OFFSET_STORAGE_TOPIC, DEBEZIUM_STATUS_STORAGE_TOPIC, ELASTICSEARCH_BATCH_SIZE, ELASTICSEARCH_CONNECTION_TIMEOUT_SECS, ELASTICSEARCH_HOST, ELASTICSEARCH_HTTP_PORT, ELASTICSEARCH_INDEX_MAPPING_LANG, ELASTICSEARCH_KEEP_ALIVE_TIMEOUT_SECS, ELASTICSEARCH_PASSWORD, ELASTICSEARCH_PAYLOAD_BYTES_SIZE, ELASTICSEARCH_PORT, ELASTICSEARCH_SCHEME, ELASTICSEARCH_SOCKET_TIMEOUT_SECS, ELASTICSEARCH_TRANSPORT_PORT, ELASTICSEARCH_TRUST_STORE_PASSWORD, ELASTICSEARCH_TRUST_STORE_PATH, ELASTICSEARCH_USER, ELASTICSEARCH_USE_SSL, ES_JAVA_OPTS, EVENT_MONITOR, EVENT_MONITOR_BATCH_SIZE, EVENT_MONITOR_LATENCY, EVENT_MONITOR_PATH_PATTERN, FERNET_KEY, FLINK_NGINX_OIDC_CLIENT_SECRET, FLINK_OAUTH2_CLIENT_SECRET, GRAPH_SERVICE_IMPL, HIVE_METASTORE_DB_HOST, HIVE_METASTORE_DB_NAME, HIVE_METASTORE_DB_PASS, HIVE_METASTORE_DB_TYPE, HIVE_METASTORE_DB_USER, HOME, HOSTNAME, JUPYTER_ENABLE_LAB, JWT_ISSUER, JWT_KEY_ID, KAFKA_AUTO_CREATE_TOPICS_ENABLE, KAFKA_BOOTSTRAP, KAFKA_CONSUMER_STOP_ON_DESERIALIZATION_ERROR, KAFKA_CONTROLLER_QUORUM_VOTERS, KAFKA_NODE_ID, KAFKA_PROCESS_ROLES, KC_DB_PASSWORD, KEYCLOAK_ADMIN_API_SECRET, KEYCLOAK_ADMIN_PASSWORD, KEYCLOAK_HOST, KEYCLOAK_PORT, KIBANA_PASSWORD, KIBANA_USER, LOG_LEVEL, MASK_PASSWORDS_API, METADATA_SERVICE_AUTH_ENABLED, MIGRATION_LIMIT_PARAM, MINIO_ROOT_PASSWORD, MINIO_ROOT_USER, NIFI_ADMIN_PASSWORD, OAUTH2_PROXY_CLIENT_SECRET, OAUTH2_PROXY_COOKIE_SECRET, OIDC_CALLBACK, OIDC_CLIENT_AUTH_METHOD, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_CUSTOM_PARAMS, OIDC_DISABLE_PKCE, OIDC_DISCOVERY_URI, OIDC_MAX_AGE, OIDC_MAX_CLOCK_SKEW, OIDC_PREFERRED_JWS, OIDC_PROMPT_TYPE, OIDC_RESPONSE_TYPE, OIDC_SCOPE, OIDC_SERVER_URL, OIDC_SESSION_EXPIRY, OIDC_TENANT, OIDC_TYPE, OIDC_USE_NONCE, OM_DATABASE, OM_EMAIL_ENTITY, OM_SM_ACCESS_KEY, OM_SM_ACCESS_KEY_ID, OM_SM_CLIENT_ID, OM_SM_CLIENT_SECRET, OM_SM_REGION, OM_SM_TENANT_ID, OM_SM_VAULT_NAME, OM_SUPPORT_URL, OPENMETADATA_CLUSTER_NAME, OPENMETADATA_HEAP_OPTS, OPENMETADATA_SERVER_URL, OPENMETADATA_SMTP_SENDER_MAIL, ORACLE_HOST, ORACLE_PASSWORD, ORACLE_PORT, ORACLE_SERVICE_NAME, ORACLE_USER, PG_DSN, PIPELINE_SERVICE_CLIENT_CLASS_NAME, PIPELINE_SERVICE_CLIENT_ENABLED, PIPELINE_SERVICE_CLIENT_ENDPOINT, PIPELINE_SERVICE_CLIENT_HEALTH_CHECK_INTERVAL, PIPELINE_SERVICE_CLIENT_HOST_IP, PIPELINE_SERVICE_CLIENT_SECRETS_MANAGER_LOADER, PIPELINE_SERVICE_CLIENT_SSL_CERT_PATH, PIPELINE_SERVICE_CLIENT_VERIFY_SSL, PIPELINE_SERVICE_IP_INFO_ENABLED, PORTAL_PORT, POSTGRES_CDC_PASSWORD, POSTGRES_CDC_USER, POSTGRES_DB, POSTGRES_HOST, POSTGRES_MAPPED_PORT, POSTGRES_MULTIPLE_DATABASES, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER, RANGER_ADMIN_PASS, RANGER_OAUTH2_SECRET, RSA_PRIVATE_KEY_FILE_PATH, RSA_PUBLIC_KEY_FILE_PATH, S3_ENDPOINT, SAML_AUTHORITY_URL, SAML_DEBUG_MODE, SAML_IDP_CERTIFICATE, SAML_IDP_ENTITY_ID, SAML_IDP_NAME_ID, SAML_IDP_SSO_LOGIN_URL, SAML_KEYSTORE_ALIAS, SAML_KEYSTORE_FILE_PATH, SAML_KEYSTORE_PASSWORD, SAML_SEND_ENCRYPTED_NAME_ID, SAML_SEND_SIGNED_AUTH_REQUEST, SAML_SIGNED_SP_METADATA, SAML_SP_ACS, SAML_SP_CALLBACK, SAML_SP_CERTIFICATE, SAML_SP_ENTITY_ID, SAML_SP_TOKEN_VALIDITY, SAML_STRICT_MODE, SAML_WANT_ASSERTION_ENCRYPTED, SAML_WANT_ASSERTION_SIGNED, SAML_WANT_MESSAGE_SIGNED, SAML_WANT_NAME_ID_ENCRYPTED, SCHEMA_REGISTRY_URL, SEARCH_TYPE, SECRET_MANAGER, SERVER_ADMIN_PORT, SERVER_HOST_API_URL, SERVER_PORT, SMTP_SERVER_ENDPOINT, SMTP_SERVER_PORT, SMTP_SERVER_PWD, SMTP_SERVER_STRATEGY, SMTP_SERVER_USERNAME, SPARK_MASTER_MODE, SPARK_MASTER_URL, SPARK_WORKER_MODE, SUPERSET_ADMIN_EMAIL, SUPERSET_ADMIN_FIRSTNAME, SUPERSET_ADMIN_LASTNAME, SUPERSET_ADMIN_PASSWORD, SUPERSET_ADMIN_USERNAME, SUPERSET_SECRET_KEY, USE_AWS_ELASTICSEARCH, WEB_CONF_CACHE_CONTROL, WEB_CONF_CONTENT_TYPE_OPTIONS_ENABLED, WEB_CONF_FRAME_OPTION, WEB_CONF_FRAME_OPTION_ENABLED, WEB_CONF_FRAME_ORIGIN, WEB_CONF_HSTS_ENABLED, WEB_CONF_HSTS_INCLUDE_SUBDOMAINS, WEB_CONF_HSTS_MAX_AGE, WEB_CONF_HSTS_PRELOAD, WEB_CONF_PERMISSION_POLICY_ENABLED, WEB_CONF_PERMISSION_POLICY_OPTION, WEB_CONF_PRAGMA, WEB_CONF_REFERRER_POLICY_ENABLED, WEB_CONF_REFERRER_POLICY_OPTION, WEB_CONF_URI_PATH, WEB_CONF_XSS_CSP_ENABLED, WEB_CONF_XSS_CSP_POLICY, WEB_CONF_XSS_CSP_REPORT_ONLY_POLICY, WEB_CONF_XSS_PROTECTION_BLOCK, WEB_CONF_XSS_PROTECTION_ENABLED, WEB_CONF_XSS_PROTECTION_ON, XPACK_SECURITY_ENABLED
- Dependency map:
  - Service name references in file: airflow-apiserver, airflow-dag-processor, airflow-init, airflow-scheduler, airflow-triggerer, airflow-worker, clickhouse-01, clickhouse-02, datahub-actions, datahub-frontend-react, datahub-gms, datahub-ingestion, datahub-upgrade, debezium, debezium-ui, elasticsearch-setup, execute-migrate-all, flink-nginx-proxy, flink-taskmanager, hive-metastore
- Top-level keys (3):
  - x-airflow-common
  - services
  - volumes
- Compose dependency map chi tiet:
  - airflow-apiserver: redis, postgres, airflow-init
  - airflow-dag-processor: redis, postgres, airflow-init
  - airflow-init: redis, postgres
  - airflow-scheduler: redis, postgres, airflow-init
  - airflow-triggerer: redis, postgres, airflow-init
  - airflow-worker: airflow-apiserver, redis, postgres, airflow-init
  - clickhouse-01: keeper-1, keeper-2, keeper-3
  - clickhouse-02: keeper-1, keeper-2, keeper-3
  - datahub-actions: datahub-gms
  - datahub-frontend-react: datahub-gms
  - datahub-gms: datahub-upgrade
  - datahub-ingestion: datahub-gms
  - datahub-upgrade: elasticsearch-setup, kafka-setup, postgres-setup, kafka, schema-registry
  - debezium: kafka, postgres, schema-registry
  - debezium-ui: debezium
  - elasticsearch-setup: elasticsearch
  - execute-migrate-all: elasticsearch, postgres
  - flink-nginx-proxy: keycloak, flink-jobmanager
  - flink-taskmanager: flink-jobmanager
  - hive-metastore: postgres
  - ingestion: elasticsearch, postgres, openmetadata-server
  - kafka-setup: kafka
  - kafka-ui: kafka, schema-registry
  - keycloak: keycloak-db
  - keycloak-init: keycloak
  - lakehouse-portal: oauth2-proxy, keycloak
  - oauth2-proxy: keycloak
  - openmetadata-server: elasticsearch, postgres, execute-migrate-all, keycloak
  - postgres-setup: postgres
  - ranger-admin: postgres, hive-metastore
  - ranger-usersync: keycloak, ranger-admin
  - schema-registry: kafka
  - spark-master: minio, hive-metastore, kafka
  - spark-thriftserver: minio, hive-metastore, spark-master
  - spark-worker-1: spark-master
  - spark-worker-2: spark-master
  - superset: postgres, redis, trino
  - superset-worker: redis, superset
  - vault-init: vault
  - vault-setup: vault

### 3.13 File: docs/_generate_doc_detail.py
- Loai: .py
- Service suy luan: N/A
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (7):
  - ast
  - from __future__ import annotations
  - from collections import defaultdict
  - from pathlib import Path
  - from typing import Any
  - os
  - re
- Internal imports (0):
- Functions top-level (11):
  - rel (line 26) args: [p]
  - discover_files (line 30) args: []
  - parse_compose_dependency_map (line 44) args: [compose_file]
  - infer_service_for_file (line 86) args: [path]
  - extract_env_vars (line 97) args: [text, is_python]
  - summarize_yaml (line 106) args: [text]
  - summarize_xml (line 118) args: [text]
  - summarize_python (line 131) args: [path, text]
  - dependency_notes (line 207) args: [path, dep_map, text]
  - write_doc (line 229) args: [files, dep_map]
  - main (line 340) args: []
- Classes (0):

### 3.14 File: infra/airflow/config/webserver_config.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: keycloak
- Imports (4):
  - from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride
  - from flask_appbuilder.security.manager import AUTH_OAUTH
  - logging
  - os
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class KeycloakSecurityManager (line 51)
    - method oauth_user_info (line 57) args: [self, provider, response]

### 3.15 File: infra/airflow/dags/_spark_common.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: AWS_DEFAULT_REGION, AWS_REGION, MINIO_ENDPOINT, MINIO_ROOT_PASSWORD, MINIO_ROOT_USER, S3_ENDPOINT, SPARK_HOME, SPARK_JARS_DIR, SPARK_JOB_BASE, SPARK_UTILS_PATH
- Dependency map:
  - Service name references in file: hive-metastore, schema-registry, spark-master
- Imports (4):
  - from __future__ import annotations
  - from airflow.datasets import Dataset
  - from typing import Iterable
  - os
- Internal imports (0):
- Functions top-level (8):
  - spark_packages (line 71) args: []
  - spark_base_conf (line 77) args: []
  - spark_env_vars (line 83) args: []
  - spark_job_base (line 99) args: []
  - spark_utils_py_files (line 105) args: []
  - iceberg_dataset (line 112) args: [table]
  - iceberg_maintenance (line 119) args: [table, expire_days]
  - maintenance_tasks_for (line 141) args: [dag, upstream_task, tables, expire_days]
- Classes (0):

### 3.16 File: infra/airflow/dags/bronze_events_kafka_stream_dag.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: ingestion
- Imports (7):
  - from _spark_common import iceberg_dataset, iceberg_maintenance, spark_base_conf, spark_env_vars, spark_job_base, spark_packages, spark_utils_py_files
  - from airflow import DAG
  - from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
  - from airflow.providers.standard.operators.python import PythonOperator
  - from datetime import datetime
  - from typing import Any
  - os
- Internal imports (0):
- Functions top-level (2):
  - build_default_params (line 112) args: [streams]
  - create_stream_tasks (line 141) args: [stream_key, stream_config, dag]
- Classes (0):

### 3.17 File: infra/airflow/dags/dag_sync_manager.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (5):
  - from airflow import DAG
  - from airflow.operators.python import PythonOperator
  - from airflow.providers.amazon.aws.hooks.s3 import S3Hook
  - from datetime import datetime
  - os
- Internal imports (0):
- Functions top-level (1):
  - sync_from_s3 (line 7) args: []
- Classes (0):

### 3.18 File: infra/airflow/dags/dbt_orchestration_dag_v1.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from airflow.sdk import dag
  - from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig
  - from cosmos.profiles import SparkThriftProfileMapping
  - os
- Internal imports (0):
- Functions top-level (1):
  - dbt_full_project_orchestration (line 40) args: []
- Classes (0):

### 3.19 File: infra/airflow/dags/silver_retail_star_schema_dag.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (6):
  - from _spark_common import iceberg_dataset, iceberg_maintenance, spark_base_conf, spark_env_vars, spark_job_base, spark_packages, spark_utils_py_files
  - from airflow import DAG
  - from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
  - from silver import TABLE_BUILDERS, TableBuilder
  - from typing import Dict
  - os
- Internal imports (0):
- Functions top-level (1):
  - create_silver_task (line 46) args: [builder, dag]
- Classes (0):

### 3.20 File: infra/airflow/processing/spark/jobs/bronze_cdc_stream.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: ingestion, schema-registry
- Imports (7):
  - argparse
  - from pathlib import Path
  - from pyspark.sql import DataFrame, SparkSession, functions, types
  - from spark_utils import build_spark, decode_confluent_avro, ensure_iceberg_table, ensure_schema, payload_size_expr, schema_id_expr, warn_if_checkpoint_exists
  - logging
  - sys
  - time
- Internal imports (0):
- Functions top-level (4):
  - build_stream (line 32) args: [spark]
  - write_stream (line 81) args: [df]
  - parse_args (line 108) args: []
  - main (line 118) args: []
- Classes (0):

### 3.21 File: infra/airflow/processing/spark/jobs/bronze_events_kafka_stream.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: ingestion, schema-registry
- Imports (8):
  - argparse
  - from pathlib import Path
  - from pyspark.sql import DataFrame, SparkSession, functions, types
  - from pyspark.sql.streaming import StreamingQueryListener
  - from spark_utils import build_spark, decode_confluent_avro, ensure_iceberg_table, ensure_schema, payload_size_expr, schema_id_expr, warn_if_checkpoint_exists
  - json
  - logging
  - sys
- Internal imports (0):
- Functions top-level (4):
  - build_stream (line 29) args: [spark]
  - write_events (line 80) args: [df]
  - parse_args (line 114) args: []
  - main (line 124) args: []
- Classes (1):
  - class _ProgressListener (line 94)
    - method onQueryStarted (line 95) args: [self, event]
    - method onQueryProgress (line 98) args: [self, event]
    - method onQueryTerminated (line 110) args: [self, event]

### 3.22 File: infra/airflow/processing/spark/jobs/silver/__init__.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (1):
  - from silver.registry import BUILDER_MAP, TABLE_BUILDERS, TableBuilder
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.23 File: infra/airflow/processing/spark/jobs/silver/builders/__init__.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (8):
  - from silver.builders.dim_customer_profile import build_dim_customer_profile
  - from silver.builders.dim_date import build_dim_date
  - from silver.builders.dim_product_catalog import build_dim_product_catalog
  - from silver.builders.dim_supplier import build_dim_supplier
  - from silver.builders.dim_warehouse import build_dim_warehouse
  - from silver.builders.fact_customer_engagement import build_fact_customer_engagement
  - from silver.builders.fact_inventory_position import build_fact_inventory_position
  - from silver.builders.fact_order_service import build_fact_order_service
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.24 File: infra/airflow/processing/spark/jobs/silver/builders/dim_customer_profile.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from __future__ import annotations
  - from pyspark.sql import DataFrame, SparkSession, functions
  - from pyspark.sql.window import Window
  - from silver.common import parse_cdc_table, scd2_from_events, surrogate_key, unix_ms_to_ts
- Internal imports (0):
- Functions top-level (1):
  - build_dim_customer_profile (line 11) args: [spark, _]
- Classes (0):

### 3.25 File: infra/airflow/processing/spark/jobs/silver/builders/dim_date.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from __future__ import annotations
  - from pyspark.sql import DataFrame, SparkSession, functions
  - from pyspark.sql.types import DateType
  - from silver.common import surrogate_key
- Internal imports (0):
- Functions top-level (1):
  - build_dim_date (line 11) args: [spark, _]
- Classes (0):

### 3.26 File: infra/airflow/processing/spark/jobs/silver/builders/dim_product_catalog.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from __future__ import annotations
  - from pyspark.sql import DataFrame, SparkSession, functions
  - from pyspark.sql.window import Window
  - from silver.common import parse_cdc_table, scd2_from_events, surrogate_key, unix_ms_to_ts
- Internal imports (0):
- Functions top-level (1):
  - build_dim_product_catalog (line 11) args: [spark, _]
- Classes (0):

### 3.27 File: infra/airflow/processing/spark/jobs/silver/builders/dim_supplier.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from __future__ import annotations
  - from pyspark.sql import DataFrame, SparkSession, functions
  - from pyspark.sql.window import Window
  - from silver.common import parse_cdc_table, scd2_from_events, surrogate_key, unix_ms_to_ts
- Internal imports (0):
- Functions top-level (1):
  - build_dim_supplier (line 11) args: [spark, _]
- Classes (0):

### 3.28 File: infra/airflow/processing/spark/jobs/silver/builders/dim_warehouse.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from __future__ import annotations
  - from pyspark.sql import DataFrame, SparkSession, functions
  - from pyspark.sql.window import Window
  - from silver.common import parse_cdc_table, scd2_from_events, surrogate_key, unix_ms_to_ts
- Internal imports (0):
- Functions top-level (1):
  - build_dim_warehouse (line 11) args: [spark, _]
- Classes (0):

### 3.29 File: infra/airflow/processing/spark/jobs/silver/builders/fact_customer_engagement.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (3):
  - from __future__ import annotations
  - from pyspark.sql import DataFrame, SparkSession, functions
  - from silver.common import parse_bronze_topic, surrogate_key
- Internal imports (0):
- Functions top-level (1):
  - build_fact_customer_engagement (line 10) args: [spark, raw_events]
- Classes (0):

### 3.30 File: infra/airflow/processing/spark/jobs/silver/builders/fact_inventory_position.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (3):
  - from __future__ import annotations
  - from pyspark.sql import DataFrame, SparkSession, functions
  - from silver.common import parse_bronze_topic, surrogate_key
- Internal imports (0):
- Functions top-level (1):
  - build_fact_inventory_position (line 10) args: [spark, raw_events]
- Classes (0):

### 3.31 File: infra/airflow/processing/spark/jobs/silver/builders/fact_order_service.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from __future__ import annotations
  - from pyspark.sql import DataFrame, SparkSession, functions
  - from pyspark.sql.window import Window
  - from silver.common import parse_bronze_topic, surrogate_key
- Internal imports (0):
- Functions top-level (1):
  - build_fact_order_service (line 11) args: [spark, raw_events]
- Classes (0):

### 3.32 File: infra/airflow/processing/spark/jobs/silver/common.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from __future__ import annotations
  - from pyspark.sql import DataFrame, SparkSession, functions, types
  - from pyspark.sql.column import Column
  - from pyspark.sql.window import Window
- Internal imports (0):
- Functions top-level (6):
  - with_payload (line 10) args: [df]
  - parse_bronze_topic (line 26) args: [raw_events, topic]
  - parse_cdc_table (line 31) args: [spark, table]
  - unix_ms_to_ts (line 36) args: [col]
  - scd2_from_events (line 42) args: [events, key_cols, ordering_cols, state_cols]
  - surrogate_key (line 69) args: []
- Classes (0):

### 3.33 File: infra/airflow/processing/spark/jobs/silver/registry.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (5):
  - from __future__ import annotations
  - from dataclasses import dataclass
  - from pyspark.sql import DataFrame, SparkSession
  - from silver.builders import build_dim_customer_profile, build_dim_date, build_dim_product_catalog, build_dim_supplier, build_dim_warehouse, build_fact_customer_engagement, build_fact_inventory_position, build_fact_order_service
  - from typing import Callable, Sequence
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class TableBuilder (line 23)
    - (khong co method)

### 3.34 File: infra/airflow/processing/spark/jobs/silver_retail_service.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (6):
  - argparse
  - from pyspark.sql import DataFrame, SparkSession, functions
  - from silver import BUILDER_MAP, TableBuilder
  - from spark_utils import build_spark, ensure_schema
  - from typing import Iterable, Sequence
  - logging
- Internal imports (0):
- Functions top-level (6):
  - write_snapshot (line 19) args: [df, builder]
  - enforce_primary_key (line 29) args: [df, keys, table_name]
  - materialise_tables (line 42) args: [spark, builders, raw_events]
  - parse_args (line 66) args: []
  - resolve_selection (line 76) args: [selection]
  - main (line 87) args: []
- Classes (0):

### 3.35 File: infra/airflow/processing/spark/jobs/spark_utils.py
- Loai: .py
- Service suy luan: airflow
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: ingestion
- Imports (8):
  - datetime
  - decimal
  - from __future__ import annotations
  - from pyspark.sql import Column, SparkSession, functions
  - from typing import Dict, Optional
  - io
  - json
  - logging
- Internal imports (0):
- Functions top-level (8):
  - build_spark (line 18) args: [app_name]
  - _json_default (line 36) args: [obj]
  - decode_confluent_avro (line 46) args: [value, schema_registry_url]
  - schema_id_expr (line 67) args: [col]
  - payload_size_expr (line 76) args: [col]
  - ensure_schema (line 82) args: [spark, schema_name]
  - ensure_iceberg_table (line 116) args: [spark, table, columns_sql]
  - warn_if_checkpoint_exists (line 151) args: [spark, checkpoint]
- Classes (0):

### 3.36 File: infra/alertmanager/config/alertmanager-stage.yml
- Loai: .yml
- Service suy luan: alertmanager
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (2):
  - route
  - receivers

### 3.37 File: infra/clickhouse/config.xml
- Loai: .xml
- Service suy luan: clickhouse
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: clickhouse-01, clickhouse-02
- XML tags quan trong (30):
  - <clickhouse>
  - <logger>
  - <level>
  - <console>
  - <log>
  - <errorlog>
  - <http_port>
  - <tcp_port>
  - <interserver_http_port>
  - <interserver_http_host>
  - <listen_host>
  - <max_connections>
  - <keep_alive_timeout>
  - <max_concurrent_queries>
  - <uncompressed_cache_size>
  - <mark_cache_size>
  - <path>
  - <tmp_path>
  - <user_files_path>
  - <format_schema_path>
  - <user_directories>
  - <users_xml>
  - <default_profile>
  - <default_database>
  - <timezone>
  - <mlock_executable>
  - <zookeeper>
  - <node>
  - <host>
  - <port>

### 3.38 File: infra/clickhouse/keeper/keeper_config.xml
- Loai: .xml
- Service suy luan: clickhouse
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- XML tags quan trong (21):
  - <clickhouse>
  - <logger>
  - <level>
  - <console>
  - <log>
  - <errorlog>
  - <listen_host>
  - <keeper_server>
  - <tcp_port>
  - <server_id>
  - <log_storage_path>
  - <snapshot_storage_path>
  - <coordination_settings>
  - <operation_timeout_ms>
  - <session_timeout_ms>
  - <raft_logs_level>
  - <raft_configuration>
  - <server>
  - <id>
  - <hostname>
  - <port>

### 3.39 File: infra/clickhouse/users.xml
- Loai: .xml
- Service suy luan: clickhouse
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- XML tags quan trong (22):
  - <clickhouse>
  - <profiles>
  - <default>
  - <max_memory_usage>
  - <use_uncompressed_cache>
  - <load_balancing>
  - <users>
  - <password>
  - <networks>
  - <ip>
  - <profile>
  - <quota>
  - <admin>
  - <access_management>
  - <quotas>
  - <interval>
  - <duration>
  - <queries>
  - <errors>
  - <result_rows>
  - <read_rows>
  - <execution_time>

### 3.40 File: infra/data-generator/__init__.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.41 File: infra/data-generator/adapters/__init__.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.42 File: infra/data-generator/adapters/kafka/__init__.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.43 File: infra/data-generator/adapters/kafka/factory.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (7):
  - from __future__ import annotations
  - from adapters.kafka.publisher import KafkaPublisher
  - from adapters.kafka.serializers import AvroSchemaEncoder
  - from config import Config
  - from confluent_kafka import SerializingProducer
  - from confluent_kafka.schema_registry import SchemaRegistryClient
  - from confluent_kafka.serialization import StringSerializer
- Internal imports (0):
- Functions top-level (1):
  - build_kafka (line 16) args: [config]
- Classes (0):

### 3.44 File: infra/data-generator/adapters/kafka/publisher.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from __future__ import annotations
  - from confluent_kafka import SerializingProducer
  - from ports.event_publisher import EventPublisher
  - from typing import Mapping, Optional
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class KafkaPublisher (line 14)
    - method __init__ (line 20) args: [self, producer]
    - method publish (line 23) args: [self, topic, key, value, headers]
    - method poll (line 43) args: [self]
    - method flush (line 46) args: [self, timeout]

### 3.45 File: infra/data-generator/adapters/kafka/serializers.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (5):
  - from __future__ import annotations
  - from confluent_kafka.schema_registry import SchemaRegistryClient
  - from confluent_kafka.serialization import SerializationContext, MessageField
  - from ports.schema_encoder import SchemaEncoder
  - from typing import Any
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class AvroSchemaEncoder (line 20)
    - method __init__ (line 23) args: [self, sr, subject, embedded_schema]
    - method encode (line 37) args: [self, topic, value]

### 3.46 File: infra/data-generator/adapters/kafka/topics.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (2):
  - from config import Config
  - from confluent_kafka.admin import AdminClient, NewTopic
- Internal imports (0):
- Functions top-level (1):
  - clear_kafka (line 10) args: [config]
- Classes (0):

### 3.47 File: infra/data-generator/adapters/minio/__init__.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (1):
  - from checkpoints import clear_checkpoints
- Internal imports (1):
  - from checkpoints import clear_checkpoints
- Functions top-level (0):
- Classes (0):

### 3.48 File: infra/data-generator/adapters/minio/checkpoints.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: AWS_REGION, MINIO_ENDPOINT, MINIO_ROOT_PASSWORD, MINIO_ROOT_USER, S3_ENDPOINT, S3_SECURE
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (7):
  - boto3
  - from __future__ import annotations
  - from botocore.config import Config
  - from botocore.exceptions import ClientError
  - from dataclasses import dataclass
  - from typing import Iterable
  - sys
- Internal imports (0):
- Functions top-level (3):
  - _parse_s3a_path (line 14) args: [path]
  - _build_client (line 44) args: [cfg]
  - clear_checkpoints (line 56) args: [paths]
- Classes (1):
  - class MinioConfig (line 25)
    - method from_env (line 33) args: [cls]

### 3.49 File: infra/data-generator/adapters/postgres/__init__.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.50 File: infra/data-generator/adapters/postgres/maintenance.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (1):
  - clear_postgres (line 3) args: [conn]
- Classes (0):

### 3.51 File: infra/data-generator/adapters/postgres/repositories.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (7):
  - from __future__ import annotations
  - from config import Config
  - from domain.enums import CATEGORIES, COUNTRIES, CUSTOMER_SEGMENTS
  - from ports.repositories import InventoryRepository, PricingRepository, ProductRepository
  - from typing import Iterable, Tuple
  - psycopg2
  - random
- Internal imports (0):
- Functions top-level (1):
  - pg_connect (line 17) args: [config]
- Classes (3):
  - class PgInventoryRepository (line 23)
    - method __init__ (line 24) args: [self, conn]
    - method read_qty_reserved (line 27) args: [self, warehouse_id, product_id]
    - method upsert_qty_reserved (line 36) args: [self, warehouse_id, product_id, qty, reserved]
    - method maybe_update_random_inventory (line 48) args: [self]
  - class PgPricingRepository (line 70)
    - method __init__ (line 71) args: [self, conn]
    - method maybe_update_random_price (line 74) args: [self]
  - class PgProductRepository (line 86)
    - method __init__ (line 87) args: [self, conn]
    - method preload_recent_products (line 90) args: [self, limit]

### 3.52 File: infra/data-generator/adapters/postgres/seed.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (6):
  - from __future__ import annotations
  - from config import Config
  - from domain.enums import CATEGORIES, COUNTRIES, CUSTOMER_SEGMENTS
  - from psycopg2.extras import execute_batch
  - from typing import Deque
  - random
- Internal imports (0):
- Functions top-level (1):
  - seed_postgres (line 16) args: [conn, config, recent_deques]
- Classes (0):

### 3.53 File: infra/data-generator/config.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: CANON_INVENTORY, CDC_TOPIC_CUSTOMER_SEGMENTS, CDC_TOPIC_INVENTORY, CDC_TOPIC_PRODUCTS, CDC_TOPIC_PRODUCT_SUPPLIERS, CDC_TOPIC_SUPPLIERS, CDC_TOPIC_USERS, CDC_TOPIC_WAREHOUSES, CDC_TOPIC_WAREHOUSE_INVENTORY, CHECKPOINT_PREFIXES, KAFKA_BOOTSTRAP, MAX_LATE_MINUTES, MIRROR_INVENTORY_TO_DB, PG_DSN, P_BAD_RECORD, P_LATE_EVENT, P_ORDER_HAS_PAYMENT, P_ORDER_HAS_SHIPMENT, P_UPDATE_INVENTORY, P_UPDATE_PRICE, SCHEMA_REGISTRY_URL, SEED_PRODUCTS, SEED_SUPPLIERS, SEED_USERS, SEED_WAREHOUSES, TARGET_EPS, TOPIC_CUSTOMER_INTERACTIONS, TOPIC_INVENTORY_CHANGES, TOPIC_ORDERS, TOPIC_PAYMENTS, TOPIC_SHIPMENTS, WEIGHT_INTERACTIONS, WEIGHT_INVENTORY_CHG, WEIGHT_ORDERS
- Dependency map:
  - Service name references in file: schema-registry
- Imports (3):
  - from __future__ import annotations
  - from dataclasses import dataclass
  - os
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class Config (line 25)
    - (khong co method)

### 3.54 File: infra/data-generator/domain/__init__.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.55 File: infra/data-generator/domain/enums.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.56 File: infra/data-generator/domain/policies.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (3):
  - from __future__ import annotations
  - from dataclasses import dataclass
  - random
- Internal imports (0):
- Functions top-level (0):
- Classes (2):
  - class FaultPolicy (line 12)
    - method apply (line 20) args: [self, obj]
  - class CanonicalInventory (line 37)
    - method is_postgres (line 42) args: [self]

### 3.57 File: infra/data-generator/main.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (18):
  - from __future__ import annotations
  - from adapters.kafka.factory import build_kafka
  - from adapters.kafka.topics import clear_kafka
  - from adapters.minio import clear_checkpoints
  - from adapters.postgres.maintenance import clear_postgres
  - from adapters.postgres.repositories import PgInventoryRepository, PgPricingRepository, PgProductRepository, pg_connect
  - from adapters.postgres.seed import seed_postgres
  - from config import Config
  - from confluent_kafka.schema_registry import SchemaRegistryClient
  - from services.common import HotCache
  - from services.interactions import InteractionService
  - from services.inventory import InventoryService
  - from services.orders import OrderService
  - from time import sleep
  - from util.rate_limit import TokenBucket
  - psycopg2
  - random
  - signal
- Internal imports (0):
- Functions top-level (3):
  - wait_for_pg (line 57) args: [dsn, max_wait_s]
  - wait_for_sr (line 72) args: [url, max_wait_s]
  - main (line 189) args: []
- Classes (1):
  - class App (line 87)
    - method __init__ (line 90) args: [self, cfg]
    - method _setup (line 95) args: [self]
    - method _loop (line 150) args: [self]
    - method _teardown (line 174) args: [self]
    - method run (line 181) args: [self]

### 3.58 File: infra/data-generator/ports/__init__.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.59 File: infra/data-generator/ports/event_publisher.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (1):
  - from typing import Mapping, Optional
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class EventPublisher (line 8)
    - method publish (line 14) args: [self, topic, key, value, headers]

### 3.60 File: infra/data-generator/ports/repositories.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (1):
  - from typing import Iterable, Optional, Tuple
- Internal imports (0):
- Functions top-level (0):
- Classes (3):
  - class InventoryRepository (line 8)
    - method read_qty_reserved (line 9) args: [self, warehouse_id, product_id]
    - method upsert_qty_reserved (line 12) args: [self, warehouse_id, product_id, qty, reserved]
    - method maybe_update_random_inventory (line 15) args: [self]
  - class PricingRepository (line 20)
    - method maybe_update_random_price (line 21) args: [self]
  - class ProductRepository (line 25)
    - method preload_recent_products (line 26) args: [self, limit]

### 3.61 File: infra/data-generator/ports/schema_encoder.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (1):
  - from typing import Any
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class SchemaEncoder (line 8)
    - method encode (line 11) args: [self, topic, value]

### 3.62 File: infra/data-generator/services/__init__.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.63 File: infra/data-generator/services/common.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (6):
  - from __future__ import annotations
  - from collections import deque
  - from datetime import datetime, timezone
  - from typing import Deque
  - random
  - string
- Internal imports (0):
- Functions top-level (6):
  - now_ms (line 14) args: []
  - rid (line 18) args: [prefix, n]
  - ensure_str (line 67) args: [v, fallback]
  - ensure_int (line 71) args: [v, fallback]
  - ensure_float (line 78) args: [v, fallback]
  - clamp_enum (line 85) args: [v, allowed, fallback]
- Classes (1):
  - class HotCache (line 22)
    - method __init__ (line 28) args: [self]
    - method pick_user (line 36) args: [self]
    - method get_or_create_session (line 43) args: [self, user_id]
    - method pick_product (line 55) args: [self]
    - method pick_warehouse (line 60) args: [self]
    - method pick_supplier (line 63) args: [self]

### 3.64 File: infra/data-generator/services/interactions.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (8):
  - from __future__ import annotations
  - from config import Config
  - from domain.enums import COUNTRIES, INTERACTION_TYPES, OS_LIST, BROWSERS
  - from domain.policies import FaultPolicy
  - from ports.event_publisher import EventPublisher
  - from ports.schema_encoder import SchemaEncoder
  - from services.common import HotCache, now_ms
  - random
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class InteractionService (line 17)
    - method __init__ (line 20) args: [self, cfg, cache, publisher, encoder]
    - method emit (line 33) args: [self]

### 3.65 File: infra/data-generator/services/inventory.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (10):
  - from __future__ import annotations
  - from config import Config
  - from domain.enums import INVENTORY_CHANGE_TYPES
  - from domain.policies import CanonicalInventory, FaultPolicy
  - from ports.event_publisher import EventPublisher
  - from ports.repositories import InventoryRepository
  - from ports.schema_encoder import SchemaEncoder
  - from services.common import HotCache, now_ms, rid, ensure_str, ensure_int
  - from typing import Tuple
  - random
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class InventoryService (line 19)
    - method __init__ (line 20) args: [self, cfg, cache, repo, publisher, encoder]
    - method _delta_reason_supplier (line 36) args: [self, change_type, prev]
    - method _apply_reserved_first (line 55) args: [self, delta, reserved]
    - method emit (line 62) args: [self]

### 3.66 File: infra/data-generator/services/orders.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (8):
  - from __future__ import annotations
  - from config import Config
  - from domain.enums import CARRIERS, CURRENCIES, PAYMENT_METHODS, PAYMENT_STATUS
  - from domain.policies import FaultPolicy
  - from ports.event_publisher import EventPublisher
  - from ports.schema_encoder import SchemaEncoder
  - from services.common import HotCache, now_ms, rid, ensure_str, ensure_float, ensure_int, clamp_enum
  - random
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class OrderService (line 25)
    - method __init__ (line 26) args: [self, cfg, cache, publisher, order_enc, payment_enc, shipment_enc]
    - method emit (line 43) args: [self]

### 3.67 File: infra/data-generator/util/__init__.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (0):
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.68 File: infra/data-generator/util/rate_limit.py
- Loai: .py
- Service suy luan: data-generator
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (4):
  - from __future__ import annotations
  - from time import monotonic
  - from typing import Callable
  - math
- Internal imports (0):
- Functions top-level (1):
  - diurnal_multiplier (line 12) args: []
- Classes (1):
  - class TokenBucket (line 20)
    - method __init__ (line 27) args: [self, rate, curve]
    - method refill (line 33) args: [self]
    - method try_consume (line 38) args: [self, n]

### 3.69 File: infra/datahub/ingestion/recipes/clickhouse.yml
- Loai: .yml
- Service suy luan: datahub
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: datahub-gms
- Top-level keys (2):
  - source
  - sink

### 3.70 File: infra/datahub/ingestion/recipes/grafana.yml
- Loai: .yml
- Service suy luan: datahub
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: datahub-gms
- Top-level keys (2):
  - source
  - sink

### 3.71 File: infra/datahub/ingestion/recipes/hive-metastore.yml
- Loai: .yml
- Service suy luan: datahub
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: datahub-gms
- Top-level keys (2):
  - source
  - sink

### 3.72 File: infra/datahub/ingestion/recipes/kafka_connectors.yml
- Loai: .yml
- Service suy luan: datahub
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: datahub-gms, debezium
- Top-level keys (2):
  - source
  - sink

### 3.73 File: infra/datahub/ingestion/recipes/kafka_topics.yml
- Loai: .yml
- Service suy luan: datahub
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: datahub-gms
- Top-level keys (2):
  - source
  - sink

### 3.74 File: infra/datahub/ingestion/recipes/minio.yml
- Loai: .yml
- Service suy luan: datahub
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: datahub-gms
- Top-level keys (2):
  - source
  - sink

### 3.75 File: infra/datahub/ingestion/recipes/postgres_ingestion.yml
- Loai: .yml
- Service suy luan: datahub
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: datahub-gms
- Top-level keys (2):
  - source
  - sink

### 3.76 File: infra/datahub/ingestion/recipes/superset.yml
- Loai: .yml
- Service suy luan: datahub
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: datahub-gms, superset
- Top-level keys (2):
  - source
  - sink

### 3.77 File: infra/datahub/ingestion/recipes/trino.yml
- Loai: .yml
- Service suy luan: datahub
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: datahub-gms, ranger-admin
- Top-level keys (2):
  - source
  - sink

### 3.78 File: infra/flink/flink-conf.yaml
- Loai: .yaml
- Service suy luan: flink
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: keycloak
- Top-level keys (30):
  - jobmanager.rpc.address
  - jobmanager.rpc.port
  - jobmanager.memory.process.size
  - taskmanager.memory.process.size
  - taskmanager.numberOfTaskSlots
  - parallelism.default
  - rest.port
  - rest.address
  - rest.bind-address
  - web.submit.enable
  - web.cancel.enable
  - web.upload.dir
  - security.context.factory.classes
  - rest.authentication.enabled
  - rest.authentication.type
  - security.oauth2.enabled
  - security.oauth2.client.id
  - security.oauth2.client.secret
  - security.oauth2.authorization.endpoint
  - security.oauth2.token.endpoint
  - security.oauth2.userinfo.endpoint
  - security.oauth2.jwks.endpoint
  - security.oauth2.issuer
  - security.oauth2.audience
  - security.oauth2.scope
  - web.session.timeout
  - state.backend
  - state.checkpoints.dir
  - state.savepoints.dir
  - high-availability

### 3.79 File: infra/grafana/config/provisioning/dashboards/dashboard.yml
- Loai: .yml
- Service suy luan: grafana
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (2):
  - apiVersion
  - providers

### 3.80 File: infra/grafana/config/provisioning/datasources/datasources.yml
- Loai: .yml
- Service suy luan: grafana
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (2):
  - apiVersion
  - datasources

### 3.81 File: infra/hive-metastore/config/core-site.xml
- Loai: .xml
- Service suy luan: hive-metastore
- Bien env phat hien: (khong co)
- Dependency map:
  - Compose service dependencies (hive-metastore): postgres
- XML tags quan trong (5):
  - <configuration>
  - <property>
  - <name>
  - <value>
  - <description>

### 3.82 File: infra/hive-metastore/config/hive-site.xml
- Loai: .xml
- Service suy luan: hive-metastore
- Bien env phat hien: (khong co)
- Dependency map:
  - Compose service dependencies (hive-metastore): postgres
- XML tags quan trong (5):
  - <configuration>
  - <property>
  - <name>
  - <value>
  - <description>

### 3.83 File: infra/hive-metastore/config/ranger-hive-audit.xml
- Loai: .xml
- Service suy luan: hive-metastore
- Bien env phat hien: (khong co)
- Dependency map:
  - Compose service dependencies (hive-metastore): postgres
- XML tags quan trong (4):
  - <configuration>
  - <property>
  - <name>
  - <value>

### 3.84 File: infra/hive-metastore/config/ranger-hive-security.xml
- Loai: .xml
- Service suy luan: hive-metastore
- Bien env phat hien: (khong co)
- Dependency map:
  - Compose service dependencies (hive-metastore): postgres
  - Service name references in file: ranger-admin
- XML tags quan trong (5):
  - <configuration>
  - <property>
  - <name>
  - <value>
  - <description>

### 3.85 File: infra/hive-metastore/config/ranger-policymgr-ssl.xml
- Loai: .xml
- Service suy luan: hive-metastore
- Bien env phat hien: (khong co)
- Dependency map:
  - Compose service dependencies (hive-metastore): postgres
- XML tags quan trong (5):
  - <configuration>
  - <property>
  - <name>
  - <value>
  - <description>

### 3.86 File: infra/jupyterlab/jupyter_lab_config.py
- Loai: .py
- Service suy luan: jupyterlab
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (1):
  - os
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.87 File: infra/loki/config/loki-config.yml
- Loai: .yml
- Service suy luan: loki
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (10):
  - auth_enabled
  - server
  - ingester
  - schema_config
  - storage_config
  - compactor
  - limits_config
  - chunk_store_config
  - table_manager
  - ruler

### 3.88 File: infra/openmetadata/ingestion/configs/dashboard/grafana_prod.yaml
- Loai: .yaml
- Service suy luan: openmetadata
- Bien env phat hien: GRAFANA_API_KEY, GRAFANA_HOST, GRAFANA_PORT, OPENMETADATA_AUTH_TYPE, OPENMETADATA_HOST, OPENMETADATA_JWT_TOKEN
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (3):
  - source
  - sink
  - workflowConfig

### 3.89 File: infra/openmetadata/ingestion/configs/dashboard/superset_prod.yaml
- Loai: .yaml
- Service suy luan: openmetadata
- Bien env phat hien: OPENMETADATA_AUTH_TYPE, OPENMETADATA_HOST, OPENMETADATA_JWT_TOKEN, SUPERSET_AUTH_PROVIDER, SUPERSET_HOST, SUPERSET_PASSWORD, SUPERSET_PORT, SUPERSET_USER
- Dependency map:
  - Service name references in file: superset
- Top-level keys (3):
  - source
  - sink
  - workflowConfig

### 3.90 File: infra/prometheus/config/alert-rules.yml
- Loai: .yml
- Service suy luan: prometheus
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (2):
  - groups
  - - name

### 3.91 File: infra/prometheus/config/prometheus.yml
- Loai: .yml
- Service suy luan: prometheus
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Top-level keys (4):
  - global
  - rule_files
  - alerting
  - scrape_configs

### 3.92 File: infra/ranger-admin/ranger-usersync/sync_users.py
- Loai: .py
- Service suy luan: ranger-admin
- Bien env phat hien: DB_HOST, DB_NAME, DB_PASS, DB_PORT, DB_USER, KEYCLOAK_ADMIN, KEYCLOAK_ADMIN_API_SECRET, KEYCLOAK_ADMIN_PASSWORD, KEYCLOAK_REALM, KEYCLOAK_URL, RANGER_ADMIN_PASS, RANGER_ADMIN_USER, RANGER_URL
- Dependency map:
  - Compose service dependencies (ranger-admin): postgres, hive-metastore
  - Service name references in file: keycloak
- Imports (4):
  - os
  - psycopg2
  - requests
  - time
- Internal imports (0):
- Functions top-level (11):
  - get_keycloak_token (line 21) args: []
  - get_keycloak_users (line 74) args: [token]
  - get_keycloak_groups (line 103) args: [token]
  - get_keycloak_roles (line 120) args: [token]
  - get_user_groups (line 137) args: [token, user_id]
  - create_ranger_group (line 154) args: [groupname, description]
  - create_ranger_role (line 203) args: [rolename, description]
  - add_user_to_group (line 253) args: [username, groupname]
  - create_ranger_user (line 307) args: [username, email]
  - sync_to_portal_users (line 390) args: []
  - main (line 465) args: []
- Classes (0):

### 3.93 File: infra/ranger-admin/trino_service_setup.py
- Loai: .py
- Service suy luan: ranger-admin
- Bien env phat hien: RANGER_ADMIN_PASS, RANGER_ADMIN_USER, RANGER_URL
- Dependency map:
  - Compose service dependencies (ranger-admin): postgres, hive-metastore
- Imports (5):
  - from apache_ranger.client.ranger_client import *
  - from apache_ranger.model.ranger_policy import *
  - from apache_ranger.model.ranger_service import *
  - json
  - os
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.94 File: infra/spark/core-site.xml
- Loai: .xml
- Service suy luan: spark
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- XML tags quan trong (5):
  - <configuration>
  - <property>
  - <name>
  - <value>
  - <description>

### 3.95 File: infra/spark/hive-site.xml
- Loai: .xml
- Service suy luan: spark
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: hive-metastore
- XML tags quan trong (5):
  - <configuration>
  - <property>
  - <name>
  - <value>
  - <description>

### 3.96 File: infra/spark/ranger-hive-audit.xml
- Loai: .xml
- Service suy luan: spark
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- XML tags quan trong (4):
  - <configuration>
  - <property>
  - <name>
  - <value>

### 3.97 File: infra/spark/ranger-hive-security.xml
- Loai: .xml
- Service suy luan: spark
- Bien env phat hien: (khong co)
- Dependency map:
  - Service name references in file: ranger-admin
- XML tags quan trong (5):
  - <configuration>
  - <property>
  - <name>
  - <value>
  - <description>

### 3.98 File: infra/spark/ranger-policymgr-ssl.xml
- Loai: .xml
- Service suy luan: spark
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- XML tags quan trong (5):
  - <configuration>
  - <property>
  - <name>
  - <value>
  - <description>

### 3.99 File: infra/superset/provisioning/databases.yaml
- Loai: .yaml
- Service suy luan: superset
- Bien env phat hien: (khong co)
- Dependency map:
  - Compose service dependencies (superset): postgres, redis, trino
  - Service name references in file: ranger-admin
- Top-level keys (1):
  - databases

### 3.100 File: infra/superset/superset_config.py
- Loai: .py
- Service suy luan: superset
- Bien env phat hien: POSTGRES_PASSWORD, POSTGRES_USER, SECRET_KEY, SUPERSET_SECRET_KEY
- Dependency map:
  - Compose service dependencies (superset): postgres, redis, trino
- Imports (2):
  - from cachelib.redis import RedisCache
  - os
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class CeleryConfig (line 21)
    - (khong co method)

### 3.101 File: infra/superset/superset_config_keycloak.py
- Loai: .py
- Service suy luan: superset
- Bien env phat hien: (khong co)
- Dependency map:
  - Compose service dependencies (superset): postgres, redis, trino
  - Service name references in file: keycloak
- Imports (4):
  - from flask_appbuilder.security.manager import AUTH_OAUTH
  - from superset.security import SupersetSecurityManager
  - logging
  - os
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class KeycloakSecurityManager (line 37)
    - method oauth_user_info (line 38) args: [self, provider, response]

### 3.102 File: test_http.py
- Loai: .py
- Service suy luan: N/A
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (2):
  - urllib.error
  - urllib.request
- Internal imports (0):
- Functions top-level (0):
- Classes (0):

### 3.103 File: test_redirect_trace.py
- Loai: .py
- Service suy luan: N/A
- Bien env phat hien: (khong co)
- Dependency map:
  - Khong tim thay dependency map ro rang trong compose cho file nay.
- Imports (2):
  - urllib.error
  - urllib.request
- Internal imports (0):
- Functions top-level (0):
- Classes (1):
  - class TraceRedirectHandler (line 4)
    - method redirect_request (line 5) args: [self, req, fp, code, msg, headers, newurl]

## 4. Ghi chu
- Tai lieu duoc sinh tu dong de dam bao coverage day du moi file Python/YAML/XML.
- Dependency map mang tinh suy luan tu docker-compose + tham chieu service name trong noi dung file.
