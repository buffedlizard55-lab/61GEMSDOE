#!/usr/bin/env python
"""H61-L: lidar scarp inside gravity corridor (lane-consistent augmentation).

The lane's gravity step sets a +/-1 km corridor; the lidar (1 m DEM aggregated to 100 m)
locates the scarp to 100 m inside it. This is the #1 hypothesis from
hypotheses.html: "1 m lidar scarp detection restricted to gravity corridors".

Uses the existing GP-1012-calibrated inversion from .cache/h61g (no re-fit).
Compares lidar candidates against the same holdout instrument as H61-G and against
the previous best (X2 slope-ridge) so the lift is measurable.

Stages: lidar_screen -> holdout -> final -> unique -> card -> all
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, sys, time, subprocess
from pathlib import Path
import numpy as np, rasterio
from scipy import ndimage as ndi
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from gems61 import buried as B, grid as gridmod, h61g as H, holdout_segmented as holdoutmod, submission_writer
from gems61.metric import ALPHA, BETA, EPS, kernel
from gems61.network import segments
EVID=ROOT/"evidence"; OUT=ROOT/"out"; CACHE=ROOT/".cache"/"h61g"; DOWNLOADS=ROOT/"docs"/"downloads"
REGISTRY_DIRS=[Path("/tmp/refs/registry"), ROOT/"docs"/"downloads"]
BUDGETS=(20000,40000)
PRUNE_PX=2.0
SEEDS=(20,21)
EVALUATOR="gems61.holdout_segmented v2 (whole segments <=12 px, 4 eroded quadrants, seeds 20+21, mode all)"

def log(m): print(m, flush=True)
def sha256(p:Path): 
    import hashlib
    h=hashlib.sha256()
    with open(p,'rb') as fh:
        for b in iter(lambda: fh.read(1<<20), b''): h.update(b)
    return h.hexdigest()
def write_json(n,o):
    EVID.mkdir(exist_ok=True)
    p=EVID/n
    p.write_text(json.dumps(o, indent=2, default=lambda x: float(x) if isinstance(x, (np.floating, np.integer, np.bool_)) else str(x))+"\n")
    log(f"wrote {p.relative_to(ROOT)}")
    return p
def _jsonable(o):
    if isinstance(o,(np.floating,)): return float(o)
    if isinstance(o,(np.integer,)): return int(o)
    if isinstance(o,np.ndarray): return o.tolist()
    if isinstance(o,(np.bool_,)): return bool(o)
    return str(o)

def load_base():
    g=gridmod.load_grid()
    grav=np.asarray(B.load_band(13), np.float64)
    valid=g.footprint & np.isfinite(grav)
    return g,grav,valid

def decode_lidar():
    # fetch quant json via codeload if needed
    jpath=ROOT/"data/external/lidar_scarp_features.json"
    if not jpath.exists():
        tarball="https://codeload.github.com/buffedlizard55-lab/GEMSDOE24/tar.gz/main"
        r=subprocess.run(["curl","-sL", tarball], stdout=subprocess.PIPE, timeout=120)
        p=subprocess.run(["tar","-xzOf","-", "--wildcards", "*/data/external/lidar_scarp_features.json"], input=r.stdout, stdout=subprocess.PIPE)
        j=json.loads(p.stdout)
        jpath.write_text(json.dumps(j, indent=2))
    else:
        j=json.loads(jpath.read_text())
    with rasterio.open(ROOT/"data/external/lidar_scarp_features_u8.tif") as src:
        lidar=np.stack([src.read(i) for i in range(1,13)], axis=0)
        descs=src.descriptions
    # decode
    decoded={}
    for i,name in enumerate(descs):
        if name=="valid":
            # keep raw 0-255 as fraction
            decoded[name]= (lidar[i].astype(np.float64)/255.0)
            continue
        if name not in j["quantisation"]:
            continue
        xmax, typ = j["quantisation"][name]
        q=lidar[i].astype(np.float64)
        mask=q>0
        out=np.zeros_like(q)
        norm=np.zeros_like(q)
        norm[mask]=(q[mask]-1)/254.0
        if typ=="sqrt":
            out[mask]=xmax*(norm[mask]**2)
        else:
            out[mask]=xmax*norm[mask]
        decoded[name]=out
        decoded[name+"_mask"]=mask
        decoded[name+"_u8"]=lidar[i]
    # valid lidar mask
    valid_lidar = lidar[11]>0
    decoded["_valid_lidar"]=valid_lidar
    decoded["_descs"]=descs
    decoded["_quant"]=j["quantisation"]
    return decoded

def lidar_screen(_a):
    g,grav,valid=load_base()
    cat=g.catalogue
    dcat=ndi.distance_transform_edt(~cat)
    kcat=kernel(dcat)
    dec=decode_lidar()
    depth=np.load(CACHE/"depth_full.npy")
    steps=np.load(CACHE/"steps_full.npy")
    corr=H.corridor_mask(steps, H.CORRIDOR_PX)
    basin=valid & (depth > H.BASIN_FLOOR_M)
    rows=[]
    def add(name, mask):
        n=int(mask.sum())
        if n==0: return
        rows.append(dict(candidate=name, n=n, within_3px=float((dcat[mask]<=3).mean()), mean_kernel=float(kcat[mask].mean())))
    base = valid & dec["_valid_lidar"]
    add("RANDOM lidar-valid pixel", base)
    add("RANDOM inside corridor (lidar-valid)", base & corr)
    for name in ["ex_max","ex_mean","step_max","lapneg_max","lappos_max","downface_max","upface_max","cross_max","relief","coh100"]:
        arr=dec[name]
        msk=dec[name+"_mask"] & valid
        if msk.sum()==0: continue
        thr=np.percentile(arr[msk], 50)
        top= msk & (arr>=thr)
        add(f"{name} top50% all", top)
        add(f"{name} top50% inside corridor", top & corr)
        add(f"{name} top50% inside corridor+basin", top & corr & basin)
        add(f"{name} top50% outside corridor", top & ~corr)
        # top 25%
        thr75=np.percentile(arr[msk],75)
        top25= msk & (arr>=thr75)
        add(f"{name} top25% inside corridor", top25 & corr)
    # also combo: relief * step_max rank?
    # simple combined score: average rank of relief, ex_max, lappos
    # build normalized rank inside valid lidar
    def rank01(vals, mask):
        out=np.zeros(vals.shape, np.float32)
        idx=np.flatnonzero(mask.ravel())
        if idx.size==0: return out
        v=vals.ravel()[idx]
        order=np.argsort(v, kind="stable")
        r=np.empty(idx.size, np.float32)
        r[order]=(np.arange(1, idx.size+1, dtype=np.float32))/np.float32(idx.size)
        out.ravel()[idx]=r
        return out
    # combined: relief + ex_max + lappos + step_max
    valid_mask = dec["_valid_lidar"] & valid
    ranks=[]
    for n in ["relief","ex_max","step_max","lappos_max"]:
        ranks.append(rank01(dec[n], valid_mask))
    combo=np.mean(ranks, axis=0) if ranks else None
    if combo is not None:
        # threshold at median
        thr=np.median(combo[valid_mask])
        top= valid_mask & (combo>=thr)
        add("COMBO relief+ex_max+step+lappos top50% inside corridor", top & corr)
        add("COMBO top25% inside corridor", valid_mask & (combo>=np.percentile(combo[valid_mask],75)) & corr)
    for r in rows:
        log(f"  {r['candidate']:55s} n={r['n']:7d} within3={r['within_3px']:.4f} k={r['mean_kernel']:.4f}")
    write_json("h61l_lidar_screen.json", dict(evidence_class="MEASURED lidar screen", rows=rows))

def _candidate_fields_lidar(g, valid):
    depth_full=np.load(CACHE/"depth_full.npy").astype(np.float64)
    steps_full=np.load(CACHE/"steps_full.npy")
    corr=H.corridor_mask(steps_full, H.CORRIDOR_PX)
    basin=valid & (depth_full > H.BASIN_FLOOR_M)
    conceal=B.concealment_prior(depth_full, floor_m=H.BASIN_FLOOR_M, cap_m=1500.0)
    # slope ridge baseline (band19) for comparison
    b19=np.asarray(B.load_band(19), np.float64)
    ridge, slope = H.slope_ridges(b19, valid)
    dec=decode_lidar()
    valid_lidar=dec["_valid_lidar"] & valid
    # helpers
    def rank01(vals,mask):
        out=np.zeros(vals.shape, np.float32)
        idx=np.flatnonzero(mask.ravel())
        if idx.size==0: return out
        v=vals.ravel()[idx]
        order=np.argsort(v, kind="stable")
        r=np.empty(idx.size, np.float32)
        r[order]=(np.arange(1, idx.size+1, dtype=np.float32))/np.float32(idx.size)
        out.ravel()[idx]=r
        return out
    # lidar decoded arrays
    relief=dec["relief"]
    ex_max=dec["ex_max"]
    step_max=dec["step_max"]
    lappos=dec["lappos_max"]
    upface=dec["upface_max"]
    downface=dec["downface_max"]
    cross=dec["cross_max"]
    # Build combined lidar scarp likelihood: weighted sum of top indicators
    # Following the screen, relief was best (0.074), upface 0.071, lappos 0.069
    # We combine relief, ex_max, step_max, lappos equally, then rank
    # Only where lidar valid
    r_relief=rank01(relief, valid_lidar)
    r_ex=rank01(ex_max, valid_lidar)
    r_step=rank01(step_max, valid_lidar)
    r_lappos=rank01(lappos, valid_lidar)
    r_upface=rank01(upface, valid_lidar)
    r_downface=rank01(downface, valid_lidar)
    combo_mean = (r_relief + r_ex + r_step + r_lappos)/4.0
    combo_best = (r_relief*0.35 + r_upface*0.25 + r_ex*0.20 + r_lappos*0.20)
    # ridge-like maxima for lidar? Instead of maxima, we can just threshold combo
    # But to mimic slope_ridges maxima, we take Blakely-Simpson maxima of combo
    combo_filled=np.where(valid_lidar, combo_mean, np.nanmedian(combo_mean))
    combo_mx = B.blakely_simpson_maxima(combo_filled) & valid_lidar
    combo_best_filled=np.where(valid_lidar, combo_best, np.nanmedian(combo_best))
    combo_best_mx = B.blakely_simpson_maxima(combo_best_filled) & valid_lidar
    # also maxima of relief alone
    relief_mx = B.blakely_simpson_maxima(np.where(valid_lidar, relief, np.nanmedian(relief))) & valid_lidar
    # candidate fields
    fields={}
    # Baseline: previous best X2 for calibration
    sl_rank=H.rank01(slope, ridge & valid)
    w=np.minimum(sl_rank,0.9)*(0.5+0.5*conceal)
    fields["X2 slope-ridge inside corridor basin (baseline)"]=np.where(ridge & corr & basin, w, 0.0)
    fields["X2 slope-ridge inside corridor any depth"]=np.where(ridge & corr, np.minimum(sl_rank,0.9), 0.0)
    # Lidar candidates
    # L1: relief maxima inside corridor
    r_relief_rank=H.rank01(relief, relief_mx & valid)
    w_relief=np.minimum(r_relief_rank,0.9)*(0.5+0.5*conceal)
    fields["L1 relief maxima inside corridor+basin"]=np.where(relief_mx & corr & basin & valid_lidar, w_relief, 0.0)
    fields["L1 relief maxima inside corridor any depth"]=np.where(relief_mx & corr & valid_lidar, np.minimum(r_relief_rank,0.9), 0.0)
    # L2: combo_mean maxima inside corridor
    r_combo=rank01(combo_mean, combo_mx & valid)
    w_combo=np.minimum(r_combo,0.9)*(0.5+0.5*conceal)
    # need rank inside valid lidar for combo mean
    r_combo_full=H.rank01(combo_mean, combo_mx & valid_lidar)
    w_combo=np.minimum(r_combo_full,0.9)*(0.5+0.5*conceal)
    fields["L2 combo(relief+ex+step+lappos) maxima inside corridor+basin"]=np.where(combo_mx & corr & basin, w_combo, 0.0)
    fields["L2b combo_best(relief+upface+ex+lappos) maxima inside corridor+basin"]=np.where(combo_best_mx & corr & basin, np.minimum(H.rank01(combo_best, combo_best_mx & valid_lidar),0.9)*(0.5+0.5*conceal), 0.0)
    # L3: dense lidar: thresholded combo (not maxima) - top 30% inside corridor
    # This is more like a field, packed per tile max
    thr70=np.percentile(combo_mean[valid_lidar], 70)
    dense = valid_lidar & (combo_mean>=thr70)
    # rank dense by combo value
    dense_rank=H.rank01(combo_mean, dense)
    fields["L3 dense top30% lidar combo inside corridor+basin"]=np.where(dense & corr & basin, dense_rank*(0.5+0.5*conceal), 0.0)
    # L4: ex_max + relief top50% outside corridor control
    fields["C lidar outside corridor (relief maxima)"]=np.where(relief_mx & ~corr & basin, w_relief, 0.0)
    # L5: lidar-only without corridor (to measure corridor lift)
    fields["C lidar relief maxima basin (no corridor)"]=np.where(relief_mx & basin & valid_lidar, w_relief, 0.0)
    # Piedmont variant: basin edge 0-2km from bedrock outcrop (depth=0 contour)
    # depth=0 buffer 0-2km basinward
    bedrock = depth_full <= 10  # outcrop approx
    # distance to bedrock edge
    # we want pixels 0-20 px (0-2km) basinward of bedrock
    # compute distance to bedrock, and also depth>0
    dist_bedrock=ndi.distance_transform_edt(~bedrock)
    piedmont = valid & (depth_full>10) & (depth_full<1500) & (dist_bedrock>=1) & (dist_bedrock<=20)
    # slope ridge in piedmont
    fields["P piedmont slope-ridge (0-2km from bedrock)"]=np.where(ridge & piedmont, w, 0.0)
    fields["P lidar relief piedmont"]=np.where(relief_mx & piedmont & valid_lidar, w_relief, 0.0)
    meta=dict(corridor_fraction=float((corr&valid).sum()/valid.sum()), basin_fraction=float(basin.sum()/valid.sum()),
              valid_lidar_fraction=float(valid_lidar.sum()/valid.sum()), n_slope_ridge=int((ridge&valid).sum()),
              n_relief_mx=int((relief_mx&valid).sum()), n_combo_mx=int((combo_mx&valid).sum()))
    aux=dict(corridor=corr, basin=basin, depth_full=depth_full, ridge=ridge, slope=slope, relief=relief, valid_lidar=valid_lidar, piedmont=piedmont)
    return fields, meta, aux

def _per_cell_emit(field, cell, visible_full, budget_cell, random_kind=None, seed=0):
    sl=cell.bbox
    vis=visible_full[sl]
    far=ndi.distance_transform_edt(~vis) > PRUNE_PX
    allowed=cell.active & far
    if random_kind=="lines":
        return H.random_lines(allowed.shape, allowed, budget_cell, seed=seed)
    if random_kind=="dots":
        return H.random_dots(allowed, budget_cell, seed=seed)
    if random_kind=="corridor":
        return H.random_dots(allowed & field[sl], budget_cell, seed=seed)
    return H.dot_thin(field[sl], allowed, budget_cell)

def _score_crop(cell, p_crop):
    p=p_crop & cell.active
    n_emit=int(p.sum())
    if n_emit==0 or cell.n_truth==0:
        return dict(tp=0.0, fp=float(n_emit), fn=float(cell.n_truth), n_emit=n_emit), None
    dp=ndi.distance_transform_edt(~p)
    tp=float(kernel(dp[cell.truth_yx]).sum())
    fn=float(cell.n_truth)-tp
    fp=float((1.0-cell.k_dg[p]).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_emit=n_emit), dp

def _pool(parts):
    tp=sum(p["tp"] for p in parts); fp=sum(p["fp"] for p in parts); fn=sum(p["fn"] for p in parts)
    return dict(pooled_dti=float(tp/(tp+ALPHA*fp+BETA*fn+EPS)), tp=tp, fp=fp, fn=fn, n_emitted=int(sum(p["n_emit"] for p in parts)), coverage=float(tp/max(tp+fn,1e-9)))
def _boot_ci(parts, n_boot=2000, seed=7):
    rng=np.random.default_rng(seed)
    parts=list(parts)
    vals=[]
    for _ in range(n_boot):
        pick=[parts[i] for i in rng.integers(len(parts), size=len(parts))]
        vals.append(_pool(pick)["pooled_dti"])
    return [float(np.percentile(vals,2.5)), float(np.percentile(vals,97.5))]

def stage_holdout(_a):
    t0=time.time()
    g,grav,valid=load_base()
    fields,meta,aux=_candidate_fields_lidar(g,valid)
    log(f"corridor {meta['corridor_fraction']:.3f} basin {meta['basin_fraction']:.3f} valid_lidar {meta['valid_lidar_fraction']:.3f}")
    ctx=holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    n_truth=sum(c.n_truth for c in ctx.cells)
    log(f"holdout {len(ctx.cells)} cells {n_truth} withheld")
    seg, n_seg = segments(g.catalogue, max_len_px=12)[:2]
    depth_full=aux["depth_full"]
    fp_px=float(g.footprint.sum())
    refs={}
    for d in REGISTRY_DIRS:
        for p in sorted(d.glob("*.tif")):
            if "gems61" in p.name: continue
            try:
                with rasterio.open(p) as src:
                    if (src.height, src.width)!=g.shape: continue
                    arr=src.read(1)
                refs[p.name]=np.isfinite(arr)&(arr>0.5)
            except Exception as e:
                log(f" skip {p.name}: {e}")
    results=[]
    def run(name,kind,field=None,budget=None,fixed=None,seed=0):
        parts,rec_rows=[],[]
        for ci,cell in enumerate(ctx.cells):
            if fixed is not None:
                p_crop=fixed[cell.bbox]
            else:
                dom_px=float(cell.active.sum())
                tot=sum(c.active.sum() for c in ctx.cells if c.seed==cell.seed)
                b_cell=int(round(budget*dom_px/float(tot)))
                p_crop=_per_cell_emit(field, cell, ctx.visible(cell.key), b_cell, random_kind=kind, seed=seed+ci)
            part,dp=_score_crop(cell, p_crop)
            part["cell"]=cell.key
            parts.append(part)
            hid=ctx.hidden_by_cell[cell.key][cell.bbox]
            ids=np.unique(seg[cell.bbox][hid]); ids=ids[ids>0]
            if dp is None: dp=np.full(hid.shape, np.inf)
            near=dp<=3.0
            segc=seg[cell.bbox]; dep=depth_full[cell.bbox]
            for sid in ids:
                m=(segc==sid)&hid
                if not m.any(): continue
                rec_rows.append((cell.key,int(sid),int(m.sum()),float(np.median(dep[m])), float(near[m].mean())))
        pooled=_pool(parts)
        rec=np.array([(r[2],r[3],r[4]) for r in rec_rows], np.float64) if rec_rows else np.zeros((0,3))
        basin_mask=rec[:,1]>100.0 if rec.size else np.zeros(0,bool)
        n_b=int(basin_mask.sum()); k_b=int((rec[basin_mask,2]>=0.5).sum()) if n_b else 0
        n_all=int(rec.shape[0]); k_all=int((rec[:,2]>=0.5).sum()) if n_all else 0
        pooled["n_emitted_per_draw"]=pooled["n_emitted"]/len(SEEDS)
        row=dict(name=name, kind=kind or "candidate", budget=budget, **pooled, ci95_bootstrap_cells=_boot_ci(parts),
                 per_cell_dti=[round(float(p["tp"]/(p["tp"]+ALPHA*p["fp"]+BETA*p["fn"]+EPS)),5) for p in parts],
                 segments_withheld_total=n_all, segments_recovered_total=k_all,
                 segments_withheld_basin_interior=n_b, segments_recovered_basin_interior=k_b,
                 basin_recovery_rate=(k_b/n_b) if n_b else None,
                 basin_recovery_ci95=list(H.wilson(k_b,n_b)) if n_b else None)
        results.append(row)
        log(f"  {name:65s} n/draw={row['n_emitted_per_draw']:8.0f} HOLDOUT-DTI={row['pooled_dti']:.4f} CI[{row['ci95_bootstrap_cells'][0]:.4f},{row['ci95_bootstrap_cells'][1]:.4f}] cov={row['coverage']:.3f} basin {k_b}/{n_b}")
        return row
    for name,m in refs.items():
        run(f"REGISTRY {name}", "registry", fixed=m)
    for budget in BUDGETS:
        for name,field in fields.items():
            run(f"{name} @ {budget}", None, field=field, budget=budget)
        run(f"CONTROL random lines @ {budget}", "lines", field=None, budget=budget, seed=100)
        run(f"CONTROL random dots inside corridor+basin @ {budget}", "corridor", field=aux["corridor"]&aux["basin"], budget=budget, seed=200)
        run(f"CONTROL random dots lidar-valid @ {budget}", "dots", field=None, budget=budget, seed=300)
    # leakage canary
    rng=np.random.default_rng(3)
    feats={"inverted depth":aux["depth_full"], "relief":aux["relief"] if "relief" in aux else np.zeros_like(valid,dtype=float),
           "band19 slope": aux["slope"], "band13 gravity": grav,
           "corridor": aux["corridor"].astype(float), "valid_lidar": aux["valid_lidar"].astype(float)}
    canary={}
    pos_idx, neg_idx=[],[]
    for cell in ctx.cells:
        sl=cell.bbox
        yy,xx=cell.truth_yx
        pos_idx.append((yy+sl[0].start, xx+sl[1].start))
        act=np.argwhere(cell.active)
        pick=act[rng.choice(act.shape[0], size=min(20000, act.shape[0]), replace=False)]
        neg_idx.append((pick[:,0]+sl[0].start, pick[:,1]+sl[1].start))
    py=np.concatenate([p[0] for p in pos_idx]); px=np.concatenate([p[1] for p in pos_idx])
    ny=np.concatenate([p[0] for p in neg_idx]); nx=np.concatenate([p[1] for p in neg_idx])
    for fname,f in feats.items():
        pv=np.nan_to_num(f[py,px], nan=0.0); nv=np.nan_to_num(f[ny,nx], nan=0.0)
        canary[fname]=dict(auc=H.auc_rank(pv,nv), n_pos=int(pv.size), n_neg=int(nv.size))
        log(f"  canary {fname:28s} AUC={canary[fname]['auc']:.3f}")
    worst=max(canary.values(), key=lambda r: r["auc"])["auc"]
    cands=[r for r in results if r["kind"]=="candidate"]
    best=max(cands, key=lambda r: r["pooled_dti"])
    ctrl_lines={r["budget"]:r for r in results if r["name"].startswith("CONTROL random lines")}
    ctrl_corr={r["budget"]:r for r in results if r["name"].startswith("CONTROL random dots inside corridor")}
    reg_best=max([r for r in results if r["kind"]=="registry"], key=lambda r: r["pooled_dti"], default=None)
    write_json("h61l_holdout.json", dict(evidence_class="HOLDOUT-DTI", evaluator=EVALUATOR, alpha=ALPHA, beta=BETA, kernel_m=300,
        n_withheld_truth_px=int(n_truth), n_cells=len(ctx.cells), prune_px=PRUNE_PX, budgets=list(BUDGETS), fields_meta=meta,
        results=results, best_candidate=best["name"],
        best_vs_random_lines=dict(candidate=best["pooled_dti"], random_lines=ctrl_lines[best["budget"]]["pooled_dti"], ratio=best["pooled_dti"]/max(ctrl_lines[best["budget"]]["pooled_dti"],1e-9)),
        registry_reference_best=(dict(name=reg_best["name"], pooled_dti=reg_best["pooled_dti"]) if reg_best else None),
        leakage_canary=dict(threshold_auc=0.90, worst_auc=worst, passed=bool(worst<0.90), per_feature=canary),
        note="Lidar holdout: same instrument as H61-G, adds lidar candidates; registry scored as-is", elapsed_s=round(time.time()-t0,1)))

def stage_final(a):
    g,grav,valid=load_base()
    hold=json.loads((EVID/"h61l_holdout.json").read_text())
    cands=[r for r in hold["results"] if r["kind"]=="candidate"]
    chosen=max(cands, key=lambda r: r["pooled_dti"]) if not a.candidate else next(r for r in cands if r["name"]==a.candidate)
    fname=chosen["name"].rsplit(" @ ",1)[0]
    budget=int(chosen["budget"])
    fields,meta,aux=_candidate_fields_lidar(g,valid)
    field=fields[fname]
    far=ndi.distance_transform_edt(~g.catalogue) > PRUNE_PX
    allowed=valid & far & ~g.catalogue
    dots=H.dot_thin(field, allowed, budget)
    ctx=holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    ribbon_vs_dots={}
    for label in ("dots (shipped)", "3x3 ribbons (not shipped)"):
        parts=[]
        for ci,cell in enumerate(ctx.cells):
            dom_px=float(cell.active.sum())
            b_cell=int(round(budget*dom_px/float(sum(c.active.sum() for c in ctx.cells if c.seed==cell.seed))))
            d_crop=_per_cell_emit(field, cell, ctx.visible(cell.key), b_cell)
            if label.startswith("3x3"):
                vis=ctx.visible(cell.key)[cell.bbox]
                far_c=ndi.distance_transform_edt(~vis)>PRUNE_PX
                d_crop=H.ribbon(d_crop,1)&cell.active&far_c
            part,_=_score_crop(cell, d_crop)
            parts.append(part)
        pooled=_pool(parts)
        ribbon_vs_dots[label]=dict(pooled_dti=pooled["pooled_dti"], ci95=_boot_ci(parts), coverage=pooled["coverage"], emitted_per_draw=pooled["n_emitted"]/len(SEEDS), fp_mass=pooled["fp"], tp_mass=pooled["tp"])
        log(f"  {label:28s} HOLDOUT-DTI={pooled['pooled_dti']:.4f} CI{ribbon_vs_dots[label]['ci95']} cov={pooled['coverage']:.3f}")
    del ctx
    values=dots.astype(np.float32)
    n_dots=int(dots.sum())
    dcat=ndi.distance_transform_edt(~g.catalogue)[dots]
    stamp=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest=hashlib.sha256(values.tobytes()).hexdigest()[:12]
    short_map={"X2 slope-ridge inside corridor basin (baseline)":"x2-baseline",
               "X2 slope-ridge inside corridor any depth":"x2b-baseline-any",
               "L1 relief maxima inside corridor+basin":"l1-relief-corr-basin",
               "L1 relief maxima inside corridor any depth":"l1-relief-corr-any",
               "L2 combo(relief+ex+step+lappos) maxima inside corridor+basin":"l2-combo-corr-basin",
               "L2b combo_best(relief+upface+ex+lappos) maxima inside corridor+basin":"l2b-combo-best-corr-basin",
               "L3 dense top30% lidar combo inside corridor+basin":"l3-dense-combo-corr-basin",
               "C lidar outside corridor (relief maxima)":"c-lidar-outside",
               "C lidar relief maxima basin (no corridor)":"c-lidar-basin-nocorr",
               "P piedmont slope-ridge (0-2km from bedrock)":"p-piedmont-slope",
               "P lidar relief piedmont":"p-lidar-piedmont"}
    short=short_map.get(fname, fname[:20])
    name=f"gems61-h61l-{short}-{n_dots}dots-{stamp}-{digest}-zeros"
    note=f"H61-L: lidar scarp ({fname.split(' ')[0]}) inside GP-1012 gravity corridor; {n_dots} dots at 3 px; UNSCORED"
    if len(note)>140: note=note[:140]
    OUT.mkdir(exist_ok=True)
    rec=submission_writer.write_submission(OUT/f"{name}.tif", values, sample=gridmod.DATA_DIR/"sample_submission.tif", footprint=g.footprint, note=note, name=name[:140], catalogue=g.catalogue,
        metadata=dict(method="H61-L", candidate=fname, budget=budget, n_dots=n_dots, holdout_dti=chosen["pooled_dti"], evaluator=EVALUATOR, prune_px=PRUNE_PX))
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for ext in (".tif",".zip",".json"):
        shutil.copy2(OUT/f"{name}{ext}", DOWNLOADS/f"{name}{ext}")
    rand=next(r for r in hold["results"] if r["name"]==f"CONTROL random lines @ {budget}")
    reg=hold.get("registry_reference_best")
    beats_random=chosen["pooled_dti"]>rand["pooled_dti"]
    beats_group=(reg is None) or (chosen["pooled_dti"]>reg["pooled_dti"])
    write_json("h61l_final.json", dict(evidence_class="MEASURED (file) + HOLDOUT-DTI", submission=name, note=note, note_chars=len(note), candidate=fname, budget=budget,
        n_dots=n_dots, ribbon_vs_dots_holdout=ribbon_vs_dots, dots_distance_to_catalogue_px=dict(min=float(dcat.min()), median=float(np.median(dcat)), mean=float(dcat.mean()), frac_within_3px=float((dcat<=3).mean())),
        tif=f"out/{name}.tif", zip=f"out/{name}.zip", receipt=f"out/{name}.json", download_tif=f"docs/downloads/{name}.tif", download_zip=f"docs/downloads/{name}.zip",
        sha256=rec["sha256"], bytes=rec["bytes"], zip_sha256=rec["zip_sha256"], validator=rec["validator"]["checks"], validator_all_passed=rec["validator"]["all_checks_passed"],
        holdout=dict(dti=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"], random_lines=rand["pooled_dti"], beats_random_lines=beats_random, registry_reference_best=reg, beats_registry=beats_group, n_withheld_truth_px=hold["n_withheld_truth_px"], evaluator=EVALUATOR),
        slot_recommendation=("PROMOTE-ELIGIBLE: beats both controls and registry on holdout" if (beats_random and beats_group) else "DO NOT SPEND A SLOT: file is valid and unique, but holdout does not put it above group's best-known file; keep as negative/diagnostic result"), organizer_receipt=None))

def stage_unique(_a):
    import rasterio
    from scipy.stats import spearmanr
    g=gridmod.load_grid()
    fin=json.loads((EVID/"h61l_final.json").read_text())
    with rasterio.open(ROOT/fin["tif"]) as src:
        mine=src.read(1)
    mine_dots=mine>0.5
    rows=[]; seen=set()
    for d in REGISTRY_DIRS:
        for p in sorted(d.glob("*.tif")):
            if p.name in seen or p.name==Path(fin["tif"]).name: continue
            seen.add(p.name)
            try:
                with rasterio.open(p) as src:
                    if (src.height, src.width)!=g.shape: continue
                    other=src.read(1)
            except Exception as e: rows.append(dict(file=p.name, error=str(e)[:100])); continue
            o=np.where(np.isfinite(other), other, 0.0)
            a_=mine[g.footprint]; b_=o[g.footprint]
            rho=float(spearmanr(a_,b_).statistic) if a_.std()>0 and b_.std()>0 else float("nan")
            od=o>0.5
            near=ndi.distance_transform_edt(~od)<=3.0
            frac=float(near[mine_dots].mean()) if mine_dots.any() else float("nan")
            base=float(near[g.footprint].mean())
            inter=int((mine_dots&od).sum()); union=int((mine_dots|od).sum())
            jac=inter/max(union,1)
            dense=int(od.sum())>5*int(mine_dots.sum())
            gate_value=jac if dense else frac
            gate_rule="Jaccard (reference is dense: >5x my support)" if dense else "one-sided 3 px overlap"
            gate_limit=0.50 if dense else 0.70
            rows.append(dict(file=p.name, sha256=sha256(p), spearman_footprint=rho, frac_my_dots_within_3px_of_theirs=frac, base_rate_within_3px=base, jaccard=jac, their_positive_px=int(od.sum()), overlap_gate_rule=gate_rule, overlap_gate_value=gate_value, overlap_gate_limit=gate_limit, overlap_gate_exceeded=bool(gate_value>gate_limit), byte_identical=(sha256(p)==fin["sha256"])))
            log(f"  {p.name[:70]:70s} rho={rho:+.4f} overlap3px={frac:.3f} (base {base:.3f}) jaccard={jac:.4f} gate={gate_rule.split(' ')[0]}")
    ok=[r for r in rows if "spearman_footprint" in r]
    worst_rho=max(ok, key=lambda r: (r["spearman_footprint"] if r["spearman_footprint"]==r["spearman_footprint"] else -2))
    worst_ov=max(ok, key=lambda r: r["frac_my_dots_within_3px_of_theirs"])
    worst_gate=max(ok, key=lambda r: r["overlap_gate_value"]/r["overlap_gate_limit"])
    verdict="UNIQUE" if (worst_rho["spearman_footprint"]<=0.90 and not any(r["overlap_gate_exceeded"] for r in ok) and not any(r["byte_identical"] for r in ok)) else "DUPLICATE -- lane drift, do not submit"
    write_json("h61l_uniqueness.json", dict(evidence_class="MEASURED", my_file=fin["tif"], my_sha256=fin["sha256"], my_dots=int(mine_dots.sum()), n_registry_rasters_compared=len(ok), rho_limit=0.90, overlap_limit=0.70, worst_spearman=dict(file=worst_rho["file"], value=worst_rho["spearman_footprint"]), worst_overlap=dict(file=worst_ov["file"], value=worst_ov["frac_my_dots_within_3px_of_theirs"], base_rate=worst_ov["base_rate_within_3px"], gate_rule=worst_ov["overlap_gate_rule"], gate_value=worst_ov["overlap_gate_value"], gate_limit=worst_ov["overlap_gate_limit"]), worst_overlap_gate=dict(file=worst_gate["file"], rule=worst_gate["overlap_gate_rule"], value=worst_gate["overlap_gate_value"], limit=worst_gate["overlap_gate_limit"]), byte_identical_to_any=[r["file"] for r in ok if r["byte_identical"]], verdict=verdict, rows=rows))

def stage_card(_a):
    hold=json.loads((EVID/"h61l_holdout.json").read_text())
    fin=json.loads((EVID/"h61l_final.json").read_text())
    uni=json.loads((EVID/"h61l_uniqueness.json").read_text())
    inv=json.loads((EVID/"h61g_invert.json").read_text())
    chosen=next(r for r in hold["results"] if r["name"]==f"{fin['candidate']} @ {fin['budget']}")
    rand=next(r for r in hold["results"] if r["name"]==f"CONTROL random lines @ {fin['budget']}")
    reg=hold.get("registry_reference_best")
    promote=fin["slot_recommendation"].startswith("PROMOTE")
    card=dict(hypothesis="H61-L: buried fault = GP-1012-calibrated basement step (+/-1km corridor) + lidar scarp (1m 3DEP DEM aggregated to 100m) inside it; 1m data supplies the 100m positional accuracy gravity cannot.",
        mechanism="Basement throw -> isostatic residual HGM (Parker/Oldenburg, Blakely-Simpson, throw>=80m) -> corridor -> lidarscars: relief/excess-slope/step + convexity maxima from 1m DEM detect 0.5-5m scarps in basin fill; corridor removes fan-toe/terrace mimics without basement step.",
        named_non_fault_mimic="Intrabasement density contacts (same gravity step, no scarp) and terrace/incision scarps or fan toes (lidar scarp with no basement step); conjunction is the discriminator. Lidar valid only where 3DEP coverage exists (76% of footprint).",
        holdout_dti=dict(value=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"], evaluator=hold["evaluator"], n_withheld_positive_px=hold["n_withheld_truth_px"], n_dots_per_draw=chosen["n_emitted"]//len(SEEDS), random_lines_same_budget=rand["pooled_dti"], basin_interior_segments=f"{chosen['segments_recovered_basin_interior']}/{chosen['segments_withheld_basin_interior']} vs {rand['segments_recovered_basin_interior']}/{rand['segments_withheld_basin_interior']} by random lines", registry_reference_best=reg),
        correlation_overlap_vs_registry=dict(worst_spearman=uni["worst_spearman"], worst_overlap=uni["worst_overlap"], n_compared=uni["n_registry_rasters_compared"], verdict=uni["verdict"]),
        raster_sha256=fin["sha256"], validator_output=dict(checks=fin["validator"], all_passed=fin["validator_all_passed"]),
        submission_name=fin["submission"], note=fin["note"], note_chars=fin["note_chars"],
        leakage_canary=hold["leakage_canary"]["passed"], leakage_worst_auc=hold["leakage_canary"]["worst_auc"],
        inversion=dict(z0_m=inv["inversion"]["z0_m"], delta_rho=inv["inversion"]["delta_rho"], regional_sigma_km=inv["inversion"]["regional_sigma_km"], fraction_deeper_than_1km=inv["depth_stats"]["fraction_gt_1km"], cross_check_r_vs_band15=inv["cross_check_vs_supplied_band15"]["pearson_r"]),
        verdict="promote" if promote else "negative", verdict_reason=fin["slot_recommendation"],
        candidate_selection=dict(rule="max pooled HOLDOUT-DTI", shipped=fin["candidate"], shipped_budget=fin["budget"], best_by_pooled_dti=hold["best_candidate"]),
        organizer_confirmed_score=None, experiments_run=3, budget_experiments=3)
    write_json("h61l_run_card.json", card)
    log(json.dumps(card, indent=1, default=_jsonable)[:4000])

STAGES=dict(lidar_screen=lidar_screen, holdout=stage_holdout, final=stage_final, unique=stage_unique, card=stage_card)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("stage", choices=list(STAGES)+["all"])
    ap.add_argument("--candidate", default=None)
    a=ap.parse_args()
    order=list(STAGES) if a.stage=="all" else [a.stage]
    for s in order:
        log(f"==== {s} ====")
        STAGES[s](a)
if __name__=="__main__": main()
