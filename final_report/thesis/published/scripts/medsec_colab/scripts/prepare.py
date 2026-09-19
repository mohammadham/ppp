"""Native DRIVE/RITE, BraTS2020 import; explicit CSV for ambiguous CXR source.

Robust zero-error matching for Kaggle & Grand-Challenge directory structures.
"""

import csv
import hashlib
import json
from pathlib import Path
import re
from .data import load_manifest


def group_split(group, seed):
  value = (
      int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16)
      / 2**32
  )
  return "train" if value < 0.7 else "val" if value < 0.85 else "test"


def extract_id(filename_or_stem: str) -> str:
  """Extract numeric ID as a 2-digit zero-padded string."""
  match = re.search(r"(\d+)", str(filename_or_stem))
  if not match:
    raise ValueError(f"Cannot infer numeric ID from: {filename_or_stem}")
  return f"{int(match.group(1)):02d}"


def find_drive_mask(all_files, ident, official_partition):
  """Find the single primary first-observer mask for a given retinal image ID."""
  candidates = []
  for p in all_files:
    if not p.is_file():
      continue

    # استخراج شناسه عددی فایل کاندید
    match = re.search(r"(\d+)", p.stem)
    if not match or f"{int(match.group(1)):02d}" != ident:
      continue

    p_str = str(p).lower().replace("\\", "/")

    # فیلتر کردن تصاویر اصلی، ماسک‌های ناظر دوم و ماسک‌های مرز دید (FOV)
    if "/images/" in p_str or "\\images\\" in p_str:
      continue
    if any(
        k in p_str
        for k in (
            "2nd",
            "2ndho",
            "_2nd_manual",
            "training_mask",
            "test_mask",
            "_mask.gif",
        )
    ):
      continue

    # شناسایی قطعی ناظر اول
    if any(
        k in p_str
        for k in ("1st_manual", "manual1", "1stho", "manual", "/mask/", "\\mask\\")
    ):
      candidates.append(p)

  # حذف موارد تکراری
  candidates = sorted(list(set(candidates)))

  # در صورتی که چندین ماسک یافت شد، اولویت با 1st_manual یا manual1 است
  if len(candidates) > 1:
    strict = [
        c
        for c in candidates
        if any(k in str(c).lower() for k in ("1st_manual", "manual1", "1stho"))
    ]
    if len(strict) == 1:
      candidates = strict

  if len(candidates) != 1:
    # اگر هنوز خالی است، جستجوی جامع‌تر بدون فیلتر فولدر
    fallback = [
        p
        for p in all_files
        if p.is_file()
        and re.search(r"(\d+)", p.stem)
        and f"{int(re.search(r'(\d+)', p.stem).group(1)):02d}" == ident
        and p.suffix.lower() in (".gif", ".png", ".tif")
        and not any(
            k in str(p).lower()
            for k in ("images", "2nd", "training_mask", "test_mask")
        )
    ]
    fallback = sorted(list(set(fallback)))
    if len(fallback) == 1:
      candidates = fallback

  return candidates


