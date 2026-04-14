#!/bin/bash
set -e

# Start Elasticsearch in the background
/usr/local/bin/docker-entrypoint.sh eswrapper &

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to start..."
until curl -s -o /dev/null -w "%{http_code}" http://localhost:9200 | grep -q "200"; do
    sleep 2
done
echo "Elasticsearch is ready!"

# Start trial license
echo "Starting trial license..."
curl -X POST "http://localhost:9200/_license/start_trial?acknowledge=true" || true

# Set cluster settings
echo "Setting cluster max shards..."
curl -X PUT "http://localhost:9200/_cluster/settings" \
    -H 'Content-Type: application/json' \
    -d '{
        "persistent": {
            "cluster.max_shards_per_node": 2000
        }
    }' || true

# ════════════════════════════════════════════════════════════════════════════
# ILM Policy — vivnstock-logs: hot 7d → delete
# ════════════════════════════════════════════════════════════════════════════
echo "Creating ILM policy: vivnstock-logs-policy..."
curl -X PUT "http://localhost:9200/_ilm/policy/vivnstock-logs-policy" \
    -H 'Content-Type: application/json' \
    -d '{
        "policy": {
            "phases": {
                "hot": {
                    "min_age": "0ms",
                    "actions": {
                        "rollover": {
                            "max_size": "5gb",
                            "max_age": "1d"
                        },
                        "set_priority": { "priority": 100 }
                    }
                },
                "warm": {
                    "min_age": "2d",
                    "actions": {
                        "forcemerge": { "max_num_segments": 1 },
                        "shrink": { "number_of_shards": 1 },
                        "set_priority": { "priority": 50 }
                    }
                },
                "delete": {
                    "min_age": "7d",
                    "actions": { "delete": {} }
                }
            }
        }
    }' || true

# ════════════════════════════════════════════════════════════════════════════
# Index Template — vivnstock-logs-* with optimized mappings
# ════════════════════════════════════════════════════════════════════════════
echo "Creating index template: vivnstock-logs..."
curl -X PUT "http://localhost:9200/_index_template/vivnstock-logs" \
    -H 'Content-Type: application/json' \
    -d '{
        "index_patterns": ["vivnstock-logs-*"],
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.lifecycle.name": "vivnstock-logs-policy",
                "index.lifecycle.rollover_alias": "vivnstock-logs"
            },
            "mappings": {
                "properties": {
                    "@timestamp": { "type": "date" },
                    "message": { "type": "text", "analyzer": "standard" },
                    "log_level": { "type": "keyword" },
                    "service": { "type": "keyword" },
                    "container_name": { "type": "keyword" },
                    "client_ip": { "type": "ip" },
                    "http_method": { "type": "keyword" },
                    "request_path": { "type": "keyword" },
                    "status_code": { "type": "integer" },
                    "status_class": { "type": "keyword" },
                    "response_time": { "type": "float" },
                    "symbol": { "type": "keyword" },
                    "batch_size": { "type": "integer" },
                    "kafka_partition": { "type": "integer" },
                    "java_class": { "type": "keyword" },
                    "airflow_module": { "type": "keyword" }
                },
                "runtime": {
                    "error_pct": {
                        "type": "double",
                        "script": {
                            "source": "if (doc['"'"'log_level'"'"'].size() > 0 && doc['"'"'log_level'"'"'].value == '"'"'ERROR'"'"') { emit(1.0); } else { emit(0.0); }"
                        }
                    }
                }
            }
        },
        "priority": 200
    }' || true

# ════════════════════════════════════════════════════════════════════════════
# Docker-logs ILM (same retention for fallback index)
# ════════════════════════════════════════════════════════════════════════════
echo "Creating ILM policy: docker-logs-policy..."
curl -X PUT "http://localhost:9200/_ilm/policy/docker-logs-policy" \
    -H 'Content-Type: application/json' \
    -d '{
        "policy": {
            "phases": {
                "hot": {
                    "actions": {
                        "set_priority": { "priority": 50 }
                    }
                },
                "delete": {
                    "min_age": "3d",
                    "actions": { "delete": {} }
                }
            }
        }
    }' || true

curl -X PUT "http://localhost:9200/_index_template/docker-logs" \
    -H 'Content-Type: application/json' \
    -d '{
        "index_patterns": ["docker-logs-*"],
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.lifecycle.name": "docker-logs-policy"
            }
        },
        "priority": 100
    }' || true

echo "Elasticsearch initialization complete!"

# Keep container running by waiting for the background process
wait
