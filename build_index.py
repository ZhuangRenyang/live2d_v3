#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描 models/ 目录并生成 models/index.json，供预览页自动发现模型。

用法：
    python build_index.py

把模型文件夹直接放进 models/ 后运行本脚本即可，无需手工登记。
支持任意层级的嵌套，例如：
    models/某模型/xxx.model3.json
    models/合辑名/某模型/xxx.model3.json
"""

import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, 'models')
OUT_FILE = os.path.join(MODELS_DIR, 'index.json')

MOC_VERSION_NAMES = {1: '3.0', 2: '3.3', 3: '4.0', 4: '4.2', 5: '5.0'}

# 扫描时忽略的目录名（小写比较）
SKIP_DIRS = {'node_modules', '.git', '__pycache__', '.vs', '.idea'}


def read_moc_version(path):
    """读取 moc3 文件头里的版本号，返回如 '3.0'；读不到返回 None。"""
    try:
        with open(path, 'rb') as f:
            head = f.read(8)
        if len(head) < 8 or head[:4] != b'MOC3':
            return None
        ver = struct.unpack('<I', head[4:8])[0]
        return MOC_VERSION_NAMES.get(ver, 'unknown(%d)' % ver)
    except OSError:
        return None


def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print('  [skip] 无法解析 %s: %s' % (path, e))
        return None


def build():
    if not os.path.isdir(MODELS_DIR):
        print('找不到 models 目录：%s' % MODELS_DIR)
        return 1

    entries = []
    seen_paths = set()

    for dirpath, dirnames, filenames in os.walk(MODELS_DIR):
        dirnames[:] = sorted(d for d in dirnames if d.lower() not in SKIP_DIRS)

        # 跳过编辑器临时目录
        if os.sep + 'tmp' in dirpath:
            continue

        model_files = sorted(f for f in filenames if f.endswith('.model3.json'))
        if not model_files:
            continue

        for mfile in model_files:
            full = os.path.join(dirpath, mfile)
            rel_file = os.path.relpath(full, MODELS_DIR).replace('\\', '/')
            if rel_file in seen_paths:
                continue
            seen_paths.add(rel_file)

            settings = load_json(full)
            if not settings:
                continue

            fr = settings.get('FileReferences') or {}
            moc = fr.get('Moc')
            textures = fr.get('Textures') or []
            motions = fr.get('Motions') or {}

            # 校验必需资源是否存在
            missing = []
            if moc and not os.path.exists(os.path.join(dirpath, moc.replace('/', os.sep))):
                missing.append(moc)
            for t in textures:
                if not os.path.exists(os.path.join(dirpath, t.replace('/', os.sep))):
                    missing.append(t)

            # 文件夹相对 models/ 的路径，用于展示层级
            rel_dir = os.path.relpath(dirpath, MODELS_DIR).replace('\\', '/')
            if rel_dir == '.':
                rel_dir = ''

            # 模型名：优先用 model3.json 文件名（去掉后缀）
            name = mfile[:-len('.model3.json')]

            # 分组：文件夹路径按层级拆开
            parts = [p for p in rel_dir.split('/') if p]

            # 动作统计
            motion_count = sum(len(v) for v in motions.values())
            groups = sorted(k for k, v in motions.items() if v)

            moc_path = os.path.join(dirpath, moc.replace('/', os.sep)) if moc else None
            moc_ver = read_moc_version(moc_path) if moc_path else None

            # 估算体积（moc + 纹理）
            size = 0
            for p in ([moc] if moc else []) + list(textures):
                fp = os.path.join(dirpath, p.replace('/', os.sep))
                try:
                    size += os.path.getsize(fp)
                except OSError:
                    pass

            entries.append({
                'path': rel_dir,                                   # 相对 models/ 的目录
                'file': mfile,                                     # model3.json 文件名
                'name': name,                                      # 模型名
                'group': '/'.join(parts[:-1]) if len(parts) > 1 else '',  # 所属分组
                'parts': parts,                                    # 层级拆解
                'motions': motion_count,
                'motionGroups': groups,
                'textures': len(textures),
                'mocVersion': moc_ver,
                'size': size,
                'missing': missing,
            })

    entries.sort(key=lambda e: (e['group'].lower(), e['name'].lower()))

    out = {
        'version': 1,
        'count': len(entries),
        'models': entries,
    }

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # ---- 输出摘要 ----
    groups = {}
    for e in entries:
        groups.setdefault(e['group'], []).append(e)

    print('已写入 %s' % OUT_FILE)
    print('共发现 %d 个模型，分布在 %d 个分组：' % (len(entries), len(groups)))
    for g in sorted(groups, key=lambda s: s.lower()):
        label = g if g else '(顶层)'
        print('  %-28s %d 个' % (label, len(groups[g])))

    bad = [e for e in entries if e['missing']]
    if bad:
        print()
        print('注意：以下模型缺少资源文件，预览时可能失败：')
        for e in bad:
            print('  %s  ->  缺 %s' % (e['path'] + '/' + e['file'], ', '.join(e['missing'])))

    return 0


if __name__ == '__main__':
    sys.exit(build())
