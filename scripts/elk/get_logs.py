import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Export last N lines from a Docker container log")
    parser.add_argument("--container", default="lakehouse-oss-vuongngo-airflow-worker-1")
    parser.add_argument("--tail", type=int, default=250)
    parser.add_argument(
        "--output",
        default="logs/last_errors.log",
        help="Workspace-relative output file path",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_path = repo_root / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        output = subprocess.check_output(
            ["docker", "logs", "--tail", str(args.tail), args.container],
            stderr=subprocess.STDOUT,
        )
        out_path.write_text(output.decode("utf-8", errors="ignore"), encoding="utf-8")
        print(f"Saved log to {out_path}")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
