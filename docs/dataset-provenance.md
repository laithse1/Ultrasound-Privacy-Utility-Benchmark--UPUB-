# Dataset provenance and acquisition status

UPUB treats dataset acquisition as part of the scientific record. Every
manifest stores the source name, release/version string, local image and mask
paths, and split assignment. Downloaded archives are not committed to Git.

## Acquired

- **BUS-BRA**: local release already present under `data/external/busbra`, with
  the official CSV metadata and five-fold information used by
  `scripts/ingest_busbra.py`.
- **TN3K**: cloned from the authors' public Hugging Face dataset repository at
  `data/external/tn3k`. The official train/validation fold-0 JSON and the
  held-out test directories are preserved. Ingestion is reproducible with:

  ```powershell
  $env:PYTHONPATH='src'
  python scripts/ingest_tn3k.py data/external/tn3k --fold 0
  python scripts/audit_manifest.py artifacts/tn3k-manifest.json
  ```

TN3K filenames do not contain patient identifiers in the acquired release.
The manifest therefore uses a documented image-case proxy group. This is
appropriate for engineering validation of the loader and model, but does not
support a claim of patient-level independence inside the trainval partition.

## Acquired

- **Breast-Lesions-USG / BrEaST**: the TCIA package is now present under
  `data/external/BrEaST-Lesions_USG-images_and_masks-Dec-15-2023`. The
  manifest contains 252 masked cases, with 145 train, 55 validation, and 52
  test cases. Four unmasked rows were excluded from segmentation. The release
  uses `CaseID`, which is preserved as the patient-group key.

## Pending or blocked

- **BUS-UCLM**: the dataset citation and author repository are recorded, but
  the official Mendeley/S3 download endpoint did not provide an accessible
  archive in this environment. No BUS-UCLM results are reported as if the
  data had been acquired. The ingestion adapter remains ready for the
  extracted `images/` and `masks/` layout described by the authors.
- **BUSI**: candidate public mirrors are being evaluated separately from the
  canonical dataset release. The acquired `data/external/busi-whu-seg` mirror
  contains 927 images and paired masks in predefined train/validation/test
  directories. It is ingested as `BUSI-WHU-Seg-mirror`, not as canonical BUSI,
  and its filenames do not expose patient identifiers. Its bounded baseline is
  recorded separately in `artifacts/busi-whu-three-seed-summary.json`.

## Reproducibility rule

The paper distinguishes measured results from planned experiments. A dataset
is promoted into the primary benchmark only after its source, license,
checksum/provenance, manifest audit, and split policy are recorded.
