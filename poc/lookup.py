import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from poc.storage import get_metadata


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def main() -> None:
    parser = argparse.ArgumentParser(description="Look up a crawled URL in DynamoDB")
    parser.add_argument("--url", required=True, help="URL to look up")
    args = parser.parse_args()

    record = get_metadata(args.url)
    if record is None:
        print(f"No record found for: {args.url}")
        return

    print(json.dumps(record, indent=2, cls=_DecimalEncoder, default=str))


if __name__ == "__main__":
    main()