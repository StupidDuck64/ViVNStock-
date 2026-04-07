"""Silver layer package — modular table builder architecture.

Exposes the central registry so Spark jobs can import the builder list in one line.
"""

from silver.registry import BUILDER_MAP, TABLE_BUILDERS, TableBuilder

__all__ = ["TABLE_BUILDERS", "BUILDER_MAP", "TableBuilder"]