def retinal(root, dataset, source):
  records = []
  root = Path(root).resolve()

  # پویش تمام فایل‌ها در ریشه
  all_repo_files = list(root.rglob("*"))

  # یافتن تصاویر بر مبنای تقسیم‌بندی رسمی (training / test)
  for official in ("training", "test"):
    # جستجوی پوشه متناظر بدون حساسیت به حروف کوچک/بزرگ
    target_dirs = [
        d
        for d in root.rglob("*")
        if d.is_dir() and d.name.lower() == official.lower()
    ]
    if not target_dirs:
      target_dirs = [root]

    images = []
    for t_dir in target_dirs:
      img_dirs = [
          d
          for d in t_dir.rglob("*")
          if d.is_dir() and d.name.lower() in ("images", "image")
      ]
      if not img_dirs:
        img_dirs = [t_dir]
      for idir in img_dirs:
        for p in idir.glob("*"):
          if p.is_file() and p.suffix.lower() in (
              ".tif",
              ".tiff",
              ".png",
              ".jpg",
          ):
            # اطمینان از اینکه فایل ماسک نباشد
            if not any(
                k in str(p).lower() for k in ("manual", "mask", "2nd", "1st")
            ):
              images.append(p)

    images = sorted(list(set(images)))

    # تفکیک تصاویر متناظر با این بخش بر اساس نام یا شماره (در DRIVE ترین از ۲۱ تا ۴۰ و تست از ۰۱ تا ۲۰ است)
    partition_images = []
    for img in images:
      ident_int = int(re.search(r"(\d+)", img.stem).group(1))
      if official.lower() == "test" and (
          "test" in str(img).lower() or ident_int <= 20
      ):
        partition_images.append(img)
      elif official.lower() == "training" and (
          "training" in str(img).lower() or ident_int > 20
      ):
        partition_images.append(img)

    if not partition_images:
      partition_images = images

    for image in partition_images:
      ident = extract_id(image.stem)

      if dataset == "DRIVE":
        masks = find_drive_mask(all_repo_files, ident, official)
      else:
        masks = [
            p
            for p in all_repo_files
            if p.is_file()
            and extract_id(p.stem) == ident
            and "av" in str(p).lower()
        ]

      if len(masks) != 1:
        raise ValueError(
            f"Need exactly one first-observer/AV mask for {image}: {masks}"
        )

      # قانون استاندارد جداسازی داده‌های شبکیه (آزمون دست‌نخورده، ۴ نمونه ترین به عنوان ولیدیشن)
      ident_num = int(ident)
      split = (
          "test"
          if (official.lower() == "test" or ident_num <= 20)
          else "val"
          if ident_num in (21, 26, 31, 36)
          else "train"
      )

      records.append(
          dict(
              id=ident,
              dataset=dataset,
              patient_id=ident,
              group_id=f"retina:{ident}",
              split=split,
              image=str(image.resolve()),
              mask=str(masks[0].resolve()),
              source=source,
              mask_definition=(
                  "first-observer vessels"
                  if dataset == "DRIVE"
                  else "AV nonzero union"
              ),
          )
      )

  # حذف رکوردهای تکراری بر اساس شناسه
  unique_records = []
  seen_ids = set()
  for r in sorted(records, key=lambda x: int(x["id"])):
    if r["id"] not in seen_ids:
      seen_ids.add(r["id"])
      unique_records.append(r)

  return unique_records


def brats(root, source, seed, modalities, stride):
  import nibabel as nib

  records = []
  if stride < 1:
    raise ValueError("Slice stride must be positive")
  if not set(modalities) <= {"t1", "t1ce", "t2", "flair"}:
    raise ValueError("Unknown BraTS modality")
  for seg in sorted(root.rglob("*_seg.nii*")):
    patient = seg.name.split("_seg.nii")[0]
    group = f"brats2020:{patient}"
    shape = nib.load(seg).shape
    for modality in modalities:
      image = seg.with_name(seg.name.replace("_seg.nii", f"_{modality}.nii"))
      if not image.is_file():
        raise FileNotFoundError(image)
      for index in range(0, shape[2], stride):
        records.append(
            dict(
                id=f"{patient}_{modality}_{index:03d}",
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
                modality=modality,
            )
        )
  return records


def prepare(
    dataset,
    root,
    output,
    source,
    seed=2026,
    csv_path=None,
    modalities=("flair",),
    stride=1,
):
  root = Path(root).resolve()
  output = Path(output)
  if not root.is_dir() or not source.strip():
    raise ValueError("Existing root and documented source required")
  if dataset in ("DRIVE", "RITE"):
    rows = retinal(root, dataset, source)
  elif dataset == "BraTS2020":
    rows = brats(root, source, seed, modalities, stride)
  else:
    if not csv_path:
      raise ValueError(
          "CXR source is ambiguous: explicit CSV and masks required"
      )
    with open(csv_path, encoding="utf-8-sig") as f:
      rows = list(csv.DictReader(f))
    for r in rows:
      r["dataset"] = dataset
      r["source"] = source
      r["group_id"] = r.get("group_id") or f'cxr:{r["patient_id"]}'
      r["split"] = r.get("split") or group_split(r["group_id"], seed)
      for k in ("image", "mask"):
        r[k] = str((root / r[k]).resolve())

  if not rows:
    raise ValueError("No real samples found; check native folder layout")

  # بازنویسی قطعی مانیفست
  if output.exists():
    output.unlink()

  output.parent.mkdir(parents=True, exist_ok=True)
  staging = output.with_suffix(".staging.jsonl")
  staging.write_text(
      "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
      encoding="utf-8",
  )
  try:
    verified = load_manifest(staging)
  finally:
    staging.unlink(missing_ok=True)

  output.write_text(
      "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in verified),
      encoding="utf-8",
  )
  return {
      "samples": len(verified),
      "manifest": str(output),
      "split_policy": "documented implementation choice",
  }