# Live2D 模型动作预览台

在浏览器里直接预览 `models/` 目录下每个 Live2D 模型的全部动作，可随时切换模型与动画。

纯静态站点，无需构建、无需后端，直接托管到 GitHub Pages 即可访问。

## 本地预览

因为需要通过 `fetch` 读取模型配置，不能用 `file://` 直接打开，起一个本地静态服务即可：

```bash
python -m http.server 8000
```

然后打开 <http://localhost:8000/>。

> 本地不是 `*.github.io` 域名，GitHub API 发现会跳过，页面会直接读 `models/index.json`。
> 想用最新模型列表，先 `python build_index.py` 刷一次索引即可。

## 部署到 GitHub Pages

```bash
git init
git add .
git commit -m "Add Live2D model viewer"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

推送后在仓库页面进入 **Settings → Pages**：

- **Source** 选择 `Deploy from a branch`
- **Branch** 选择 `main`，目录选 `/ (root)`
- 保存，等一两分钟即可通过 `https://<你的用户名>.github.io/<仓库名>/` 访问

仓库根目录已放好 `.nojekyll`，避免 GitHub Pages 的 Jekyll 处理干扰静态资源。

## 新增模型

**丢进去就行。** 把 Live2D 导出好的模型文件夹整个放进 `models/`，刷新页面即可看到：

```
models/
├── my_model/
│   ├── my_model.model3.json
│   ├── my_model.moc3
│   ├── motions/*.motion3.json
│   └── textures/*.png
└── Azue Lane(JP)/         ← 套在子文件夹里也可以
    ├── aaa/
    │   └── aaa.model3.json
    └── bbb/
        └── bbb.model3.json
```

- 目录层级会被自动识别，侧栏按分组折叠展示，切换模型时能看清它属于哪个文件夹
- 动作列表自动从 `.model3.json` 的 `FileReferences.Motions` 读取，无需手工登记
- 一个目录里放多个 `.model3.json`（例如 `bisimai_2`）也能各自被识别成独立模型

### 模型是怎么被发现的

GitHub Pages 不支持列目录，所以页面用三级降级策略：

| 顺序 | 方式 | 说明 |
| --- | --- | --- |
| 1 | **GitHub API** | 在 `*.github.io` 上自动枚举仓库里的 `models/**/*.model3.json`，真正的零操作。仓库需公开，有匿名调用频率限制 |
| 2 | **`models/index.json`** | 由 `build_index.py` 预先扫描生成。离线可用，Pages 上最稳，推荐提交到仓库 |
| 3 | **内置兜底清单** | 写死在 `index.html` 的 `MODELS_FALLBACK`，**只放了一个模型**，仅为保证页面能起来；正常情况下走 1/2 两级 |

侧栏标题旁会显示当前用的是哪种来源（鼠标悬停可看完整说明）。

### 生成索引（推荐）

新增或删除模型后，跑一次就能刷新索引：

```bash
python build_index.py
```

它会递归扫描 `models/`，读取每个模型的 moc 版本、动作数量、纹理数量，顺带检查 `.model3.json` 里引用的文件是否齐全，然后写出 `models/index.json`。

> `models/index.json` 只是加速与离线备份。**没有它页面同样能工作** —— 在 GitHub Pages 上会走 GitHub API 自动发现，本地开发时若没有它则退回内置清单。


## 配置文件 `models/manifest.json`（可选）

只用来**改名字**和**按模型隐藏图层**，模型是否被收录与它无关。文件不存在也没关系。

```json
{
  "alias":   { "my_model": "我的看板娘" },
  "motions": { "idle": "待机", "touch_head": "摸摸头" },
  "hiddenParts": {
    "Azue Lane(JP)/zhala_2/zhala_2.model3.json": ["PartHandLCongxia"]
  }
}
```

