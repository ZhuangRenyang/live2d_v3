#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
models_tool.py —— Live2D 模型目录的「扫描 / 索引 / 增量打包准备」一体化工具。

它是 models/ 目录的唯一权威：既生成预览页要读的 models.json，
又负责发布时「哪些是新增的、该打哪几个包」。

用法
----
    python models_tool.py                       # 常规：扫 models/ → 根目录 models.json
    python models_tool.py -job release          # 内部：准备增量发布（见下）
    python models_tool.py -job release -plan    # 只算不复制/不落盘，把计划打成 JSON

（`-job release` 是给 CI 用的：**只做"准备"——识别新增、把新增模型整目录复制到
  live2d_v3_models_new/、重写 models.json**。真正打 zip、发 Release 交给工作流，
 因为那两件事涉及 `zip` / `gh` 这类外部命令，Python 重写一遍不划算。）

`-job release` 会往 stdout 打一段 JSON（工作流用 `tee` 存成文件再读，不用临时 SQLite 之类）：

    {"total": 45, "new": 2, "gone": 1, "first": false, "grouped": false,
     "new_models": ["Celeste - free", "用户上传/新模型"],
     "gone_models": ["Azue Lane(JP)/gone_model/m.model3.json"]}

`-plan` 时不会复制文件、也不会重写 models.json（CI 想先看看再决定时用得上）。

