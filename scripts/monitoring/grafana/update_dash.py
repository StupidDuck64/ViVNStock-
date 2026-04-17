import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

def update_dashboard(filename):
    print(f"Updating {filename}")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        updated = False
        for panel in data.get('panels', []):
            title = panel.get('title', '').lower()
            if 'targets' not in panel:
                continue
            
            for target in panel['targets']:
                # Dashboard 1:
                if 'cpu throttling' in title:
                    target['expr'] = 'rate(container_cpu_cfs_throttled_seconds_total{name!=""}[5m])'
                    updated = True
                elif 'redis memory' in title:
                    target['expr'] = 'redis_memory_used_bytes'
                    updated = True
                elif 'redis connected clients' in title:
                    target['expr'] = 'redis_connected_clients'
                    updated = True
                elif 'minio free storage' in title:
                    target['expr'] = '(minio_node_disk_free_bytes / minio_node_disk_total_bytes) * 100'
                    updated = True
                
                # Dashboard 2:
                elif 'fastapi http 5xx' in title or 'fastapi 5xx' in title:
                    target['expr'] = 'sum by (method, endpoint) (rate(fastapi_responses_total{status=~"5.."}[5m]))'
                    updated = True
                elif 'fastapi response latency' in title or 'fastapi p95' in title:
                    target['expr'] = 'histogram_quantile(0.95, sum by (le, method, endpoint) (rate(fastapi_request_duration_seconds_bucket[5m])))'
                    updated = True
                elif 'kafka traffic' in title or 'kafka messages in' in title:
                    target['expr'] = 'sum by (topic) (rate(kafka_topic_partition_current_offset[5m]))'
                    updated = True
                elif 'spark consumer lag' in title or 'kafka consumer lag' in title:
                    target['expr'] = 'sum by (partition) (kafka_consumergroup_lag{consumergroup=~".*spark.*", topic="vnstock.ohlc.realtime"})'
                    updated = True

        if updated:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("Successfully updated")
        else:
            print("No matching panels found")
            
    except Exception as e:
        print(f"Failed to update {filename}: {e}")

update_dashboard(str(REPO_ROOT / "infra/grafana/config/dashboards/01_SRE_Data_Pipeline.json"))
update_dashboard(str(REPO_ROOT / "infra/grafana/config/dashboards/02_SRE_API_Storage.json"))