- 键可以是模型名、相对 `models/` 的目录路径，或完整的 `路径/文件名`，按顺序匹配。
- `alias` 给模型起中文名；`motions` 把动作文件名映射成可读名称。未登记的项会自动把文件名转成首字母大写的可读形式。
- `hiddenParts` 填**部件**名，`hiddenDrawables` 填**网格**名，可同时使用。
- 有些模型**导出时丢掉了部分网格的「不透明度参数绑定」**，那些网格的静态不透明度是 1，moc3 里没有任何参数能改变它 —— 于是本该只在特定动作里出现的备用图层永久显示，看上去就是「多了一只手」。这属于模型自身的缺陷，任何渲染器都会把它画出来，只能在数据侧指定隐藏谁。
- 名字写错不会报错，只是不起作用。隐藏是每帧重设的（SDK 每次 update 都会按绑定重算网格不透明度，会覆盖手工写进去的 0）。


## 界面功能

页面刻意做得很轻：**没有动作列表**，模型一载入就自动把全部动作依次播完，
打开就是在动的看板娘，不需要点任何东西。底部「列表循环」默认开启 ——
当前模型的全部动作播完后会**自动切到模型列表里的下一个模型**，从头到尾轮播下去。
只想反复看某一个模型的话，把「列表循环」关掉即可（那时只在本模型内循环动作）。

> 「列表循环」里的「列表」指的是**侧栏那个模型列表**，而且是**你眼前看到的那一份** ——
> 搜索框里筛出了几个模型，轮播范围就是这几个；当前模型被筛掉时会从可见列表的第一个重新开始。

| 功能 | 说明 |
| --- | --- |
| 模型列表 | 左侧按文件夹分组折叠展示，可搜索，点击切换模型 |
| 自动依次播完全部动作 | 载入模型后从第 1 个动作自动往下播，播完最后一个回到第 1 个，无限循环 |
| 播放控制 | 播放 / 暂停 |
| 速度 | 0.1× ~ 3× 变速播放 |
| 缩放 | 20% ~ 400%，也可用滚轮；拖动画面可平移，双击复位 |
| 舞台背景 | 顶栏三档切换：**浅色 / 深色 / 黑色**。黑色舞台背景最干净，看模型轮廓、透明边缘和发光特效时最清楚 |
| **全屏播放** | 顶栏右上角的图标，一键让整个屏幕只剩模型（浏览器原生全屏 + 隐藏全部面板） |
| GitHub 图标 | 顶栏右上角，点击打开本仓库 |
| 显示网格 | 叠加参考网格，方便定位 |
| 列表循环 | 默认开启。开：当前模型全部动作播完后自动切到**模型列表**里的下一个（到末尾回到第一个），一直轮播下去；关：只在本模型内循环动作，不切模型 |
| 下载模型 | 把当前模型打包成 zip 下载，解压后直接丢进 `models/` 就能用 |
| **本地预览** | 侧栏左下角的按钮。点开一个对话框，里面写明上传要求，**选择文件**或**把压缩包直接拖进去**都能用；浏览器内解压校验后**直接放进预览**，不用先放进 `models/` 也不用刷新页面。详见下一节 |
| 快捷键 | `←` `→` 跳到上/下一个动作、`空格` 播放/暂停、`R` 重播当前、`T` 循环切换舞台背景、`F` 全屏、`Esc` 退出全屏 |

舞台左上角的信息条会显示当前是第几个动作、叫什么名字、多长。

### 下载模型（打包成 zip）

点「下载模型」，页面会顺着 `model3.json` 的 `FileReferences` 把 moc3、贴图、物理、动作、
语音等**所有被引用的文件**抓下来，打成一个 zip：

```
zhala_2.zip
└─ zhala_2/                      ← 顶层文件夹用模型目录名，解压即用
   ├─ zhala_2.model3.json
   ├─ zhala_2.moc3
   ├─ textures/*.png
   ├─ motions/*.motion3.json
   └─ sounds/*.mp3
```

### 本地预览（上传模型压缩包）

