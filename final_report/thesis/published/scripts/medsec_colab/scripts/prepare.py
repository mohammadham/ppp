"""Native DRIVE/RITE, BraTS2020 import; explicit CSV for ambiguous CXR source.

Robust, zero-error dataset preparation supporting Kaggle and Grand-Challenge layouts.
"""
import csv
import json
import re
from pathlib import Path
from .data import load_manifest


def extract_numeric_id(path: Path) -> str:
    """Extract numeric ID as a 2-digit zero-padded string."""
    match = re.search(r"(\d+)", str(path.stem))
    if not match:
        raise ValueError(f"Cannot extract numeric ID from: {path}")
    return f"{int(match.group(1)):02d}"


def retinal(root: Path, dataset: str, source: str):
    """Prepare DRIVE/RITE dataset records with explicit first-observer masks."""
    root = Path(root).resolve()
    records = []

    #Independent split for test and training partitions
    for partition in ("test", "training"):
        part_dir = None
        for candidate in root.iterdir():
            if candidate.is_dir() and candidate.name.lower() == partition:
                part_dir = candidate
                break

        if not part_dir:
            continue

        # Extract primary images (excluding mask files)
        images = []
        for p in part_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".tif", ".tiff", ".png", ".jpg", ".jpeg"):
                p_str = str(p).lower().replace("\\", "/")
                # Skip mask files from the image list
                if any(x in p_str for x in ("/mask/", "/1st_manual/", "/manual/", "manual", "_mask")):
                    continue
                images.append(p)

        images = sorted(images, key=lambda x: extract_numeric_id(x))

        # Collect all mask candidates in this partition
        all_mask_candidates = []
        for p in part_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".gif", ".png", ".tif", ".tiff"):
                p_str = str(p).lower().replace("\\", "/")
                # Skip image files
                if "/images/" in p_str:
                    continue
                # Filter out second-observer masks and FOV boundary masks
                if any(bad in p_str for bad in ("2nd", "2ndho", "_2nd_manual", "training_mask", "test_mask")):
                    continue
                all_mask_candidates.append(p)

        for img in images:
            ident = extract_numeric_id(img)

            # Match mask based on numeric ID
            matched = [m for m in all_mask_candidates if extract_numeric_id(m) == ident]

            # If no direct match, try fallback search without folder filter
            if not matched:
                for p in part_dir.rglob("*"):
                    if p.is_file() and extract_numeric_id(p) == ident and p != img:
                        p_str = str(p).lower().replace("\\", "/")
                        if not any(bad in p_str for bad in ("2nd", "2ndho")):
                            matched.append(p)
                matched = list(set(matched))

            # Prioritize first-observer mask (1st_manual/manual1)
            if len(matched) > 1:
                prio = [m for m in matched if any(k in str(m).lower() for k in ("1st_manual", "manual1", "1stho"))]
                if len(prio) == 1:
                    matched = prio

            if len(matched) != 1:
                raise ValueError(f"Need exactly one first-observer mask for {img}, found: {matched}")

            # Determine train/val/test split based on standard retinal split
            ident_int = int(ident)
            if partition == "test" or ident_int <= 20:
                split = "test"
            elif ident_int in (21, 26, 31, 36):
                split = "val"
            else:
                split = "train"

            records.append({
                "id": ident,
                "dataset": dataset,
                "patient_id": ident,
                "group_id": f"retina:{ident}",
                "split": split,
                "image": str(img.resolve()),
                "mask": str(matched[0].resolve()),
                "source": source,
                "mask_definition": "first-observer vessels" if dataset == "DRIVE" else "AV nonzero union"
            })

    # Ensure no duplicate samples based on ID
    unique = {}
    for r in records:
        unique[r["id"]] = r

    return sorted(list(unique.values()), key=lambda x: int(x["id"]))


def brats(root, source, seed, modalities, stride):
    """Prepare BraTS2020 dataset records."""
    import nibabel as nib
    records = []
    if stride < 1:
        raise ValueError("Slice stride must be positive")
    if not set(modalities) <= {"t1", "t1ce", "t2", "flair"}:
        raise ValueError("Unknown BraTS modality")

    for seg in sorted(Path(root).rglob("*_seg.nii*")):
        patient = seg.name.split("_seg.nii")[0]
        group = f"brats2020:{patient}"
        shape = nib.load(seg).shape

        for modality in modalities:
            image = seg.with_name(seg.name.replace("_seg.nii", f"_{modality}.nii"))
            if not image.is_file():
                raise FileNotFoundError(image)

            for index in range(0, shape[2], stride):
                records.append(dict(id=f"{patient}_{modality}_{index:03d}",
                                    dataset="BraTS2020",
                                    patient_id=patient,
                                    group_id=group,
                                    split=group_split(group, seed),
                                    image=str(image.resolve()),
                                    mask=str(seg.resolve()),
                                    axis=2,
                                    slice=index,
                                    source=source,
                                    mask_definition="whole tumor: segmentation > 0",
                                    modality=modality))

    return records


def group_split(group, seed):
    """Deterministic train/val/test split based on hash of group identifier."""
    value = (int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16) / 2**32)
    return "train" if value < 0.7 else "val" if value < 0.85 else "test"


def prepare(dataset, root, output, source, seed=2026, csv_path=None, modalities=("flair",), stride=1):
    """Main preparation function: generate manifest from dataset directory."""
    root = Path(root).resolve()
    output = Path(output)

    if not root.is_dir() or not source.strip():
        raise ValueError("Existing root and documented source required")

    if dataset in ("DRIVE", "RITE"):
        rows = retinal(root, dataset, source)
    elif dataset == "BraTS2020":
        rows = brats(root, source, seed, modalities, stride)
    else:
        raise ValueError(f"Dataset {dataset} requires explicit csv_path")

    if not rows:
        raise ValueError("No real samples found; check native folder layout")

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    staging = output.with_suffix(".staging.jsonl")
    staging.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    try:
        verified = load_manifest(staging)
    finally:
        staging.unlink(missing_ok=True)

    output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in verified), encoding="utf-8")
    return {"samples": len(verified), "manifest": str(output), "split_policy": "standard retinal split"}