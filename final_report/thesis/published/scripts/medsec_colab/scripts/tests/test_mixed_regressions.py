"""Regression evidence for MIXED fixes. Synthetic fixtures are SOFTWARE TESTS ONLY."""
import csv
import hashlib
import json
from pathlib import Path
import nbformat
import numpy as np
import pytest
from PIL import Image
from scripts.chaos import roi_digest, initial_state, stream, quantize_states, rhs, system_jacobian
from scripts.cipher import encrypt, decrypt
from scripts.config import ode_parameters
from scripts.data import load_manifest, MIXEDDataset
from scripts.mixed_manifest import build_mixed_manifest


def test_full_digest_contract_and_short_digest_rejection(tiny_image_roi, stable_cfg):
    image, mask = tiny_image_roi
    digest, moments = roi_digest(image, mask)
    assert len(digest) == 64 and len(moments) == 4
    cipher, consumed = encrypt(image, mask, stable_cfg)
    assert consumed == digest
    np.testing.assert_array_equal(decrypt(cipher, consumed, stable_cfg), image)
    with pytest.raises(ValueError, match='64 hex'): initial_state(digest[0])
    with pytest.raises(ValueError, match='Empty ROI'): roi_digest(image, np.zeros_like(mask))
    with pytest.raises(ValueError, match='Constant ROI'): roi_digest(np.zeros_like(image), mask)


def test_quantization_formula_is_float64_pointwise_not_global_minmax(stable_cfg):
    values = np.array([[.000000011234567, -1.001, .999], [1.43256, 0., -2.]])
    expected = np.remainder(np.floor(np.abs(values)*stable_cfg['scale']), 256).astype(np.uint8)
    np.testing.assert_array_equal(quantize_states(values, stable_cfg['scale']), expected)
    first = stream('ab'*32, 20, stable_cfg)
    longer = stream('ab'*32, 50, stable_cfg)
    np.testing.assert_array_equal(first, longer[:20])
    assert first.dtype == np.uint8 and first.shape == (20, 5)


@pytest.mark.parametrize('variant,p', [(0, [2.,3.,4.,5.,6.,7.,8.]), (1,[2.,3.,4.,5.,.2]),
                                      (2,[40.,8.,40.,1.,-0.5,25.5,0.05])])
def test_all_system_jacobians_match_finite_difference(variant, p):
    s = np.array([.3,-.2,.5,.1,-.4]); p = np.array(p); delta = 1e-6
    fd = np.column_stack([(rhs(s+np.eye(5)[i]*delta,p,variant)-rhs(s-np.eye(5)[i]*delta,p,variant))/(2*delta) for i in range(5)])
    np.testing.assert_allclose(system_jacobian(s,p,variant), fd, atol=1e-7)


def test_no_silent_parameter_aliases_or_defaults(stable_cfg):
    cfg = {**stable_cfg, 'parameters': {**stable_cfg['parameters'], 'a': 40.}}
    with pytest.raises(ValueError, match='Ambiguous'): ode_parameters(cfg)
    cfg['parameters'] = {'gamma': 40.}
    with pytest.raises(ValueError): ode_parameters(cfg)


def _fundus_fixtures(tmp_path):
    chase = tmp_path/'chase'; stare = tmp_path/'stare'; chase.mkdir(); stare.mkdir()
    mask = np.zeros((32,48), np.uint8); mask[8:20,10:30] = 255
    for i in range(1,7):
        for eye in 'LR':
            image = np.random.default_rng(i*100+ord(eye)).integers(0,256,(32,48,3),dtype=np.uint8)
            Image.fromarray(image).save(chase/f'Image_{i:02d}{eye}.jpg')
            for observer in ('1stHO','2ndHO'): Image.fromarray(mask).save(chase/f'Image_{i:02d}{eye}_{observer}.png')
        image = np.random.default_rng(i).integers(0,256,(32,48,3),dtype=np.uint8)
        Image.fromarray(image).save(stare/f'im{i:04d}.ppm')
        for observer in ('ah','vk'): Image.fromarray(mask).save(stare/f'im{i:04d}.{observer}.ppm')
    return chase, stare


def test_stare_never_uses_masks_as_images_chase_eyes_stay_together(tmp_path):
    chase, stare = _fundus_fixtures(tmp_path); out = tmp_path/'mixed.jsonl'
    result = build_mixed_manifest(chase, stare, out)
    assert result['samples'] == 18 and result['subjects'] == 12
    rows = load_manifest(out)
    assert all('.ah.' not in r['image'] and '.vk.' not in r['image'] for r in rows)
    for patient in {r['patient_id'] for r in rows}:
        assert len({r['split'] for r in rows if r['patient_id'] == patient}) == 1
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    build_mixed_manifest(chase, stare, out)
    assert hashlib.sha256(out.read_bytes()).hexdigest() == digest
    loader = MIXEDDataset(out, size=32)
    assert all(r['split'] == 'train' for r in loader.records)
    assert len(loader) == result['split_counts']['train']
    with pytest.raises(FileExistsError): build_mixed_manifest(chase, stare, out, seed=88)