侧栏左下角（模型列表下面那条通栏按钮）的 **「本地预览」**，可以上传一个模型压缩包，
**在浏览器里解压、校验、直接上架**，不用先把文件放进 `models/`、也不用刷新页面。
整个过程**不会把任何字节传到服务器** —— 解压出来的文件全部变成内存里的 blob，页面直接从内存取。

点它会弹出一个对话框，**上传要求就写在对话框里**（格式、体积、模型版本、必需 / 可选文件），
进来有三种方式：

- 点对话框里的虚线框 → 打开系统文件选择框
- **把压缩包直接拖到对话框上**（拖到要求清单那一片也算，不要求精准落在虚线框里）
- 键盘：打开对话框后焦点在虚线框上，回车或空格同样能选文件

处理进度（解压 / 校验）显示在对话框里；校验不通过时**对话框不关**，原因直接写在对话框内，
可以立刻换一个文件再试。`Esc` / 点 `×` / 点遮罩都能关掉它。

侧栏底部会出现一个 **「本地模型」** 分组，里面的条目带 × 可以移除（只从列表移除，不会删你本地文件）。
本地模型只存在于本次会话，刷新页面就没了。

**哪些包能用：**

| 检查项 | 不满足时 |
| --- | --- |
| 是合法的 zip（不是 ZIP64、没有密码、压缩方式是 store 或 deflate） | 拒绝 |
| 里面有 `.model3.json` | 拒绝 |
| `model3.json` 是合法 JSON，且有 `FileReferences.Moc` | 拒绝 |
| moc3 文件存在、文件头是 `MOC3`、版本不高于页面 Core 支持的 5.0 | 拒绝 |
| 有贴图，且每张贴图都存在、都是能识别的图片格式 | 拒绝 |
| 动作 / 物理 / 姿势 / 表情 / 语音 | 缺了就裁掉，仍然放行（并提示） |

**不合规的包一个都进不去**：模型列表和当前正在预览的模型**完全不变**，
只在对话框里和舞台上各弹一条说明原因的提示（比如「压缩包里缺少 1 张贴图：xxx.png」）。

几个实现上的注意点，改动这块代码前值得先看一眼：

- zip 的尺寸一律以**中央目录**为准。很多打包工具会写「数据描述符」（本地头里尺寸填 0），
  只读本地头会得到 0 字节的文件。
- 解压 deflate 用浏览器原生的 `DecompressionStream('deflate-raw')`，没有引任何压缩库。
- 文件名没标 UTF-8 时按 GBK 兜底（Windows 自带「压缩到 zip」在老系统上就是这么写的）。
- `model3.json` 里每个文件引用都会被换成该文件自己的 **blob: 绝对地址**，因为 blob URL
  之间没法互相解析相对路径。
- ⚠️ SDK 的 `ModelSettings.resolveURL()` 用的是打包进来的 Node `url` 兼容层，
  它会把 `blob:http://…` 解析成 `blob:http//…`（吃掉冒号）→ 贴图和 moc3 全部加载失败。
  页面启动时打了一个补丁：**已经是绝对地址的直接原样返回**（见 `patchModelSettingsResolveURL`）。
- 对话框挂在舞台内部而不是 `body` 上（全屏时舞台才是整屏），因此它的 `pointerdown` / `wheel`
  要拦掉冒泡，否则会被舞台当成「拖动模型 / 缩放」。

### 直接用链接指定模型

地址栏支持 `?model=` 参数，方便分享和调试：

```
http://localhost:8000/?model=Azue%20Lane(JP)/zhala_2/zhala_2.model3.json
```

`model` 的值可以是模型的完整 key（`相对路径/文件名`）、相对 `models/` 的目录路径，或模型名。
链接优先于本地上次记住的模型。


## 目录结构

