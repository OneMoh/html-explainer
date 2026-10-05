#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""blur_integrate.py —— 快门运动模糊的积分器（渲染管线第 2 段，Node 侧只负责抓帧）。

为什么单独成段：
  运动模糊的本质是「快门开着的时候，把光积分起来」。截图是一个**瞬间**，
  所以快动作会重影成一串。做法是：同一帧在快门开合区间里 seek 若干次、
  各自截图，再把它们在**线性光**下平均 —— 这才是真的积分，不是 blur 滤镜。
  积分要逐像素算，Node 侧没有图像库，所以这一段交给 numpy/PIL（本来就是本技能的依赖）。

  分成「抓帧（Node，多进程）」+「积分（Python，多进程）」两段还有两个好处：
    · 抓帧阶段才能被 --workers 进程级并行拉满（Chrome 截图是 CPU 活，多进程各自一个浏览器）；
    · --resume 天然可用：已经积分出成品的帧直接跳过，只补缺的。

输入目录约定（render_video.mjs 写出来的）：
  <project>/render/shutter/f_000123/00.png … 0K.png     一帧的 K 个快门样本
输出：
  <project>/render/frames/f_000123.png                  积分后的成片帧
  （若该帧是 hold，Node 侧已直接落盘、不留 shutter 目录，这里不会碰到它）

用法
  "$PY" scripts/blur_integrate.py --project . [--workers 8] [--json]
  "$PY" scripts/blur_integrate.py --project . --report     # 只看统计
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image

# sRGB ↔ 线性光 查表（8bit → float32；16bit → uint8）
_u = np.arange(256) / 255.0
SRGB_TO_LIN = np.where(_u <= 0.04045, _u / 12.92, ((_u + 0.055) / 1.055) ** 2.4).astype(np.float32)
_l = np.arange(65536) / 65535.0
LIN_TO_SRGB = np.clip(np.rint(np.where(_l <= 0.0031308, _l * 12.92,
                                       1.055 * np.power(_l, 1 / 2.4) - 0.055) * 255.0),
                      0, 255).astype(np.uint8)
# sRGB → 线性光 的 uint16 版（积分累加专用：uint32 累加比 float32 省一半内存带宽）
SRGB_TO_LIN_U16 = np.clip(np.rint(SRGB_TO_LIN.astype(np.float64) * 65535.0), 0, 65535).astype(np.uint16)


def _probe_grey(rgb, step=8):
    """抽样灰度图 —— 只用来判断「有没有动 / 有没有切」。

    ★ 不解整图、也不做 BOX 降采样：判切只需要「相邻样本的相对变化量」，
      step=8 抽样（240×135）足够，且**不产生任何大中间数组**
      （旧版对每张样本 reshape+mean，会分配 6.2M 元素的临时数组 —— 这是积分段主要开销之一）。
    luma 系数与 PIL 的 convert('L') 一致（ITU-R 601-2）。
    """
    a = rgb[::step, ::step]
    return (a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114).astype(np.int16)


def cut_side(small):
    """决定要积分哪几张。

    默认全要。但如果相邻两张之间**某一步的变化远大于其它步**（≥3×），那不是运动而是
    不连续 —— 硬切、一个词蹦出来、打出一个字、素材翻页。这时候只保留「帧时刻所在的那一侧」，
    否则硬切会被积成一帧的溶解（Pocket Weather 11.5s 那个切点实测变成了一帧溶解）。
    """
    n = len(small)
    if n < 4:
        return list(range(n))
    d = np.array([np.abs(small[k + 1] - small[k]).mean() for k in range(n - 1)])
    j = int(d.argmax())
    rest = np.delete(d, j)
    if d[j] <= 0 or rest.size == 0 or d[j] < 3 * rest.max():
        return list(range(n))
    # j 在左半 → 保留右半（帧时刻一侧）；否则保留左半
    return list(range(j + 1, n)) if j < n // 2 else list(range(j + 1))


def _save(img, path, ext='png', quality=95, tries=4):
    """写中间帧成品。ext=='jpg' 走 JPEG，否则走 PNG。两者都带重试。

    ★ 为什么必须按 ext 分叉（不是「顺手加个开关」）：`--jpeg` 通道下 Node 侧把静帧直接写成
      `.jpg`，如果积分器仍写 `.png`，`render/frames/` 里就会同时存在两种扩展名 ——
      ffmpeg 的输入是 `f_%06d.jpg`，会**静默漏掉全部动帧**（片子里所有带运动模糊的帧消失），
      而完整性闸门只按一种扩展名点号，两边永远对不上。通道必须一路贯穿到积分器。

    ★ 为什么要重试：在启用实时文件扫描的环境里，刚写出的文件会被扫描线程短暂占用，
      再次覆盖就可能拿到 Permission denied（实测 24 帧里偶发 3 帧）。
      这不是逻辑错误，等几十毫秒即可 —— 但如果不重试，整帧就被判失败。
    """
    for i in range(tries):
        try:
            if ext == 'jpg':
                img.save(path, 'JPEG', quality=quality, subsampling=0)
            else:
                img.save(path, compress_level=1)
            return
        except (PermissionError, OSError):
            if i == tries - 1:
                raise
            time.sleep(0.2 * (i + 1))


