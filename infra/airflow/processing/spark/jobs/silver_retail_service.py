import argparse
import logging
from typing import Iterable, Sequence

from pyspark.sql import DataFrame, SparkSession, functions as F

from spark_utils import build_spark, ensure_schema
from silver import BUILDER_MAP, TableBuilder

# Runtime logger for this job
logger = logging.getLogger(__name__)


def write_snapshot(df: DataFrame, builder: TableBuilder) -> None:
    """
    Write a DataFrame to an Iceberg table in snapshot mode (create or replace).

    Each run fully replaces the target table with fresh data, which is the
    recommended approach for batch rebuilds of Silver layer tables.

    Args:
        df:      DataFrame to write.
        builder: TableBuilder containing the target table name and partition columns.
    """
    writer = df.writeTo(builder.table).using("iceberg")

    # Apply partitioning; partitioned tables scan fewer files on filtered queries
    for column in builder.partition_cols:
        writer = writer.partitionedBy(F.col(column))

    # Create if the table does not exist; replace all data if it does
    writer.createOrReplace()

    logger.info("Table written: %s", builder.table)


def enforce_primary_key(df: DataFrame, keys: Sequence[str], table_name: str) -> None:
    """
    Validate primary-key uniqueness before writing a table.

    Groups rows by the key columns and counts occurrences; any group with
    count > 1 indicates a duplicate key and causes the job to abort.

    Args:
        df:         DataFrame to validate.
        keys:       Column names that form the primary key.
        table_name: Table name used in log/error messages.

    Raises:
        ValueError: If duplicate primary keys are detected.
    """
    dup_count = (
        df.groupBy(*[F.col(key) for key in keys])
        .count()
        .where(F.col("count") > 1)
        .count()
    )

    if dup_count > 0:
        raise ValueError(f"Primary key violation in {table_name}: {dup_count} duplicates")


def materialise_tables(
    spark: SparkSession,
    builders: Iterable[TableBuilder],
    raw_events: DataFrame | None = None,
) -> None:
    """
    Build / refresh a list of Silver tables.

    For each table:
    1. Call builder.build_fn() to produce the DataFrame.
    2. Cache small dimensions so they can be reused within the same pipeline run.
    3. Validate primary-key constraints (if defined).
    4. Write the snapshot to Iceberg.
    5. Unpersist the cache after writing to relieve memory pressure.

    Args:
        spark:      Active SparkSession.
        builders:   TableBuilders selected by the CLI.
        raw_events: Optional raw-events DataFrame (required by fact tables and
                    event-driven dimensions).
    """
    # Ensure the silver schema exists before writing any tables
    ensure_schema(spark, "iceberg.silver")

    for builder in builders:
        logger.info("Building %s...", builder.identifier)

        # build_fn may read Bronze tables and/or raw_events depending on table logic
        df = builder.build_fn(spark, raw_events)

        # Cache small dimensions (except dim_customer_profile which can be large/SCD2)
        # to avoid redundant recomputations if the same data is referenced multiple times
        if "dim_" in builder.identifier and builder.identifier != "dim_customer_profile":
            df.cache()
            logger.info("Cached small dimension: %s", builder.identifier)

        # Validate PK uniqueness if the builder defines a primary key
        if builder.primary_key:
            enforce_primary_key(df, builder.primary_key, builder.identifier)

        write_snapshot(df, builder)

        # Release cached data to avoid memory pressure on the executor
        if df.is_cached:
            df.unpersist()
            logger.info("Unpersisted cache for: %s", builder.identifier)

        logger.info("Completed %s", builder.identifier)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Silver job."""
    parser = argparse.ArgumentParser(description="Build Silver dimensions and facts")
    parser.add_argument(
        "--tables",
        default="all",
        help="Comma-separated list of table identifiers to build (default: all)",
    )
    return parser.parse_args()


def resolve_selection(selection: str) -> set[str]:
    """
    Normalise the table selection from the CLI argument.

    Args:
        selection: "all" or a comma-separated list of table identifiers.

    Returns:
        Set of valid table identifiers to build.

    Raises:
        ValueError: If any requested identifier is not registered in BUILDER_MAP.
    """
    if selection.lower() == "all":
        return set(BUILDER_MAP)

    requested = {item.strip() for item in selection.split(",") if item.strip()}
    unknown = requested - set(BUILDER_MAP)
    if unknown:
        raise ValueError(f"Unknown table identifiers: {', '.join(sorted(unknown))}")
    return requested


def main() -> None:
    """Entry point for the Silver job."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args = parse_args()
    selected = resolve_selection(args.tables)

    if not selected:
        logger.info("No tables selected")
        return

    # App name shown in the Spark UI
    app_name = f"silver_retail:{':'.join(sorted(selected))}"
    logger.info("Starting %s with %d tables", app_name, len(selected))

    spark = build_spark(app_name=app_name)
    spark.sparkContext.setLogLevel("WARN")

    ensure_schema(spark, "iceberg.silver")

    try:
        selected_builders = [BUILDER_MAP[identifier] for identifier in selected]

        # Only load raw_events if at least one selected builder needs it
        requires_events = any(builder.requires_raw_events for builder in selected_builders)
        raw_events = spark.table("iceberg.bronze.raw_events") if requires_events else None

        materialise_tables(spark, selected_builders, raw_events)
        logger.info("Silver job completed successfully")
    except Exception as e:
        logger.error("Silver job failed: %s", str(e))
        raise
    finally:
        # Always stop the SparkSession to release cluster resources
        spark.stop()


if __name__ == "__main__":
    main()
