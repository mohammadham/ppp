"""Per-dataset binary segmentation; train/val only, group isolation, resumable."""
import random
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from .artifacts import environment, sha256_file, write_json
from .data import load_manifest, load_sample
from .model import UNet, segmentation_scores

class SegmentationDataset(Dataset):
    def __init__(self, records, size): self.records, self.size = records, size
    def __len__(self): return len(self.records)
    def __getitem__(self, index):
        a, m, _ = load_sample(self.records[index], self.size)
        return torch.from_numpy(a.astype(np.float32)/255)[None], torch.from_numpy(m.astype(np.float32))[None]

def loss_function(logits, target):
    probability = logits.sigmoid(); axes = (1, 2, 3)
    dice = (2*(probability*target).sum(axes)+1)/(probability.sum(axes)+target.sum(axes)+1)
    return torch.nn.functional.binary_cross_entropy_with_logits(logits, target) + (1-dice).mean()

def train(manifest, dataset, cfg, output, device='cpu', resume=False):
    t = dict(cfg['training']); seed = int(cfg['seed'])
    for field in ('epochs', 'batch_size', 'base_channels', 'patience'):
        if not isinstance(t[field], int) or t[field] < 1: raise ValueError(f'Invalid training {field}')
    if t['size'] < 16 or t['learning_rate'] <= 0 or not 0 < t['threshold'] < 1: raise ValueError('Invalid training settings')
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False; torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    records = [r for r in load_manifest(manifest) if r['dataset'] == dataset]
    partitions = {s: [r for r in records if r['split'] == s] for s in ('train', 'val')}
    if any(not rows for rows in partitions.values()): raise ValueError('Both nonempty train and val partitions required')
    output = Path(output)
    if output.exists() and any(output.iterdir()) and not resume: raise FileExistsError('Use a new directory or --resume')
    output.mkdir(parents=True, exist_ok=True)
    loaders = {s: DataLoader(SegmentationDataset(rows, t['size']), batch_size=t['batch_size'],
                            shuffle=s == 'train', num_workers=0) for s, rows in partitions.items()}
    net = UNet(t['base_channels']).to(device)
    optimizer = torch.optim.Adam(net.parameters(), lr=t['learning_rate'])
    best, best_loss, start, stale, history = -1., float('inf'), 0, 0, []
    manifest_hash = sha256_file(manifest)
    data_fingerprint = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    if resume:
        checkpoint = torch.load(output/'last.pt', map_location=device, weights_only=True)
        if checkpoint['manifest_sha256'] != manifest_hash or checkpoint['dataset'] != dataset or checkpoint['training'] != t:
            raise ValueError('Resume requires identical manifest, dataset and training configuration')
        if checkpoint.get('data_fingerprint') != data_fingerprint:
            raise ValueError('Resume requires identical source image/mask contents and record metadata')
        net.load_state_dict(checkpoint['state_dict']); optimizer.load_state_dict(checkpoint['optimizer'])
        best, start, stale, history = checkpoint['best'], checkpoint['trained_epochs'], checkpoint['stale'], checkpoint['history']
        best_loss = checkpoint.get('best_val_loss', float('inf'))
        torch.set_rng_state(checkpoint['torch_rng'].cpu())
        if torch.cuda.is_available() and checkpoint.get('cuda_rng'): torch.cuda.set_rng_state_all(checkpoint['cuda_rng'])
    write_json(output/'provenance.json', {'environment': environment(), 'config': cfg, 'manifest_sha256': manifest_hash,
                                        'data_fingerprint': data_fingerprint,
                                        'dataset': dataset, 'records': records, 'test_used_for_training': False})
    for epoch in range(start, t['epochs']):
        if stale >= t['patience']: break
        epoch_result = {'epoch': epoch+1}
        for phase in ('train', 'val'):
            net.train(phase == 'train'); losses, scores = [], []
            for image, target in loaders[phase]:
                image, target = image.to(device), target.to(device)
                with torch.set_grad_enabled(phase == 'train'):
                    logits = net(image); loss = loss_function(logits, target)
                    if not torch.isfinite(loss): raise ValueError('Nonfinite training loss')
                    if phase == 'train':
                        optimizer.zero_grad(set_to_none=True); loss.backward(); optimizer.step()
                losses.extend([loss.item()]*len(image))
                for pred, truth in zip(logits.detach().sigmoid().cpu().numpy(), target.cpu().numpy()):
                    scores.append(segmentation_scores(pred >= t['threshold'], truth > .5)['dice'])
            epoch_result[phase+'_loss'] = float(np.mean(losses)); epoch_result[phase+'_dice'] = float(np.mean(scores))
        # Dice is discrete: while all predictions stay below threshold, a falling
        # validation loss is meaningful progress, not a reason to keep epoch 1.
        improved = (epoch_result['val_dice'] > best or
                    (epoch_result['val_dice'] == best and epoch_result['val_loss'] < best_loss))
        if improved: best_loss = epoch_result['val_loss']
        best = max(best, epoch_result['val_dice']); stale = 0 if improved else stale+1
        history.append(epoch_result)
        state = {'state_dict': net.state_dict(), 'optimizer': optimizer.state_dict(), 'training': t,
                 'dataset': dataset, 'manifest_sha256': manifest_hash, 'trained_epochs': epoch+1, 'best': best,
                 'data_fingerprint': data_fingerprint,
                 'best_val_loss': best_loss,
                 'stale': stale, 'history': history, 'torch_rng': torch.get_rng_state(),
                 'cuda_rng': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
                 'seen_groups': sorted({r['group_id'] for s in partitions.values() for r in s}),
                 'seen_image_sha256': sorted({r['image_sha256'] for s in partitions.values() for r in s})}
        for name in (['last.pt', 'best.pt'] if improved else ['last.pt']):
            temporary = output/(name+'.tmp'); torch.save(state, temporary); temporary.replace(output/name)
        write_json(output/'history.json', history)
        print(epoch_result, flush=True)
    return {'best_checkpoint': str(output/'best.pt'), 'epochs': len(history), 'best_val_dice': best}