```
.
├── index.html                   预览页面（全部逻辑）
├── build_index.py               扫描 models/ 生成 index.json
├── tmp/                         本机测试 / 临时脚本（已 git 忽略，不进 Pages）
│   ├── _regress.js              无头 Chrome 回归测试（93 项）
│   ├── _probe_responsive.js     多端适配专项测试（52 项）
│   ├── _probe_ctrlwrap.js       底部控制条换行专项测试（38 项）
│   ├── _probe_cycle.js          列表循环专项测试（22 项）
│   ├── _probe_local.js          本地预览上传 zip 专项测试（118 项）
│   ├── _probe_dragreal.js       本地预览真实拖拽专项 · CDP 派发（13 项）
│   └── _probe_zip.js            下载模型 zip 打包专项测试（16 项）
├── assets/
│   ├── live2dcubismcore.min.js  Live2D Cubism Core（官方运行时）
│   ├── pixi.min.js              PIXI.js v6
│   └── cubism4.min.js           pixi-live2d-display 的 Cubism 4 渲染层
├── models/
│   ├── index.json               自动生成的模型索引（可提交）
│   ├── manifest.json            名称映射 + 按模型隐藏图层（可选，手工维护）
│   └── <模型目录>/
└── .nojekyll
```

> `tmp/` 下的脚本都用 `const ROOT = path.join(__dirname, '..')` 指回项目根，
> 所以**必须从项目根执行**（`node tmp/xxx.js`），不能 `cd tmp` 再跑。
>
> 它们需要 `ws`（脚本内用 `NODE_PATH` 指向工作区里的 node_modules 即可），
> 以及 `C:\Program Files\Google\Chrome\Application\chrome.exe`。

## 验收

七套测试都用无头 Chrome（`ws` + `C:\Program Files\Google\Chrome\Application\chrome.exe`）跑，
从项目根依次执行即可（Git Bash / WSL 下用下面的一行命令）：

```bash
export NODE_PATH="$HOME/.workbuddy-ai/binaries/node/workspace/node_modules"
NODE="$HOME/.workbuddy-ai/binaries/node/versions/22.22.2-2/node.exe"
for s in _regress _probe_responsive _probe_ctrlwrap _probe_cycle _probe_local _probe_dragreal _probe_zip; do
  "$NODE" "tmp/$s.js" || break
done
```

| 脚本 | 断言数 | 覆盖 |
| --- | --- | --- |
| `tmp/_regress.js` | 93 | 回归：布局 / 全屏 / 播放 / 循环动作 / 速度基准 |
| `tmp/_probe_responsive.js` | 52 | 多端：5 视口 + 抽屉开合 + 真实 touch→pointer 链 |
| `tmp/_probe_ctrlwrap.js` | 38 | 手机控制条换行显示全、不横向溢出 |
| `tmp/_probe_cycle.js` | 22 | 列表循环：显示顺序 ≠ 原始顺序、换模型、绕回 |
| `tmp/_probe_local.js` | 118 | 本地预览上传：选文件 / 12 类坏包全拒 / 解压上架 / 权重到 1 |
| `tmp/_probe_dragreal.js` | 13 | 本地预览真实拖拽：`Input.dispatchDragEvent` 从浏览器层派发，文件由浏览器填 `dataTransfer.files` |
| `tmp/_probe_zip.js` | 16 | 下载模型：手写 zip 结构 / 逐字节与源一致 / 系统解压可用 |

合计 **352 项断言，0 失败**。

> ⚠️ `_probe_dragreal.js` 依赖 Chrome 的 `Input.dispatchDragEvent`（拖拽模拟）能力，
> 该能力随 Chrome 版本变化；若某版本把它整组 `SKIP`，前六套仍是本地预览的完整保证，
> 换 Chrome 后需复验这一套。

## 说明

- 渲染依赖 `Live2D Cubism Core`，其使用需遵守 [Live2D 专有软件许可协议](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html)。
- 请确保你对所使用的 Live2D 模型拥有相应的展示与分发授权。
- 本项目依赖的第三方库：PIXI.js（MIT）、pixi-live2d-display（MIT）。
