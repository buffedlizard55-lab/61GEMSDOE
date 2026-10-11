#!/usr/bin/env python3
"""LOQO for H61-O variable density"""
import sys, json, time
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from gems61 import buried as B, grid as gridmod, h61o as M, holdout_segmented as holdoutmod
import run_h61g as R
from gems61.network import segments
EVID=ROOT/'evidence'
CACHE=ROOT/'.cache/h61o'
SEEDS=R.SEEDS

def log(m): print(m, flush=True)

g=gridmod.load_grid()
grav=np.asarray(B.load_band(13), np.float64)
valid=g.footprint & np.isfinite(grav)
stack=np.load(CACHE/'stack.npy', mmap_mode='r')
names=json.loads((EVID/'h61o_features.json').read_text())['feature_names']
depth_fine=np.load(CACHE/'depth_fine.npy')

ctx=holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
seg_cache=segments(g.catalogue, max_len_px=12)[0]
quad=ctx.quad
dom_total=float(sum(c.active.sum() for c in ctx.cells if c.seed==ctx.cells[0].seed))

def emit_and_score(oof, cell, prune, budget, depth_fine):
    sl=cell.bbox
    vis=ctx.visible(cell.key)[sl]
    far=ndi.distance_transform_edt(~vis) > prune
    allowed=cell.active & far
    b_cell=int(round(budget*float(cell.active.sum())/dom_total))
    p=oof[cell.key][sl].astype(np.float64)
    dots=M.dot_thin(p, allowed, b_cell, tile_px=3)
    part, dp=R._score_crop(cell, dots)
    return part

rows=[]
for q,qname in enumerate(holdoutmod.FOLD_NAMES):
    outside=quad!=q
    hidden_here=np.zeros(g.shape, bool)
    for c in ctx.cells:
        if c.fold==q:
            hidden_here|=ctx.hidden_by_cell[c.key]
    train_pos=g.catalogue & outside & ~hidden_here
    model, rec=M.train_habitat(np.asarray(stack), valid, train_pos, names, seed=100+q)
    p=M.predict_habitat(model, np.asarray(stack), valid)
    oof={c.key: p.astype(np.float32) for c in ctx.cells if c.fold==q}
    del model,p
    parts=[]
    for cell in ctx.cells:
        if cell.fold!=q: continue
        part=emit_and_score(oof, cell, 3.0, 40000, depth_fine)
        parts.append(part)
    pooled=R._pool(parts)
    # canary
    rng=np.random.default_rng(5)
    py,px,ny,nx=[],[],[],[]
    for cell in ctx.cells:
        if cell.fold!=q: continue
        sl=cell.bbox
        yy,xx=cell.truth_yx
        py.append(yy+sl[0].start); px.append(xx+sl[1].start)
        act=np.argwhere(cell.active)
        pick=act[rng.choice(act.shape[0], size=min(20000, act.shape[0]), replace=False)]
        ny.append(pick[:,0]+sl[0].start); nx.append(pick[:,1]+sl[1].start)
    py=np.concatenate(py); px=np.concatenate(px)
    ny=np.concatenate(ny); nx=np.concatenate(nx)
    pm=np.zeros(g.shape, np.float64)
    for c in ctx.cells:
        if c.fold==q:
            pm+=oof[c.key]
    auc=M.auc_rank(np.nan_to_num(pm[py,px]), np.nan_to_num(pm[ny,nx]))
    row=dict(quadrant=qname, n_train=int(train_pos.sum()), train_auc=rec['train_auc'], loqo_auc=auc, loqo_dti=pooled['pooled_dti'], loqo_cov=pooled['coverage'])
    rows.append(row)
    log(f"LOQO {qname}: train {row['n_train']} auc {rec['train_auc']:.3f} canary {auc:.3f} DTI {pooled['pooled_dti']:.4f} cov {pooled['coverage']:.3f}")
    del oof

out=dict(evidence_class="LOQO", rows=rows, worst_auc=max(r['loqo_auc'] for r in rows), mean_dti=float(np.mean([r['loqo_dti'] for r in rows])))
R.write_json("h61o_loqo.json", out)
log(json.dumps(out, indent=2))