def integrate_dir(d, out, ext='png', quality=95, box=8):
    """积分一个 shutter 目录 → 一张成品帧（按 ext 写 png 或 jpg）。返回 (kept, total, cut)

    ★ 每张样本只解码一次：小图（判动/判切）由已解码的 RGB 数组就地降采样得到。
    """
    names = sorted(f for f in os.listdir(d) if f.lower().endswith('.png'))
    if not names:
        return 0, 0, False
    if len(names) == 1:
        # 只有一张样本：目标也是 PNG 时直接拷贝原始字节（逐位无损，不必过一遍编解码）；
        # 目标是 JPEG 就必须真转一次，否则会出现「.jpg 文件名装着 PNG 内容」的脏帧。
        src = os.path.join(d, names[0])
        if ext == 'png':
            shutil.copyfile(src, out)
        else:
            _save(Image.open(src).convert('RGB'), out, ext, quality)
        return 1, 1, False
    arrs = [np.asarray(Image.open(os.path.join(d, n)).convert('RGB')) for n in names]
    if len(arrs) == 1:
        _save(Image.fromarray(arrs[0]), out, ext, quality)
        return 1, 1, False
    keep = cut_side([_probe_grey(a, box) for a in arrs]) if len(arrs) >= 4 else list(range(len(arrs)))
    # ★ uint16 查表 + uint32 累加：与 float32 累加数值等价（实测 8bit 往返差 0），
    #   但内存带宽减半（float32 临时数组 25MB/张 → uint16 12MB/张）
    acc = None
    for k in keep:
        u = SRGB_TO_LIN_U16[arrs[k]]
        acc = u.astype(np.uint32) if acc is None else acc + u
    n = len(keep)
    idx = np.clip((acc + n // 2) // n, 0, 65535).astype(np.uint16)
    _save(Image.fromarray(LIN_TO_SRGB[idx]), out, ext, quality)
    return n, len(arrs), n < len(arrs)


def _work(job):
    d, out, ext, quality = job
    try:
        kept, tot, cut = integrate_dir(d, out, ext, quality)
        # ★ 这里**不删样本目录**：删除文件的开销在不少环境（沙箱 / 实时扫描 / 网络盘）里
        #   远高于积分本身 —— 实测 24 帧样本的目录删除要 120s+，而积分只要 1.6s。
        #   清理统一挪到积分全部完成后（main 里并行做），且可 --keep-shutter 跳过。
        return {'ok': True, 'frame': os.path.basename(out), 'kept': kept, 'total': tot,
                'cut': cut, 'dir': d}
    except Exception as e:  # noqa: BLE001
        return {'ok': False, 'frame': os.path.basename(out),
                'err': f'{type(e).__name__}: {e}', 'dir': d}


def _rm(d):
    """并行清理一个样本目录（失败不致命）"""
    try:
        shutil.rmtree(d, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass
    return 1


def _clean_via_temp(shutter_root):
    """把整个样本目录**整体 rename 到系统临时目录**再删。返回耗时（秒）。

    ★ 为什么要绕这一下：在启用了实时文件扫描 / 云同步 / 企业策略的环境里，
      **用户目录下**逐个删文件是致命慢的 —— 本机实测删 96 个文件要 121s，
      而同一批文件在系统临时目录里删除只要 0.06s。同盘 rename 是纯元数据操作（0.03s），
      因此「整体搬走 + 在临时目录删」把清理成本从 121s 压到 0.08s（≈1400×）。
      跨盘或权限失败时退回原地删（慢，但功能不缺）。
    """
    if not os.path.isdir(shutter_root):
        return 0.0
    t = time.time()
    tmp = os.path.join(tempfile.gettempdir(), 'hx-shutter-%d' % os.getpid())
    try:
        if os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
        os.replace(shutter_root, tmp)
    except OSError:
        shutil.rmtree(shutter_root, ignore_errors=True)
        return time.time() - t
    shutil.rmtree(tmp, ignore_errors=True)
    return time.time() - t


def pending(project, ext='png', quality=95):
    """列出还没积分的帧（shutter 目录还在、且成品帧还没生成）"""
    sd = os.path.join(project, 'render', 'shutter')
    fd = os.path.join(project, 'render', 'frames')
    if not os.path.isdir(sd):
        return []
    jobs = []
    for name in sorted(os.listdir(sd)):
        d = os.path.join(sd, name)
        if not os.path.isdir(d):
            continue
        # ★ 成品帧的扩展名必须与渲染通道一致（Node 侧 --jpeg → 'jpg'）。写死 .png 的后果：
        #   `render/frames/` 里动帧是 .png、静帧是 .jpg，而 ffmpeg 的输入是 `f_%06d.<ext>`，
        #   会**静默漏掉全部动帧**；完整性闸门只按一种扩展名点号，两边永远对不上。
        out = os.path.join(fd, name + '.' + ext)
        # 成品已存在且不比方样本旧 → 是上一轮留下的样本，跳过（--resume 语义）
        if os.path.exists(out):
            try:
                if os.path.getmtime(out) >= os.path.getmtime(d):
                    continue
            except OSError:
                pass
        jobs.append((d, out, ext, quality))
    return jobs


def main():
    ap = argparse.ArgumentParser(description='快门运动模糊积分器')
    ap.add_argument('--project', default='.')
    ap.add_argument('--workers', type=int, default=max(1, min(16, (os.cpu_count() or 4) - 2)))
    ap.add_argument('--keep-shutter', action='store_true',
                    help='积分后保留 shutter 样本目录（默认清理；样本可用于复查）')
    ap.add_argument('--ext', choices=['png', 'jpg'], default='png',
                    help="成品帧扩展名 —— 必须与渲染通道一致（Node 侧 --jpeg 就传 jpg）")
    ap.add_argument('--jpeg-quality', type=int, default=95,
                    help='ext=jpg 时的 JPEG 质量（与 Node 侧 --jpeg-quality 保持一致）')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    project = os.path.abspath(a.project)
    os.makedirs(os.path.join(project, 'render', 'frames'), exist_ok=True)

    jobs = pending(project, a.ext, a.jpeg_quality)
    if a.report:
        n_samp = sum(len([f for f in os.listdir(d) if f.endswith('.png')]) for d, *_ in jobs)
        print(f'待积分 {len(jobs)} 帧 · 共 {n_samp} 张快门样本'
              f'（平均 {n_samp / len(jobs):.1f} 张/帧）' if jobs else '没有待积分的帧')
        return 0
    if not jobs:
        print('blur_integrate：没有待积分的帧（全部已是成品或 shutter 关闭）')
        return 0

    t0 = time.time()
    done = 0
    kept_total = 0
    samp_total = 0
    cut_total = 0
    errs = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_work, j) for j in jobs]
        for f in futs:
            r = f.result()
            if r['ok']:
                done += 1
                kept_total += r['kept']
                samp_total += r['total']
                cut_total += 1 if r['cut'] else 0
            else:
                errs.append(r)
    dt = time.time() - t0
    out = {'frames': len(jobs), 'integrated': done, 'errors': len(errs),
           'samples': samp_total, 'kept_samples': kept_total, 'cut_protected_frames': cut_total,
           'seconds': round(dt, 2), 'workers': a.workers,
           'fps_integrate': round(done / dt, 1) if dt > 0 else None}

    # ---- 清理样本目录：★ 在关键路径之外 ----
    # 删除文件的开销在沙箱 / 实时扫描 / 网络盘上可以远高于积分本身（本机用户目录下实测
    # 删 96 个文件要 121s，而积分只要 1.6s）。所以：① 先出成品、再清理；
    # ② 全部样本都处理完时走「整体 rename 到 Temp 再删」的快路径。
    dirs = [j[0] for j in jobs]
    shutter_root = os.path.join(project, 'render', 'shutter')
    all_dirs = []
    if os.path.isdir(shutter_root):
        all_dirs = [x for x in os.listdir(shutter_root) if os.path.isdir(os.path.join(shutter_root, x))]
    if a.keep_shutter:
        out['clean_seconds'] = None
    else:
        t1 = time.time()
        if jobs and len(all_dirs) == len(jobs):
            _clean_via_temp(shutter_root)
        elif dirs:
            with ProcessPoolExecutor(max_workers=a.workers) as ex:
                list(ex.map(_rm, dirs))
        out['clean_seconds'] = round(time.time() - t1, 2)

    if a.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(f'积分完成：{done}/{len(jobs)} 帧 · 保留 {kept_total} 张样本 · '
              f'{cut_total} 帧保住了硬切 · {dt:.1f}s（{out["fps_integrate"]} 帧/秒, {a.workers} 进程）')
        for e in errs[:5]:
            print(f'  ✗ {e["frame"]}: {e["err"]}')
        if a.keep_shutter:
            print(f'  样本目录已保留：{os.path.join(project, "render", "shutter")}')
        else:
            print(f'  清理样本目录：{len(dirs)} 个 / {out["clean_seconds"]}s')
    return 0 if not errs else 1


if __name__ == '__main__':
    raise SystemExit(main())
