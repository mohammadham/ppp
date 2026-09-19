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

def loss_function(logits, target, pos_w=1.0, neg_w=1.0):
    probability = logits.sigmoid(); axes = (1, 2, 3)
    dice = (2*(probability*target).sum(axes)+1)/(probability.sum(axes)+target.sum(axes)+1)
    dice_loss = (1.0 - dice).mean()
    # Vessel pixels are a tiny minority (~5% in DRIVE); an unweighted BCE is dominated
    # by the background class and pushes every probability below threshold, which makes
    # the hard mask empty and the Dice zero. Weight each pixel by the inverse class
    # frequency so the foreground signal is not drowned out.
    weight = pos_w * target + neg_w * (1.0 - target)
    bce_per_pixel = torch.nn.functional.binary_cross_entropy_with_logits(
        logits, target, reduction='none')
    bce = (bce_per_pixel * weight).sum() / weight.sum()  # weight-normalised mean BCE
    return bce + dice_loss

def train(manifest, dataset, cfg, output, device='cpu', resume=False):
    t = dict(cfg['training']); seed = int(cfg['seed'])
    t.setdefault('selection_metric', 'val_dice')
    if t['selection_metric'] not in ('val_dice', 'val_soft_dice'): raise ValueError('Unknown checkpoint selection metric')
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
        if checkpoint.get('seed') != seed: raise ValueError('Resume requires identical seed')
        if checkpoint.get('selection_metric') != t['selection_metric']:
            raise ValueError('Resume requires identical checkpoint selection policy; legacy weights require a new run')
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
    # Learn the foreground/background balance once from the TRAINING set only (never
    # validation/test) and derive inverse-frequency weights for the BCE term.
    pos_pixels, neg_pixels = 0, 0
    with torch.inference_mode():
        weight_loader = DataLoader(SegmentationDataset(partitions['train'], t['size']),
                                   batch_size=t['batch_size'], shuffle=False,
                                   generator=torch.Generator().manual_seed(seed))
        for image, target in weight_loader:
            sum_t = int(target.sum().item())
            pos_pixels += sum_t
            neg_pixels += int(target.numel() - sum_t)
    if pos_pixels <= 0:
        pos_pixels = neg_pixels or 1
    if neg_pixels <= 0:
        neg_pixels = pos_pixels
    pos_w = (pos_pixels + neg_pixels) / (2.0 * pos_pixels)
    neg_w = (pos_pixels + neg_pixels) / (2.0 * neg_pixels)
    print(f'class weights from training data: foreground={pos_w:.3f} background={neg_w:.3f}',
          flush=True)

    for epoch in range(start, t['epochs']):
        if stale >= t['patience']: break
        epoch_result = {'epoch': epoch+1}
        for phase in ('train', 'val'):
            net.train(phase == 'train'); losses, scores, softs = [], [], []
            for image, target in loaders[phase]:
                image, target = image.to(device), target.to(device)
                with torch.set_grad_enabled(phase == 'train'):
                    logits = net(image); loss = loss_function(logits, target, pos_w=pos_w, neg_w=neg_w)
                    if not torch.isfinite(loss): raise ValueError('Nonfinite training loss')
                    if phase == 'train':
                        optimizer.zero_grad(set_to_none=True); loss.backward(); optimizer.step()
                losses.extend([loss.item()]*len(image))
                prob = logits.detach().sigmoid()
                softs.extend(((2*(prob*target).sum((1, 2, 3)) + 1) /
                              (prob.sum((1, 2, 3)) + target.sum((1, 2, 3)) + 1)).cpu().tolist())
                for pred, truth in zip(prob.cpu().numpy(), target.cpu().numpy()):
                    scores.append(segmentation_scores(pred >= t['threshold'], truth > .5)['dice'])
            epoch_result[phase+'_loss'] = float(np.mean(losses))
            epoch_result[phase+'_dice'] = float(np.mean(scores))
            epoch_result[phase+'_soft_dice'] = float(np.mean(softs))
        # Selection follows the metric actually reported; validation loss breaks ties.
        selected_score = epoch_result[t['selection_metric']]
        improved = (selected_score > best or
                    (abs(selected_score - best) < 1e-9 and epoch_result['val_loss'] < best_loss))
        if improved:
            best_loss = epoch_result['val_loss']
        best = max(best, selected_score)
        stale = 0 if improved else stale + 1
        history.append(epoch_result)
        state = {'state_dict': net.state_dict(), 'optimizer': optimizer.state_dict(), 'training': t,
                 'dataset': dataset, 'manifest_sha256': manifest_hash, 'trained_epochs': epoch+1, 'best': best,
                 'data_fingerprint': data_fingerprint,
                 'best_val_loss': best_loss,
                 'selection_metric': t['selection_metric'],
                 'seed': seed,
                 'stale': stale, 'history': history, 'torch_rng': torch.get_rng_state(),
                 'cuda_rng': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
                 'seen_groups': sorted({r['group_id'] for s in partitions.values() for r in s}),
                 'seen_image_sha256': sorted({r['image_sha256'] for s in partitions.values() for r in s})}
        for name in (['last.pt', 'best.pt'] if improved else ['last.pt']):
            temporary = output/(name+'.tmp'); torch.save(state, temporary); temporary.replace(output/name)
        write_json(output/'history.json', history)
        print(epoch_result, flush=True)
    best_state = torch.load(output/'best.pt', map_location='cpu', weights_only=True)
    chosen = best_state['history'][-1]
    return {'best_checkpoint': str(output/'best.pt'), 'epochs': len(history),
            'selection_metric': t['selection_metric'], 'best_selection_score': best,
            'selected_epoch': best_state['trained_epochs'],
            'best_val_dice': chosen['val_dice'], 'selected_val_soft_dice': chosen['val_soft_dice']}