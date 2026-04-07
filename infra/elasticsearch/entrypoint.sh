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

echo "Elasticsearch initialization complete!"

# Keep container running by waiting for the background process
wait