def test_legacy_eye_leakage_rejected_even_with_fake_distinct_group_ids(tmp_path):
    rows = [dict(id=f'eye{eye}',dataset='CHASE_STARE_Merged',patient_id=f'p{eye}',group_id=f'g{eye}',
                 split=split,image=f'Image_01{eye}.jpg',mask=f'm{eye}.png',source='SOFTWARE TEST ONLY',mask_definition='vessels')
            for eye, split in [('L','train'),('R','test')]]
    path = tmp_path/'legacy.jsonl'; path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with pytest.raises(ValueError, match='leakage'): load_manifest(path, verify_files=False)


def test_capacity_failure_keeps_cipher_metrics_and_differential_trials(trained_bundle):
    from scripts.experiments import run
    from scripts.reporting import make_report
    b = trained_bundle
    b['payload'].write_bytes(np.random.default_rng(2).integers(0,256,50000,dtype=np.uint8).tobytes())
    out = b['root']/'capacity_failure'
    status = run(b['manifest'], 'DRIVE', b['best_checkpoint'], b['config'], b['payload'], out)
    rows = [json.loads(line) for line in (out/'samples.jsonl').read_text().splitlines()]
    row = rows[0]
    assert status['successful_samples'] == 0 and status['successful_ciphers'] == 1
    assert row['stage'] == 'embedding' and row['cipher_status'] == 'ok'
    assert row['capacity']['required_bits'] > row['capacity']['available_bits']
    assert 'entropy' in row['security'] and 'recovery_quality' not in row
    assert row['message_exact'] is None
    assert status['differential_successful'] == b['config']['differential_trials']
    summary = make_report(out)
    assert summary['metrics']['security.entropy']['n'] == 1
    with (out/'reports/keys.csv').open(encoding='utf-8-sig') as f: keys = list(csv.DictReader(f))
    assert 'cipher_sensitivity.npcr' in keys[0]


def test_corrected_notebook_compiles_and_comparison_runs_unchanged():
    from scripts.build_mixed_notebook import notebook
    nb = nbformat.from_dict(notebook()); nbformat.validate(nb)
    for cell in nb.cells:
        if cell.cell_type == 'code':
            compile(cell.source, cell.id, 'exec')
            assert not cell.outputs and cell.execution_count is None
    root = Path(__file__).resolve().parents[2]
    for name, digest in [('MIXED(2).ipynb','e74a992a39df6c88808a8d392d623db3f3b82873f6f7ab48935292fcf363c066'),
                         ('MIXED(2) (1).ipynb','720bc4b4e4ad5473a508e5529229614bafa95be653f15d344a0bd54a0151b883')]:
        path = root/name
        if path.exists(): assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_interrupted_training_resume_matches_uninterrupted(tmp_path, stable_cfg, monkeypatch):
    """Interrupt AFTER saving epoch 2, resume with identical config, compare all weights."""
    import torch
    import scripts.training as training
    rows = []
    for i, split in enumerate(('train','train','train','val','test')):
        image = np.random.default_rng(i).integers(0,60,(32,32),dtype=np.uint8)
        mask = np.zeros((32,32), np.uint8); mask[8:24,8:24] = 255
        image[8:24,8:24] += 170
        ip, mp = tmp_path/f'i{i}.png', tmp_path/f'm{i}.png'
        Image.fromarray(image).save(ip); Image.fromarray(mask).save(mp)
        rows.append(dict(id=str(i),dataset='DRIVE',patient_id=str(i),group_id=f'retina:{i}',split=split,
                         image=str(ip),mask=str(mp),source='SOFTWARE TEST ONLY',mask_definition='toy ROI'))
    manifest = tmp_path/'manifest.jsonl'; manifest.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    cfg = {**stable_cfg, 'training': {**stable_cfg['training'], 'epochs': 4, 'patience': 8, 'base_channels': 2}}
    full, resumed = tmp_path/'full', tmp_path/'resumed'
    training.train(manifest, 'DRIVE', cfg, full)
    original_write = training.write_json
    def interrupted_write(path, value):
        original_write(path, value)
        if Path(path) == resumed/'history.json' and len(value) == 2:
            raise InterruptedError('SIMULATED SOFTWARE TEST interruption after checkpoint save')
    monkeypatch.setattr(training, 'write_json', interrupted_write)
    with pytest.raises(InterruptedError): training.train(manifest, 'DRIVE', cfg, resumed)
    monkeypatch.setattr(training, 'write_json', original_write)
    training.train(manifest, 'DRIVE', cfg, resumed, resume=True)
    a = torch.load(full/'last.pt', weights_only=True)
    b = torch.load(resumed/'last.pt', weights_only=True)
    assert a['history'] == b['history']
    for key in a['state_dict']:
        torch.testing.assert_close(a['state_dict'][key], b['state_dict'][key], rtol=0, atol=0)