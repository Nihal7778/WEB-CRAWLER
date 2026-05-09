import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from poc.queue_client import push_crawl_message


def load_urls(path: Path) -> list[str]:
    urls = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def main() -> None:
    urls_file = Path(__file__).resolve().parent / "urls.txt"
    urls = load_urls(urls_file)
    print(f"Loading {len(urls)} URLs into the crawl queue...")
    for url in urls:
        push_crawl_message(url)
        print(f"  + {url}")
    print(f"Done. {len(urls)} messages queued.")


if __name__ == "__main__":
    main()