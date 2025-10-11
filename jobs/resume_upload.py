import sys
from jobs.indexer import load_jsonl, load_data_to_bq


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m jobs.resume_upload /path/to/enriched.jsonl")
        sys.exit(1)
    path = sys.argv[1]
    rows = load_jsonl(path)
    load_data_to_bq(rows, batch_size=50, max_retries=4)


if __name__ == "__main__":
    main()
