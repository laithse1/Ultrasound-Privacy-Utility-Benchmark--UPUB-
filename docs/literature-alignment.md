# Literature alignment

This review used the user-provided `ctoth/research-papers-plugin` workflow.
The installed launcher was incomplete, so the linked repository was cloned
temporarily and its retrieval scripts were run directly. MONAI, AAU-Net, and
the medical-image de-identification paper were downloaded with metadata and
PDFs into the gitignored `papers/` workspace.

## Papers and implications

| Work | What it establishes | Consequence for UPUB |
|---|---|---|
| Cardoso et al., 2022, MONAI | A healthcare-focused PyTorch framework with medical-image transforms, networks, and deployment utilities. | MONAI is an implementation foundation, not a novelty claim. Our contribution is the privacy–utility benchmark contract around it. |
| Chen et al., 2022, AAU-Net | Ultrasound lesion segmentation remains an active architecture problem; attention and multi-scale receptive fields improve segmentation research baselines. | UPUB should compare against stronger architectures later. The current compact U-Net is explicitly a reproducibility baseline. |
| Gómez-Flores et al., 2024, BUS-BRA | BUS-BRA provides 1,064 patients, lesion masks, pathology, BI-RADS, and evaluation metadata. | Cite the dataset paper and preserve patient-disjoint folds. Report rotating evaluation as development evidence, not a final external test. |
| Vallez et al., 2025, BUS-UCLM | 683 images from 38 patients with normal, benign, and malignant cases and expert masks. | Use as a small, patient-level external breast-ultrasound validation set; report wide uncertainty. |
| Gong et al., 2022, TN3K | 3,493 thyroid-nodule ultrasound images with pixel labels. | Use only as a separately labeled cross-anatomy domain-shift experiment. |
| Xian et al., 2018, BUSIS | Public breast-ultrasound segmentation benchmark with standardized evaluation motivation. | Optional reference dataset after access and partition audit. |
| De-Identification of Medical Imaging Data, 2024, arXiv:2410.12402 | Open-source de-identification can combine DICOM metadata handling with learned removal of text in image pixels. | Our explainable detector is a pre-OCR control. A meaningful future contribution is threat-modelled OCR/pixel evaluation, not claiming complete de-identification today. |

## Defensible contribution statement

The project should not claim a new segmentation architecture or a new
de-identification model. The defensible contribution is an executable,
local-first privacy–utility benchmark that:

1. creates controlled synthetic DICOM PHI with an answer key;
2. evaluates residual header/pixel PHI and downstream segmentation utility;
3. enforces patient-disjoint BUS-BRA manifests with provenance;
4. exposes the workflow through API/worker containers and an optional OHIF /
   Orthanc DICOMweb boundary; and
5. makes failure modes measurable before adding stronger AI.

## Required next comparisons

- Add the full AAU-Net reproduction under the same manifest and training
  budget. UPUB now includes a compact attention-gated U-Net comparator as an
  intermediate architecture baseline; it is not claimed to reproduce AAU-Net.
- Add OCR-based burned-in PHI detection and adversarial/negative controls.
- Add a locked external dataset or a clearly separated final BUS-BRA holdout.
- Report confidence intervals, calibration, subgroup/failure analysis, and
  reproducible seeds for every model comparison.

## Reference links

- [MONAI paper](https://arxiv.org/abs/2211.02701)
- [AAU-Net paper](https://arxiv.org/abs/2204.12077)
- [BUS-BRA dataset paper](https://doi.org/10.1002/mp.16812)
- [BUS-BRA dataset release](https://doi.org/10.5281/zenodo.8231412)
- [Medical image de-identification paper](https://arxiv.org/abs/2410.12402)
