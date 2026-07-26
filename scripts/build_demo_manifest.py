import argparse
from pathlib import Path

from us_privbench.data.manifest import CaseRecord, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a patient-disjoint UPUB demo manifest")
    parser.add_argument("--output", type=Path, default=Path("artifacts/demo-manifest.json"))
    args = parser.parse_args()
    records = [
        CaseRecord("demo-train-001", "patient-001", "train", "synthetic://train/001", dataset_name="upub-demo", dataset_version="0.1"),
        CaseRecord("demo-train-002", "patient-002", "train", "synthetic://train/002", dataset_name="upub-demo", dataset_version="0.1"),
        CaseRecord("demo-val-001", "patient-003", "validation", "synthetic://validation/001", dataset_name="upub-demo", dataset_version="0.1"),
        CaseRecord("demo-test-001", "patient-004", "test", "synthetic://test/001", dataset_name="upub-demo", dataset_version="0.1"),
    ]
    write_manifest(records, args.output)
    print(f"wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
