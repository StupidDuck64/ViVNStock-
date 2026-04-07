#!/bin/sh
# POSIX sh: use -eu. 'pipefail' is not portable to /bin/sh in some images.
set -eu

RECIPE_DIR="/recipes"
LOG_DIR="/logs"

mkdir -p "$LOG_DIR"

echo "Starting datahub ingestion runner"

# Wait for DataHub GMS to be available (basic wait loop)
# honor DATAHUB_GMS_HOST and DATAHUB_GMS_PORT environment variables if set
GMS_HOST=${DATAHUB_GMS_HOST:-datahub-gms}
GMS_PORT=${DATAHUB_GMS_PORT:-8080}

max_attempts=60
sleep_seconds=5
attempt=1
while ! curl -sSf "http://${GMS_HOST}:${GMS_PORT}/health" >/dev/null 2>&1; do
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "DataHub GMS did not become healthy after $max_attempts attempts; proceeding anyway."
    break
  fi
  echo "Waiting for DataHub GMS to be ready (${attempt}/${max_attempts})..."
  attempt=$((attempt + 1))
  sleep "$sleep_seconds"
done

# Apply every recipe YAML in the recipes folder
applied_any=false
for f in "$RECIPE_DIR"/*.yml "$RECIPE_DIR"/*.yaml; do
  [ -f "$f" ] || continue
  applied_any=true
  name=$(basename "$f")
  logfile="$LOG_DIR/${name%.*}.log"
  echo "Applying recipe: $name"
  if command -v datahub >/dev/null 2>&1; then
    # Run ingestion and capture output
    datahub ingest -c "$f" 2>&1 | tee "$logfile" || echo "Ingestion failed for $name (see $logfile)"
  else
    echo "datahub CLI not found in image; cannot run ingestion for $name" | tee "$logfile"
  fi
done

if [ "$applied_any" = false ]; then
  echo "No recipes found in $RECIPE_DIR"
fi

# Keep container alive and surface logs
if ls "$LOG_DIR"/*.log >/dev/null 2>&1; then
  echo "Tailing logs in $LOG_DIR"
  tail -F "$LOG_DIR"/*.log
else
  echo "No logs to tail; sleeping indefinitely"
  sleep infinity
fi
