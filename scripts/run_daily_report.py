import argparse
import json

from app.workers.daily_jobs import run_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Run daily research report once.")
    parser.add_argument("--topic", default=None, help="Topic name from configs/topics.yaml")
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Generate report without sending email",
    )
    args = parser.parse_args()
    results = run_once(topic_name=args.topic, send_email=not args.no_email)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
