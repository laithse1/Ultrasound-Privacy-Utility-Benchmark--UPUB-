"""Process queued local jobs once, useful for tests and Compose smoke checks."""

from us_privbench.storage.local import LocalArtifactStore
from us_privbench.worker.main import process_once


if __name__ == "__main__":
    print({"processed": process_once(LocalArtifactStore())})
