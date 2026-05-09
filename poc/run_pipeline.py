import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from poc.queue_client import queue_depth
from poc.worker import run_worker

NUM_WORKERS = 5


def main() -> None:
    print(f"Crawl queue depth: {queue_depth()}")
    if queue_depth() == 0:
        print("Queue is empty. Run `python -m poc.ingester` first.")
        return

    stop_event = threading.Event()
    threads = []
    started = time.monotonic()

    for i in range(NUM_WORKERS):
        t = threading.Thread(target=run_worker, args=(i + 1, stop_event), daemon=True)
        t.start()
        threads.append(t)

    print(f"Started {NUM_WORKERS} workers")
    print("─" * 80)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\nInterrupt received, stopping workers...")
        stop_event.set()
        for t in threads:
            t.join(timeout=5)

    elapsed = time.monotonic() - started
    print("─" * 80)
    print(f"Pipeline complete in {elapsed:.1f}s")
    print(f"Remaining queue depth: {queue_depth()}")


if __name__ == "__main__":
    main()