为什么基线是 models.json 而不是单独一份清单
------------------------------------------
models.json 一物两用：**预览页靠它发现模型，发布流程靠它做增量**。
以前这里还维护过一份 models.txt 专做增量基线，两套代码两份清单迟早对不上，已废弃。
于是「把新的 models.json 提交回仓库」这一步就是基线回写 —— 它失败了，
下一轮会把同一批模型再当成新增重发一遍。
"""

import argparse
import json
import os
import shutil
import struct
import sys

# 跨平台：Windows 控制台默认编码可能是 GBK/CP936，Linux 在 C locale 下是 ASCII，
# 都会让含中文/日文的 print 抛 UnicodeEncodeError（尤其 CI 里 stdout 被重定向时）。
# 统一把标准输出/错误流改成 UTF-8；老解释器没有 reconfigure 就跳过。
# ⚠️ 只 reconfigure，不动 sys.argv —— 老代码用 sys.argv 取命令行参数，
#    在 Windows 上会把中文参数按 ANSI 解码成乱码；现在走 argparse 就没这问题了。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, 'models')
OUT_FILE = os.path.join(HERE, 'models.json')
NEW_MODELS_DIR = os.path.join(HERE, 'live2d_v3_models_new')

MOC_VERSION_NAMES = {1: '3.0', 2: '3.3', 3: '4.0', 4: '4.2', 5: '5.0'}

# 扫描时忽略的目录名（小写比较）。'tmp' 一并忽略（编辑器/临时目录）。
# ⚠️ 这里按「目录名」判断，而不是拿 os.sep 去拼子串匹配完整路径 ——
#   老写法 `os.sep + 'tmp' in dirpath` 在项目本身位于 /tmp（Linux）或 C:\tmp（Windows）
#   时会把**每个**目录都判成临时目录，结果一个模型都扫不到。
SKIP_DIRS = {'node_modules', '.git', '__pycache__', '.vs', '.idea', 'tmp'}


# ── 扫描 ────────────────────────────────────────────────────────────────

def read_moc_version(path):
    """读取 moc3 文件头里的版本号，返回如 '3.0'；读不到返回 None。

    moc3 头是：前 4 字节 ASCII 'MOC3'，紧接着一个 little-endian uint32 版本号。
    1→3.0 / 2→3.3 / 3→4.0 / 4→4.2 / 5→5.0（Cubism 官方 MocVersion 枚举）。
    """
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
    """读 JSON；解析失败只警告、返回 None（不因为一个坏模型整轮失败）。

    用 utf-8-sig：容忍 Windows 工具写出的 BOM（文件无 BOM 时与 utf-8 完全等价）。
    """
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print('  [skip] 无法解析 %s: %s' % (path, e))
        return None


def norm_key(path, file):
    """把 (目录, 文件名) 归一成基线键：统一 '/' 分隔、不留首尾斜杠。

    ⚠️ 必须归一，否则 'a/b' + 'x.model3.json' 与 'a\\b' + 'x.model3.json'
    会被当成两个不同的模型（Windows 上 os.path.relpath 给的是反斜杠）。
    """
    return (str(path) + '/' + str(file)).replace('\\', '/').strip('/')


def scan_models():
    """扫描 models/ 目录，返回模型条目列表；models/ 不存在时返回 None。

    一个「模型」= 一个 `*.model3.json` 文件（就页面加载时要找的那个），
    它所在目录就是模型目录，里面可以再套任意层级。
    """
    if not os.path.isdir(MODELS_DIR):
        print('找不到 models 目录：%s' % MODELS_DIR)
        return None

    entries = []
    seen_paths = set()

    for dirpath, dirnames, filenames in os.walk(MODELS_DIR):
        dirnames[:] = sorted(d for d in dirnames if d.lower() not in SKIP_DIRS)

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

            # 校验必需资源是否存在（字段名与预览页的 missing 保持同口径）
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

    # ⚠️ 排序键必须与预览页（assets/js/app.js）和「贡献模型」上传时的归并规则一致，
    #    否则同一份内容在三处会排出不同顺序，git diff 里反复出现无意义的重排。
    entries.sort(key=lambda e: (e['group'].lower(), e['name'].lower()))
    return entries


# ── 索引读写 ────────────────────────────────────────────────────────────

def read_index_keys(path):
    """读一份索引，返回它记录的所有模型键（path/file 归一后的集合）。

    文件不存在或解析失败都返回空集合 —— 调用方据此判断"没有基线"。
    """
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return set()
    keys = set()
    for e in data.get('models', []):
        k = norm_key(e.get('path', ''), e.get('file', ''))
        if k:
            keys.add(k)
    return keys


def load_existing_index():
    """读**仓库当前这份** models.json 里的模型键集合（作为增量基线）。"""
    return read_index_keys(OUT_FILE)


def load_committed_index():
    """读 **git 里已提交的那一版** models.json 的模型键集合。

    ⚠️ 必须走 git，不能直接读工作区文件：`-job release` 跑起来的时候，
    工作区的 models.json 可能**已经被本次扫描重写过了**（或者本来就是脏的），
    拿它当"上一版"必然算不出"已消失"。
    读不到（首次运行、或文件还没入库）就返回空集合。
    """
    import subprocess
    try:
        blob = subprocess.run(
            ['git', 'show', 'HEAD:models.json'],
            cwd=HERE, capture_output=True, check=False,
        )
        if blob.returncode != 0:
            return set()
        data = json.loads(blob.stdout.decode('utf-8-sig'))
    except (OSError, ValueError):
        return set()
    keys = set()
    for e in data.get('models', []):
        k = norm_key(e.get('path', ''), e.get('file', ''))
        if k:
            keys.add(k)
    return keys


def save_index(entries):
    """将扫描结果写入 models.json（原子替换）。"""
    out = {
        'version': 1,
        'count': len(entries),
        'models': entries,
    }
    # newline='\n'：Windows 文本模式默认把 \n 写成 \r\n，会让同一份清单在
    # Windows 与 Linux 上生成的字节不同（git 里反复出现无意义的整文件 diff）。
    # 固定成 \n，两个平台的产物完全一致。
    #
    # 先写同目录下的临时文件再 os.replace：os.replace 是原子操作，
    # 中途被打断也不会留下半截 JSON（否则页面读到半个文件、git 提交进去也可能）。
    tmp = OUT_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT_FILE)


# ── 增量发布准备 ────────────────────────────────────────────────────────

def group_by_top_dir(rel_dirs):
    """把一批「相对 models/ 的模型目录」归并成互不嵌套的顶层目录。

    ⚠️⚠️ 这一步以前在工作流里用 bash 做（`awk -F/ '{print $1}'`），是**错的**：
    那样只会取每个路径的第一段，于是同一个顶层目录下的**多个新增模型**会被
    复制好几遍（目录名带空格/中文时还更容易出错）。
    这里按"把每个模型目录的各层前缀都记下来，再丢掉被其它项包含的那些"来归并。

        ['Celeste - free', 'Azue Lane(JP)/a', 'Azue Lane(JP)/b']
            → ['Azue Lane(JP)', 'Celeste - free']        # Azue Lane 只复制一次

    返回的路径里仍可能有**嵌套**关系（例如同时返回 'X' 与 'X/Y'）。
    这没关系：copytree 是按顺序复制到各自的相对位置，先 X 后 X/Y 时
    X 已经把 X/Y 的内容带过去了，第二次再拷只是覆盖同样的内容。
    """
    items = []
    for r in rel_dirs:
        r = str(r).replace('\\', '/').strip('/')
        if r and r not in items:
            items.append(r)

    keep = []
    for r in sorted(items, key=lambda s: (s.count('/'), s)):
        # r 是某个已保留项的子路径 → 已经被它覆盖，不用再单独复制一次
        if any(r == k or r.startswith(k + '/') for k in keep):
            continue
        keep.append(r)
    return sorted(keep)


def copy_new_models(entries, existing_keys, plan_only=False, prepare=True):
    """把不在 existing_keys 里的模型**整个目录**复制到 NEW_MODELS_DIR。

    返回真正要复制（或计划要复制）的「相对 models/ 的模型目录名」列表 ——
    Release 说明和增量包都以此为准，保证「说了什么」和「装了什么」一致。

    ⚠️ 复制的是**模型目录**（model3.json 所在目录）而不是整个分组目录：
    一个分组下既有新增模型也有老模型时，复制整个分组会把老模型也塞进增量包。
    """
    rel_dirs = []
    for e in entries:
        if norm_key(e['path'], e['file']) not in existing_keys:
            rel_dirs.append(e['path'])
    rel_dirs = sorted(set(rel_dirs))

    if plan_only or not prepare:
        return rel_dirs

    # 目标目录由 clean_pack_artifacts 清掉后新建；这里兜一层（单独调用时不至于失败）
    if not os.path.isdir(NEW_MODELS_DIR):
        os.makedirs(NEW_MODELS_DIR, exist_ok=True)

    for rel_dir in group_by_top_dir(rel_dirs):
        src = os.path.join(MODELS_DIR, rel_dir.replace('/', os.sep))
        dst = os.path.join(NEW_MODELS_DIR, rel_dir.replace('/', os.sep))
        if os.path.isdir(src):
            # dirs_exist_ok：嵌套项（'X' 与 'X/Y'）会先后落到同一棵树下，
            # 不加这个参数第二次就会 FileExistsError。
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print('  复制：%s' % rel_dir)
        else:
            print('  [skip] 目录不存在：%s' % rel_dir)

    return rel_dirs


def clean_pack_artifacts():
    """删掉上一次 `-job release` 留下的产物。

    ⚠️ 必须包含在 `-job release` 里，而且要在复制**之前**删：
    `copytree(dirs_exist_ok=True)` 只覆盖、不清理，上一次跑剩下来的模型会留在
    目录里，被打进一个名叫「新增」却装着上一轮内容的包。
    """
    for d in (NEW_MODELS_DIR, os.path.join(HERE, '_pack_new')):
        if os.path.isdir(d):
            shutil.rmtree(d)


# ── 输出 ────────────────────────────────────────────────────────────────

def print_summary(entries):
    """打印扫描摘要。"""
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


def emit_plan(result):
    """把发布计划打成一行 JSON（工作流读它，比自己 grep 输出稳）。

    放在最后一行、且**不带缩进**：`tee` 存下来的文件里最后一行就是计划，
    前面的人类可读日志照常出现在 CI 日志里。
    """
    sys.stdout.flush()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def release_plan(entries, plan_only=False):
    """算出这一轮发布需要的一切，返回给调用方打 JSON。

    ⚠️ **首次运行（仓库里压根没有 models.json）不复制任何东西**：
    没有基线 → 全部模型都会被判成"新增" → 复制出来的是完整的一份 models/，
    几百兆做一次毫无意义的拷贝（调用方本来也不会据此发"增量包"）。
    所以先判 first，再决定要不要复制。
    """
    first = not os.path.isfile(OUT_FILE)
    existing = load_existing_index() if not first else set()
    committed = load_committed_index()

    new_models = [] if first else copy_new_models(entries, existing, plan_only=plan_only,
                                                  prepare=not plan_only)
    current_keys = {norm_key(e['path'], e['file']) for e in entries}

    return {
        'first': first,
        'total': len(entries),
        'new': len(new_models),
        'new_models': new_models,
        'gone': len(committed - current_keys),
        'gone_models': sorted(committed - current_keys),
    }


def build_parser():
    ap = argparse.ArgumentParser(
        prog='models_tool.py',
        description='扫描 models/ 生成 models.json，并为增量发布准备文件。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python models_tool.py\n'
               '  python models_tool.py -job release\n'
               '  python models_tool.py -job release -plan\n',
    )
    ap.add_argument('-job', choices=['release'], default=None,
                    help="release = 增量发布准备（识别新增 + 复制到 live2d_v3_models_new/）")
    ap.add_argument('-plan', action='store_true',
                    help='只计算、不复制文件也不写 models.json（需配合 -job release）')
    # 兼容老写法 `python models_tool.py release`（曾经是位置参数）
    ap.add_argument('legacy_job', nargs='?', default=None,
                    help=argparse.SUPPRESS)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    job = args.job

    # 老写法兼容：`python models_tool.py release` ≡ `-job release`
    if job is None and args.legacy_job == 'release':
        job = 'release'

    entries = scan_models()
    if entries is None:
        return 1

    if job == 'release':
        # ⚠️ 先清产物再复制，顺序不能反（见 clean_pack_artifacts 的注释）
        if not args.plan:
            clean_pack_artifacts()
        plan = release_plan(entries, plan_only=args.plan)
        if args.plan:
            print('计划模式：不复制文件、不写 models.json')
        print('新增模型 %d 个，已消失 %d 个' % (plan['new'], plan['gone']))
        for m in plan['new_models']:
            print('  新增: %s' % m)
        for m in plan['gone_models']:
            # CI 里这行会被 GitHub 渲染成一条警告 —— 索引里有、仓库里没有
            print('::warning::已消失: %s' % m)
        if not args.plan:
            save_index(entries)
            print_summary(entries)
        emit_plan(plan)
        return 0

    save_index(entries)
    print_summary(entries)
    if args.plan:
        print('计划模式：仅扫描，未做任何发布准备')
    # 非发布模式也打一行 JSON，免得调用方要分两种情况解析
    emit_plan({
        'first': not os.path.isfile(OUT_FILE),
        'total': len(entries),
        'new': 0, 'new_models': [],
        'gone': 0, 'gone_models': [],
    })
    return 0


if __name__ == '__main__':
    sys.exit(main())
