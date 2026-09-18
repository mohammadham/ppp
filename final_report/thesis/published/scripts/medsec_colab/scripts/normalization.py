"""Universal dataset normalization layer for mixed-fundus datasets.
Solves: dimension mismatches (565×584, 700×605, 999×960), format mismatches
(.tif/.gif/.ppm/.png/.jpg), binary mask value differences (255 vs {0,1}),
and FOV mask dependency. All outputs standardized to (C, 512, 512).
"""
from pathlib import Path
import re
import numpy as np
from PIL import Image


def load_image_uint8(path: Path, mode: str = 'RGB') -> np.ndarray:
    """Load image via PIL, convert to target mode, return uint8 numpy array.
    
    Handles: .tif, .gif, .png, .jpg, .ppm, .bmp etc.
    OpenCV imread would return None for .gif; PIL handles all.
    """
    with Image.open(path) as im:
        if im.mode != mode:
            im = im.convert(mode)
        return np.array(im, dtype=np.uint8)


def normalize_mask(mask: np.ndarray) -> np.ndarray:
    """Binary-normalize mask to {0.0, 1.0} float32 range.
    
    Handles: 255-valued masks (DRIVE), {0,1} masks (other datasets),
    multi-channel RGB masks, P-mode (palette) masks.
    """
    if mask.ndim == 3:
        # If RGB, reduce to single channel
        if mask.shape[2] == 3:
            mask = np.any(mask != 0, axis=-1).astype(np.uint8)
        else:
            mask = np.max(mask, axis=-1).astype(np.uint8)
    # Binarize: any non-zero becomes 1
    mask = (mask > 0).astype(np.float32)
    return mask


def find_fov_mask(mask_dir: Path, patient_stem: str, target_size: tuple = (512, 512)) -> np.ndarray:
    """Find or generate FOV (field-of-view) circular mask.
    
    DRIVE uses *_training_mask.gif files. Other datasets may not have them.
    Falls back to all-ones tensor if file not found.
    """
    # Try DRIVE-style pattern first
    fov_candidates = list(mask_dir.glob(f"*{patient_stem}*training_mask*")) + \
                     list(mask_dir.glob(f"*{patient_stem}*mask*.gif")) + \
                     list(mask_dir.glob(f"*{patient_stem}*.gif"))
    
    if fov_candidates:
        fov_path = fov_candidates[0]
        try:
            with Image.open(fov_path) as im:
                if im.mode != 'L':
                    im = im.convert('L')
                fov_arr = np.array(im, dtype=np.float32)
                # Resize if needed using nearest-neighbor (mask)
                if fov_arr.shape != target_size:
                    fov_arr = np.array(Image.fromarray(fov_arr.astype(np.uint8)).resize(
                        target_size, Image.Resampling.NEAREST))
                # Binarize
                fov_arr = (fov_arr > 0).astype(np.float32)
                # Ensure correct shape
                if fov_arr.ndim == 2:
                    fov_arr = fov_arr[np.newaxis, ...]  # (1, H, W)
                return fov_arr
        except Exception:
            pass  # Fall through to fallback
    
    # Fallback: all-ones FOV mask (full image)
    return np.ones((1, *target_size), dtype=np.float32)


def extract_patient_stem(filename: str) -> str:
    """Extract patient/image stem from filename, working across naming conventions.
    
    Handles: Image_01L.jpg, im0001.ppm, stare_imXXXX, chase_Image_XXL etc.
    Uses pathlib stem removal + optional underscore stripping.
    """
    stem = Path(filename).stem  # removes extension
    # Remove common suffixes that are NOT patient IDs (mask suffixes, manual markers)
    stem = re.sub(r'(_manual1|_1stHO|_2ndHO|\.ah|\.vk|_mask)', '', stem, flags=re.IGNORECASE)
    return stem

def resolve_mask_path(img_path, candidate_masks):
    """Find the correct primary mask for an image from candidate list.
    
    Prioritizes 1stHO/manual1 masks, excludes 2ndHO to avoid duplicate pairing.
    """
    img_stem = extract_patient_stem(img_path)
    for m in candidate_masks:
        if img_stem == extract_patient_stem(m):
            if '2ndHO' not in str(m):
                return m
    return None


def load_sample_normalized(image_path: Path, mask_path: Path,
                           fov_dir: Path = None,
                           target_size: tuple = (512, 512)) -> dict:
    """Load and normalize a single image-mask pair to unified format.
    
    Returns dict with:
    - 'image': np.ndarray (3, 512, 512) float32 [0, 1]
    - 'mask': np.ndarray (1, 512, 512) float32 {0.0, 1.0}
    - 'fov_mask': np.ndarray (1, 512, 512) float32 {0.0, 1.0} (always ones if FOV absent)
    - 'original_shape': tuple (H, W) before resize
    - 'resized_shape': tuple (512, 512)
    """
    # --- Load image ---
    original_shape = None
    img_uint8 = load_image_uint8(image_path, mode='RGB')
    original_shape = img_uint8.shape[:2]  # (H, W)
    
    # Resize image to target (bilinear)
    img_pil = Image.fromarray(img_uint8)
    img_resized = np.array(img_pil.resize(target_size, Image.Resampling.BILINEAR), dtype=np.float32)
    # Normalize to [0, 1]
    img_norm = img_resized / 255.0
    # Transpose to (C, H, W) -> (3, 512, 512)
    img_tensor = np.transpose(img_norm, (2, 0, 1))
    
    # --- Load mask ---
    mask_uint8 = load_image_uint8(mask_path, mode='L')
    mask_norm = normalize_mask(mask_uint8)
    
    # Resize mask to target (nearest-neighbor to preserve binary edges)
    mask_pil = Image.fromarray((mask_norm * 255).astype(np.uint8))
    mask_resized = np.array(mask_pil.resize(target_size, Image.Resampling.NEAREST), dtype=np.float32)
    # Re-binarize after resize (floating point artifacts)
    mask_final = (mask_resized > 127.0).astype(np.float32)
    # Transpose to (C, H, W) -> (1, 512, 512)
    mask_tensor = mask_final[np.newaxis, ...] if mask_final.ndim == 2 else mask_final
    
    # --- FOV mask ---
    fov_mask = find_fov_mask(fov_dir, extract_patient_stem(image_path.name), target_size) if fov_dir else np.ones((1, *target_size), dtype=np.float32)
    
    return {
        'image': img_tensor,       # (3, 512, 512) float32 [0, 1]
        'mask': mask_tensor,       # (1, 512, 512) float32 {0.0, 1.0}
        'fov_mask': fov_mask,      # (1, 512, 512) float32 {0.0, 1.0}
        'original_shape': original_shape,
        'resized_shape': target_size,
    }