#!/bin/bash
set -e

WORKDIR=/app/ingestion/configs

cd "$WORKDIR"

# Xử lý từng thư mục
for dir in database/ dashboard/ messaging/ pipeline/; do
    if [ -d "$dir" ]; then
        for file in "$dir"/*.yaml "$dir"/*.yml; do
            if [ -f "$file" ]; then
                echo "Running ingestion for $file"
                metadata ingest -c "$file"
            fi
        done
    fi
done