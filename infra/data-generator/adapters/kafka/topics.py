from confluent_kafka.admin import AdminClient, NewTopic

from config import Config


def clear_kafka(config: Config) -> None:
    topics = [
        config.topic_orders,
        config.topic_payments,
        config.topic_shipments,
        config.topic_inventory_changes,
        config.topic_customer_interactions,
        config.cdc_topic_users,
        config.cdc_topic_products,
        config.cdc_topic_inventory,
        config.cdc_topic_warehouse_inventory,
        config.cdc_topic_suppliers,
        config.cdc_topic_customer_segments,
        config.cdc_topic_product_suppliers,
        config.cdc_topic_warehouses,
    ]
    topics = list(dict.fromkeys(topics))
    admin = AdminClient({"bootstrap.servers": config.bootstrap})
    print("🧹 Deleting Kafka topics...")
    futures = admin.delete_topics(topics, operation_timeout=10)
    for t, f in futures.items():
        try:
            f.result()
            print(f"  ✨ Deleted topic {t}")
        except Exception as e:
            print(f"  ⚠️ Delete failed for {t}: {e}")
    print("📝 Re-creating topics...")
    new_topics = [NewTopic(t, num_partitions=3, replication_factor=1) for t in topics]
    futures = admin.create_topics(new_topics)
    for t, f in futures.items():
        try:
            f.result()
            print(f"  ✅ Re-created topic {t}")
        except Exception as e:
            print(f"  ⚠️ Create failed for {t}: {e}")
