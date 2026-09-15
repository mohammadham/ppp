"""SOFTWARE TEST ONLY: native layout and explicit failure contracts."""
import json
import numpy as np
import pytest
from PIL import Image
from scripts.data import load_manifest, load_sample
from scripts.prepare import prepare
from scripts.stego import CapacityError
from scripts.transport import send

def test_zero_capacity_is_typed_failure_without_relaxing_roi(stable_cfg):
    image = np.arange(1024, dtype=np.uint8).reshape(32, 32)
    roi = np.ones_like(image, bool)
    original = image.copy()
    with pytest.raises(CapacityError) as error:
        send(image, roi, b'SOFTWARE TEST ONLY', stable_cfg, b'A'*32)
    assert error.value.details['error_code'] == 'NO_ELIGIBLE_PIXELS'
    assert error.value.details['available_bits'] == 0
    assert error.value.details['embedded_bits'] == 0
    assert error.value.details['roi_protection_relaxed'] is False
    np.testing.assert_array_equal(original, image)

@pytest.mark.parametrize('dataset,mask_folder,extension', [('DRIVE','1st_manual','.gif'), ('RITE','av','.png')])
def test_native_retinal_import_shared_group_and_mask(dataset, mask_folder, extension, tmp_path):
    for split, ident in [('training', '21'), ('training', '22'), ('test', '01')]:
        directory = tmp_path/dataset/split
        (directory/'images').mkdir(parents=True, exist_ok=True)
        (directory/mask_folder).mkdir(exist_ok=True)
        image = np.zeros((24, 32, 3), np.uint8)
        image[:,:,0] = int(ident)+np.arange(32, dtype=np.uint8)[None,:]
        Image.fromarray(image).save(directory/'images'/f'{ident}_{split}.tif')
        mask = np.zeros((24, 32, 3), np.uint8); mask[4:12, 6:16, 0] = 255
        Image.fromarray(mask).save(directory/mask_folder/f'{ident}_manual{extension}')
    output = tmp_path/f'{dataset}.jsonl'
    prepare(dataset, tmp_path/dataset, output, 'SOFTWARE TEST ONLY native fixtures')
    rows = load_manifest(output)
    assert {r['id']:r['split'] for r in rows} == {'01':'test','21':'val','22':'train'}
    assert all(r['group_id'] == 'retina:'+r['id'] for r in rows)
    image, mask, _ = load_sample(rows[0])
    assert image.shape == mask.shape == (24,32)
    assert mask.sum() == 80

def test_missing_files_and_cross_dataset_group_leakage(tmp_path):
    rows = [dict(id='01',dataset=ds,patient_id='01',group_id='retina:01',split=split,
                 image='missing.png',mask='missing_mask.png',source='SOFTWARE TEST ONLY',mask_definition='vessels')
            for ds,split in [('DRIVE','train'),('RITE','test')]]
    path = tmp_path/'manifest.jsonl'
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with pytest.raises(ValueError, match='leakage'): load_manifest(path, verify_files=False)
    with pytest.raises(FileNotFoundError): load_manifest(path)