# Live2D 模型动作预览台

在浏览器里直接预览 `models/` 目录下每个 Live2D 模型的全部动作，可随时切换模型与动画。

纯静态站点，无需构建、无需后端，直接托管到 GitHub Pages 即可访问。

## 本地预览

因为需要通过 `fetch` 读取模型配置，不能用 `file://` 直接打开，起一个本地静态服务即可：

```bash
python -m http.server 8000
```

然后打开 <http://localhost:8000/>。

> 页面直接读取项目根目录下的 `models.json`（由 `models_tool.py` 扫描 `models/` 生成）。
> 加了新模型后，先 `python models_tool.py` 刷一次清单即可。

## 部署到 GitHub Pages

页面与模型**分两个分支存放**，这是刻意的：

| 分支 | 放什么 | 体积 |
|---|---|---|
| `master` | 全部代码 + `models/` + `models.json` | 200MB+ |
| `gh-pages` | **只有页面壳**：`index.html`、`assets/`、`.nojekyll`、`models.json` | ~1MB |

Pages 从 `gh-pages` 发布，模型由页面从 `master` 的 raw / jsDelivr 读取。

**为什么要拆**：如果页面和模型同在发布分支上，那么**每次改动都会让 Pages 重新构建整站** ——
往 `models/` 加一个模型、甚至只是刷新一下 20KB 的 `models.json`，都要等它把 200 多兆的产物
重新同步一遍。拆开之后：

- **加模型 / 刷新清单** → 只动 `master`，`gh-pages` 一个字节都不用变，页面刷新即生效
- **改页面代码** → 由 `.github/workflows/pages.yml` 自动把页面壳重发到 `gh-pages`（秒级）
- **想手动重发一次** → 仓库 **Actions → 左侧「发布页面到 gh-pages」→ Run workflow**，
  分支选 `master`。工作流是**幂等**的：每轮都重建产物 + orphan 强推，跑几次结果都一样。

推送后在仓库页面进入 **Settings → Pages**：

- **Source** 选择 `Deploy from a branch`
- **Branch** 选择 `gh-pages`，目录选 `/ (root)`
- 保存，等一两分钟即可通过 `https://<你的用户名>.github.io/<仓库名>/` 访问

> ⚠️⚠️ **顺序别搞反：先让页面壳进 `gh-pages`，再切 Pages 的分支设置。**
> 分离之前的老页面是按**相对路径**找 `models/` 的，而 `gh-pages` 上**没有** `models/` ——
> 先切设置、再发页面，中间那段时间站点上模型全部 404（列表还是 42 个，点谁谁失败）。
> 正确顺序：① 把页面代码提交到 `master`（工作流会自己发；也可以手动跑一次确认）
> → ② 确认 `gh-pages` 上是**新版**页面 → ③ 再去 Settings 把分支切成 `gh-pages`。

`gh-pages` 分支由工作流自动创建并维护，**不要手工往上面推东西**（每轮都会被覆盖）。
仓库根目录已放好 `.nojekyll`，避免 GitHub Pages 的 Jekyll 处理干扰静态资源。

> ⚠️ 工作流检出时用了 **sparse-checkout**（只取 `index.html` / `assets/` / `.nojekyll` /
> `models.json`）+ `fetch-depth: 1`。不这么做的话，一个「发页面」的活儿会把
> master 上 263MB 模型 + 190MB 历史全拉下来 —— 而它只需要 1.1MB。
> **改动那份 sparse 清单时，要同时改「组装」步骤里的 `cp` 清单**（两处必须一致）；
> 少写一个会因为检出守卫直接失败，不会静默出错。

> ⚠️ 页面里的模型地址写在 `assets/js/app.js` 顶部的 `rawBaseOf()` / `cdnBaseOf()`。
> 把仓库改名或换用户名后，改那两处的 `REPO_OWNER` / `REPO_NAME` 即可
> （**默认主用 jsDelivr、备用 raw**，主源失败会自动切备源；
> 用 `?src=raw` / `?src=cdn` 可强制指定，方便排查）。
>
> **两处都会自动切备源**：① 读 `models.json` 时探到主源不可用；
> ② 模型资源取不到时（例如 jsDelivr 整段抽风或 raw 对批量请求限速，
> 而 20KB 的清单恰好取得到）——
> 这种情况下列表能列出来但每个模型都载入失败，所以载入失败会**再切一次**重试。


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

浏览器不允许直接列目录，所以页面**直接读取项目根目录下的清单文件 `models.json`**，读不到时才退回内置兜底清单：

| 顺序 | 方式 | 说明 |
| --- | --- | --- |
| 1 | **`models.json`** | 位于**仓库根目录**，由 `models_tool.py` 扫描 `models/` 生成。直接读文件，不限流、任意静态托管、离线可用，推荐提交到仓库 |
| 2 | **内置兜底清单** | 写死在脚本里的 `MODELS_FALLBACK`，**只放了一个模型**，仅为保证页面能起来；正常情况下走第 1 级 |

侧栏标题旁会显示当前用的是哪种来源（鼠标悬停可看完整说明）。

> **页面与模型分居两个分支**（见上面「部署到 GitHub Pages」）。页面部署在 `gh-pages` 上时，
> 这一级会去 `master` / `main` 的 jsDelivr / raw 地址取 `models.json` 与 `models/`；
> 本机起服务时则走相对路径。侧栏标题旁的来源标注会写出当前是 `jsDelivr` / `raw` / 本机
> 以及命中的分支，鼠标悬停能看到完整地址 —— 排查「模型没更新」时先看这里。
>
> **默认走 jsDelivr**（国内节点多、不限速）。代价是 jsDelivr 对分支引用（`@master`）
> 本身有缓存，刚推上去的模型可能得等几分钟到几小时才出现 —— 追新模型时用
> `?src=raw` 绕开缓存。
>
> **分支不用你操心**：GitHub 新建仓库默认分支叫 `main`，老仓库多是 `master`，
> 页面**两个都试**（先 `master` 后 `main`），谁先取到 `models.json` 就用谁。
> 探明分支之后候选源会收窄成「同一分支的 jsDelivr → raw」两项，
> 这样「主源半死时换备用源」那唯一一次重试仍然是**换源**而不是换分支。

### 生成清单（推荐）

新增或删除模型后，跑一次就能刷新清单：

```bash
python models_tool.py                 # 扫描 models/ → 根目录 models.json
python models_tool.py -job release    # 发布准备（识别新增 + 复制待发布模型，CI 用）
python models_tool.py -job release -plan   # 只看计划，不落盘
```

它会递归扫描 `models/`，读取每个模型的 moc 版本、动作数量、纹理数量，顺带检查 `.model3.json` 里引用的文件是否齐全，然后在**项目根目录**写出 `models.json`。

`-job release` 是给发布流程用的：它会拿 `models.json` 当基线，把**新增**的模型整个目录复制到 `live2d_v3_models_new/`，再把新清单写回 `models.json`（这就是下一轮的基线）。打 zip、发 Release 由 `.github/workflows/models-release.yml` 负责 —— 那两件事靠 `zip` / `gh` 这类外部命令，Python 重写一遍不划算。

> 脚本每次都会在最后一行打一段 JSON（`total` / `new` / `gone` / `new_models`），CI 读它拿结果，不用去解析人类可读的日志。
>
> `models.json` 是页面唯一的模型发现来源。**没有它页面会退回内置兜底清单**（只有一个模型）。加完模型记得重新跑一次脚本。


## 隐藏多余图层

有些模型**导出时丢掉了部分网格的「不透明度参数绑定」**：那些网格的静态不透明度是 1，
moc3 里没有任何参数能改变它 —— 于是本该只在特定动作里出现的备用图层永久显示，
看上去就是「多了一只手」。这属于模型自身的缺陷，任何渲染器都会把它画出来，
只能在数据侧指定隐藏谁。

页面里在**右侧「部件面板」**里调：把对应部件 / 网格的不透明度拉到 0 即可，
要留档就点「导出配置」，会下载一份 `<模型名>.hidden.json`。
面板的覆盖是**临时**的，切换模型即失效；隐藏每帧重设
（SDK 每次 update 都会按绑定重算不透明度，会覆盖手工写进去的 0）。

> 以前这一层由手工维护的 `models/manifest.json` 配置（`alias` / `motions` / `hiddenParts`）。
> 那份文件已经删掉，页面不再读取任何外部隐藏配置，也**不再有那个 404 请求**。


## 界面功能

页面刻意做得很轻：**没有动作列表**，模型一载入就自动把全部动作依次播完，
打开就是在动的看板娘，不需要点任何东西。底部「列表循环」默认**关闭** ——
当前模型的全部动作播完后会回到第 1 个，无限循环；打开它就**自动切到模型列表里的
下一个模型**，从头到尾轮播下去。
只想反复看某一个模型的话，保持「列表循环」关闭即可（这时只在本模型内循环动作）。

> 「列表循环」里的「列表」指的是**侧栏那个模型列表**，而且是**你眼前看到的那一份** ——
> 搜索框里筛出了几个模型，轮播范围就是这几个；当前模型被筛掉时会从可见列表的第一个重新开始。

| 功能 | 说明 |
| --- | --- |
| 模型列表 | 左侧按文件夹分组折叠展示，可搜索，点击切换模型。**桌面端默认悬停自动展开**：鼠标移到页面左边缘（≤ 8px）**并停留 1 秒**才滑出 —— 只是划过去不会弹，蹭到屏幕最左边、或者从别的窗口切回来鼠标恰好落在边上都不会跳出来；鼠标移出侧栏则 1.5 秒后自动折叠（收起可以慢一点）；顶栏汉堡一直可用。点侧栏头的「📌 固定」按钮可关掉悬停行为，只用汉堡控制（顶栏汉堡桌面 + 手机都显示，手机没有悬停可言所以固定按钮在手机端不显示） |
| 自动依次播完全部动作 | 载入模型后从第 1 个动作自动往下播，播完最后一个回到第 1 个，无限循环 |
| 播放控制 | 播放 / 暂停 |
| 速度 | 0.1× ~ 3× 变速播放 |
| 缩放 | 20% ~ 400%，也可用滚轮；拖动画面可平移，双击复位 |
| 舞台背景 | 顶栏三档切换：**浅色 / 深色 / 黑色**。黑色舞台背景最干净，看模型轮廓、透明边缘和发光特效时最清楚 |
| **全屏播放** | 顶栏右上角的图标，一键让整个屏幕只剩模型（浏览器原生全屏 + 隐藏全部面板） |
| GitHub 图标 | 顶栏右上角，点击打开本仓库 |
| 显示网格 | 叠加参考网格，方便定位 |
| 列表循环 | 默认关闭。关：只在本模型内循环动作，不切模型。开：当前模型全部动作播完后自动切到**模型列表**里的下一个（到末尾回到第一个），一直轮播下去 |
| 下载模型 | 把当前模型打包成 zip 下载，解压后直接丢进 `models/` 就能用 |
| **本地预览** | 侧栏左下角的按钮。点开一个对话框，里面写明上传要求，**选择文件**或**把压缩包直接拖进去**都能用；浏览器内解压校验后**直接放进预览**，不用先放进 `models/` 也不用刷新页面。详见下一节 |
| **添加外部模型源** | 侧栏头「模型列表」右边的 **＋** 按钮。粘一条别人仓库的 `models.json` 链接（raw / jsDelivr 均可），自动把那个仓库的模型**按用户名 + 它自己的目录层级**加进左侧列表，可一键移除整组。**填过的链接会记住**（刷新后自动预填）。详见「添加外部模型源」一节 |
| 快捷键 | `←` `→` 跳到上/下一个动作、`空格` 播放/暂停、`R` 重播当前、`T` 循环切换舞台背景、`F` 全屏、`P` 开关右侧部件面板（右下角按钮点不到时用键盘开）、`Esc` 逐级关闭：贡献对话框 → 本地预览对话框 → 添加外部源对话框 → 右抽屉 → 全屏 → 侧栏（一次只关一层） |

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

### 贡献模型：把预览成功的模型传回仓库

侧栏底部「贡献模型」（**没有本地预览成功的模型时它是灰的**）。上传走 GitHub Git Data API：
每个文件单独建 blob，然后**一个 tree + 一个 commit + 一次 ref 更新**，
不会出现「传一半」的中间状态。

**传到哪个仓库，由对话框自己判断：**

| 情况 | 行为 |
| --- | --- |
| 当前在 `*.github.io`（GitHub Pages）上 | **自动识别**出所在仓库，锁定成只读一行，不让改 |
| 地址栏带 `?repo=用户名/仓库名` | 按它来（本地开发 / 自动化用） |
| 推不出来（本地预览 / 自定义域名） | 出现输入框，**由你填**；会预填项目自带的仓库当建议值，但提示语是「请确认」而不是「已选定」 |

⚠️ **绝不拿建议值当结论静默上传** —— 传错仓库等于把几十 MB 公开推到别人家。
推不出来又没填就点上传，会直接报错拦下来。

**上传时一并更新 `models.json`**：先把仓库根的 `models.json` 拉下来，把新模型按
`models_tool.py` 的字段格式并进去（`path` / `file` / `name` / `group` / `parts` / `motions` /
`motionGroups` / `textures` / `mocVersion` / `size` / `missing`，排序规则也一致），
再和模型文件放进**同一个 commit**。这样不用等下一次跑 `models_tool.py`，
仓库重新构建后页面就能发现它。

清单的三种状态：

| 仓库里的 `models.json` | 行为 |
| --- | --- |
| 正常 | 合并进去（是追加，不是覆盖） |
| 不存在（404） | 从空清单开始造一份 |
| **存在但解析不了** | **整包失败** —— 拿空清单顶上等于把已收录的模型一次性抹掉，宁可不传 |

后两种都在传文件**之前**判定，不会白传几十 MB。

### 添加外部模型源：把别人仓库的模型加进列表

侧栏头「模型列表」右边的 **＋** 按钮。粘一条别人仓库 `models.json` 的链接，点「读取并添加」，
那个仓库里的模型就会出现在左侧列表里，**层级照搬它的目录结构**：
最外一层是**用户名**（表示「这批模型来自哪个仓库」），里面再按对方仓库的文件夹逐级展开 ——
比如清单里的 `"path": "Azue Lane(JP)/aierdeliqi_4"`，在侧栏里就是
`weiraing ▸ Azue Lane(JP) ▸ aierdeliqi_4`（列表项右侧标一个 `raw` / `jsDelivr`
小标签，用户名那层的分组头上有个 ✕ 可以一键移除整组）。

> **手机端**：点 ＋ 之后侧栏抽屉会**自动收回去**。对话框挂在舞台里（层级低于抽屉），
> 抽屉不收就会被压在底下，只看得到右边一条缝。「本地预览」「贡献模型」同理。

两种链接都认：

```
https://raw.githubusercontent.com/<owner>/<repo>/refs/heads/<branch>/models.json
https://cdn.jsdelivr.net/gh/<owner>/<repo>@<branch>/models.json
```

**镜像源可切**：对话框里的「镜像源」段控件**默认选中 jsDelivr**（国内快），也可以手动切到
raw —— 比如想避开 CDN 缓存看仓库最新状态。页面会用同一个 `owner/repo/branch` 重新拼地址。
粘上链接后「解析预览」会实时显示解析出的仓库 / 分支 / 生效源，粘错了当场能看出来
（链接域名跟选中的源不一致时会自动按选中的源纠正）。

模型文件从那个仓库的 **`models/` 子目录**下取（`models/<path>/<model3.json>`），
所以对方仓库的目录结构要跟本仓库一致（`models_tool.py` 生成 `models.json` 的那套）。

几条行为约定：

- **层级照搬对方仓库**：用户名是最外一层，里面按清单里的 `group`（即对方仓库的文件夹路径）
  逐级展开 —— 本仓库的模型也是这么分组的，两边规则一致。每层默认折叠，展开状态按
  「用户名/文件夹」的**全路径**单独记（`weiraing/Azue Lane(JP)` 与 `Azue Lane(JP)` 互不影响）；
  切到外部模型时会自动把整条路径逐层展开。
- **不持久化**：外部源只活在当前这次会话，刷新页面就没了，下次要用重新加一遍。
  ⚠️ **但填过的链接会记住**：对话框里的输入框与「镜像源」选择会存进 `localStorage`，
  刷新网页 / 下次打开自动预填（清空输入框即忘掉）。这样不用每次回去翻仓库页复制地址 ——
  注意记住的只是**地址**，不是「已加载的模型」。
- **同一用户名只保留一份**：重复添加同一个 owner 时，旧的整组被新清单替换，不会叠加。
- **失败自动切镜像**：先用你选的那个源拉，拉不到自动试另一个（raw ↔ jsDelivr）；两个都拉不到
  才在对话框里报错，并把两个源各自的失败原因一起列出来。
- **外部模型的备用源也是它自己的**：某个外部模型加载失败时，页面切的是**那个外部源自己的**
  raw ↔ jsDelivr，不会动本仓库正在用的源 —— 否则一个外部仓库挂掉会把整个页面的模型来源切走。
- ⚠️ 可用性由对方仓库决定。对方删库 / 改路径 / 限速时，那一组模型就会加载失败。

### 直接用链接指定模型

地址栏支持 `?model=` 参数，方便分享和调试：

```
http://localhost:8000/?model=Azue%20Lane(JP)/zhala_2/zhala_2.model3.json
```

`model` 的值可以是模型的完整 key（`相对路径/文件名`）、相对 `models/` 的目录路径，或模型名。
链接优先于本地上次记住的模型。


## 模型订阅包（自动发布）

`.github/workflows/models-release.yml` 每 7 天检查一次 `models/`，有新增模型就自动发一份订阅包，省得订阅者反复拉这个几百兆的仓库。

| Release | 内容 |
| --- | --- |
| `live2d_v3_models_all.zip` | `models/` **全部**模型（全量） |
| `live2d_v3_models_new.zip` | **仅本次新增**的模型（增量，本轮没有新增时不产生） |
| `models-latest` | 固定指针，资产每轮原地覆盖，下载地址不变 |

两个固定下载地址，内容相同（都是最新一轮的资产）：

```
https://github.com/<owner>/<repo>/releases/download/models-latest/live2d_v3_models_all.zip
https://github.com/<owner>/<repo>/releases/latest/download/live2d_v3_models_all.zip
```

两个 zip 内部都带 `models/` 顶层目录，**解压到仓库根目录**即可（`models.json` 随仓库分发，不含在包里 —— 解完跑一次 `python models_tool.py` 重建即可）。

**分工**：`models_tool.py` 负责「有哪些模型、哪些是新的」（扫描 / 基线比对 / 复制新增），工作流只负责打包、发 Release、把新清单提交回去。

> 基线就是仓库里的 `models.json` 本身 —— 一物两用：页面靠它发现模型，发布流程靠它算增量。所以**别再往仓库里塞第二份清单**（曾经有过一份 `models.txt`，两套代码两份基线，迟早对不上）。
>
> 首次运行（仓库里没有 `models.json`）只建立基线、不发布：没有基线时全部模型都会被判成新增。想立刻发一份全量包，手动触发工作流并勾选 `force_publish`。
>
> 一年 52 轮的 `all.zip` 会慢慢吃掉仓库配额，想回收旧 Release：手动触发时把 `prune_keep` 填成要保留的个数（默认 `0` = 一个不删，定时触发永远不删）。


## 目录结构

```
.
├── index.html                   预览页面（纯 HTML 结构）
├── models.json                  自动生成的模型清单（项目根目录，可提交）
├── models_tool.py               扫描 models/ 生成 models.json；发布时识别并复制新增模型
├── .github/workflows/
│   ├── models-release.yml       模型索引与增量发布（每天触发，用「纪元天数 % 7」卡成 7 天）
│   └── pages.yml                把页面壳发布到 gh-pages（只含 index.html / assets / .nojekyll / models.json）
├── tmp/                         本机测试 / 临时脚本（已 git 忽略，不进 Pages）
│   ├── _regress.js              无头 Chrome 回归测试
│   ├── _probe_responsive.js     多端适配专项测试
│   ├── _probe_ctrlwrap.js       底部控制条换行专项测试
│   ├── _probe_cycle.js          列表循环专项测试
│   ├── _probe_collapse.js       侧栏分组折叠专项测试
│   ├── _probe_parts.js          右侧部件面板专项测试
│   ├── _probe_local.js          本地预览上传 zip 专项测试
│   ├── _probe_dragreal.js       本地预览真实拖拽专项 · CDP 派发
│   ├── _probe_hoverreal.js      侧栏悬停真实鼠标专项 · CDP 派发 mouseMoved（合成事件验不出 pointerType 和陈旧定时器）
│   ├── _probe_zip.js            下载模型 zip 打包专项测试
│   ├── _probe_navflicker.js     侧栏开合闪屏专项 · 同步补渲染 + 时间线探针
│   ├── _probe_export.js         导出截图 / 隐藏配置专项测试
│   ├── _probe_contrib.js        贡献模型上传专项测试（GitHub API 全 mock）
│   ├── _probe_pagesplit.js      页面/模型分离专项（本机相对路径 + 假 Pages 域名走 raw/CDN 跨源取模型 + master→main 分支回退）
│   ├── _probe_extsrc.js         添加外部模型源专项（假域名 + 假远端清单：解析 / 切镜像 / 加层级 / 移除组 / 记住链接 / 手机抽屉让位）
│   ├── _shot_ext_tree.js        侧栏层级验收图（把本仓库真实 models.json 当外部源注入，出折叠/展开/放大三张图）
│   └── _certs/                  上面那条要用的自签证书（tmp/ 已被忽略，不会进仓库）
├── assets/
│   ├── css/app.css              页面样式
│   ├── js/app.js                页面逻辑（ES module）
│   ├── live2dcubismcore.min.js  Live2D Cubism Core（官方运行时）
│   ├── pixi.min.js              PIXI.js v6
│   └── cubism4.min.js           pixi-live2d-display 的 Cubism 4 渲染层
├── models/
│   └── <模型目录>/
└── .nojekyll
```

> `tmp/` 下的脚本都用 `const ROOT = path.join(__dirname, '..')` 指回项目根，
> 所以**必须从项目根执行**（`node tmp/xxx.js`），不能 `cd tmp` 再跑。
>
> 它们需要 `ws`（脚本内用 `NODE_PATH` 指向工作区里的 node_modules 即可），
> 以及 `C:\Program Files\Google\Chrome\Application\chrome.exe`。

## 验收

十六套测试都用无头 Chrome（`ws` + `C:\Program Files\Google\Chrome\Application\chrome.exe`）跑，
从项目根依次执行即可（Git Bash / WSL 下用下面的一行命令）：

```bash
# ⚠️ NODE_PATH 必须写成 Windows 形式（C:/…）。写成 "$HOME/…" 时 node.exe 认不出来
#    （$HOME 展开成 /c/Users/… 这种 POSIX 路径），报 Cannot find module 'ws'。
export NODE_PATH="C:/Users/rain/.workbuddy-ai/binaries/node/workspace/node_modules"
NODE="C:/Users/rain/.workbuddy-ai/binaries/node/versions/22.22.2-2/node.exe"
for s in _regress _probe_responsive _probe_ctrlwrap _probe_cycle _probe_collapse _probe_parts \
         _probe_navflicker _probe_local _probe_dragreal _probe_hoverreal _probe_zip _probe_export \
         _probe_contrib _probe_models_json _probe_pagesplit _probe_extsrc; do
  "$NODE" "tmp/$s.js" || break
done
```

> ⚠️ `_probe_pagesplit.js` 需要 `tmp/_certs/` 里的自签证书（页面里模型地址是 `https://`，
> 测试服务必须也起 HTTPS，否则浏览器直接 `ERR_SSL_PROTOCOL_ERROR`）。证书已生成好；
> 换机器时用这条命令重建一次即可：
>
> ```bash
> mkdir -p tmp/_certs && openssl req -x509 -newkey rsa:2048 -nodes \
>   -keyout tmp/_certs/key.pem -out tmp/_certs/cert.pem -days 2 \
>   -subj "/CN=raw.githubusercontent.com" \
>   -addext "subjectAltName=DNS:raw.githubusercontent.com,DNS:cdn.jsdelivr.net,DNS:weiraing.github.io,DNS:localhost,IP:127.0.0.1"
> ```
>
> ⚠️ `_probe_extsrc.js` 的服务**必须监听 443**（不是随机端口）：假域名走
> `--host-resolver-rules` 映射到本机，但浏览器对假域名默认连 **443**，而 `MAP` 不按端口分发
> —— 绑在别的端口上会 `ERR_CONNECTION_REFUSED`。跑之前先确认 443 没被占：
> `netstat -ano | grep ":443.*LISTENING"`。

| 脚本 | 断言数 | 覆盖 |
| --- | --- | --- |
| `tmp/_regress.js` | 97 | 回归：布局 / 全屏 / 播放 / 循环动作 / 速度基准 |
| `tmp/_probe_responsive.js` | 82 | 多端：4 视口（1440×900 桌面 / 900×1200 平板 / 390×844 竖屏 / 844×390 横屏）+ 抽屉开合 + 真实 touch→pointer 链 + 顶栏汉堡折叠 + 桌面悬停自动展开（**停留 1s 才展开、划过不展开、刚收起不被弹开、热区内抖动不重置计时、移出窗口撤销排队**；四条早退全覆盖：触屏 / 手写笔 / 全屏 / 「固定」；**排好定时器后切到手机不会把抽屉自己弹出来**）/「📌 固定」开关（图标灰白/彩色 + 刷新持久化） |
| `tmp/_probe_ctrlwrap.js` | 38 | 手机控制条换行显示全、不横向溢出 |
| `tmp/_probe_cycle.js` | 22 | 列表循环：显示顺序 / 换模型 / 播完绕回 |
| `tmp/_probe_collapse.js` | 16 | 侧栏分组默认折叠：展开 / 刷新记住 / 搜索不受折叠影响 |
| `tmp/_probe_parts.js` | 76 | 部件面板：勾选 / 滑杆 / 网格 bit0 / solo / 搜索 / 切模型清空 / 手机抽屉 |
| `tmp/_probe_local.js` | 118 | 本地预览上传：选文件 / 12 类坏包全拒 / 解压上架 / 权重到 1 |
| `tmp/_probe_dragreal.js` | 13 | 本地预览真实拖拽：`Input.dispatchDragEvent` 从浏览器层派发，文件由浏览器填 `dataTransfer.files` |
| `tmp/_probe_hoverreal.js` | 12 | 侧栏悬停真实鼠标：`Input.dispatchMouseEvent` 派发真实 mouseMoved —— 合成 `PointerEvent` 验不出真实 `pointerType`，也验不出「陈旧定时器把抑制窗口刷掉」这类竞态 |
| `tmp/_probe_zip.js` | 16 | 下载模型：手写 zip 结构 / 逐字节与源一致 / 系统解压可用 |
| `tmp/_probe_navflicker.js` | 6 | 侧栏展开/折叠时模型不闪：resize 后必须**同步**补一次渲染（画布改尺寸会清空 WebGL 缓冲） |
| `tmp/_probe_export.js` | 9 | 导出：截图 / `<模型名>.hidden.json` 配置落盘 |
| `tmp/_probe_contrib.js` | 73 | 贡献模型：CDP 把 `api.github.com` 全拦下伪造响应，**一个字节都发不出去**；含仓库自动识别 / 手填 / `models.json` 的三种仓库状态 |
| `tmp/_probe_models_json.js` | 6 | 清单路径：页面只认根目录 `models.json`，不会再去请求废弃的 `models/index.json` |
| `tmp/_probe_pagesplit.js` | 37 | 页面/模型分离：本机同源走相对路径（回归底线）；假 Pages 域名下**默认走 jsDelivr**跨源取到 `models.json` + model3 + moc3 + 纹理（且证明候选表是 jsDelivr 在前、raw 在后）；空格/括号/中文逐段编码；`?src=` 强制选源；两个源都挂时降级到内置清单且不白屏；**主源「半死」**（清单取得到、模型资源全挂）时自动切到备用源并载入成功；**分支回退**（`master` 取不到时自动试 `main`，并证明候选表已收窄成同一分支的两个源） |
| `tmp/_probe_extsrc.js` | 88 | 添加外部模型源：＋ 按钮**位置与样式**（绝对定位、规则在顶层未被 `@media` 包住、与 📌 同一行同尺寸且在左侧；手机端与 × 对齐；侧栏直接子元素仍是 4 个）/ 弹窗三个关闭入口（**默认镜像源是 cdn**）/ raw 与 jsDelivr 链接解析（含各类错误链接）/ 镜像源 raw↔cdn 互转 / 解析预览联动 / **侧栏层级（源 → 文件夹 → 模型：子层嵌在源层内、根目录模型不套子层、计数为子树总数、✕ 只在源层、默认折叠、点开后真的可见、折叠状态按全路径记、切换模型时逐层展开）** / 同 owner 重复添加用最新清单替换 / 移除整组 / **端到端**（假远端清单经真 fetch 走通，成功后弹窗自动关）/ **记住填过的链接**（真 reload 后仍预填，含镜像源选择；**无记忆时默认 cdn**；清空即忘）/ **手机端抽屉让位**（从抽屉里点 ＋ 或「本地预览」，抽屉自动收起且真的滑出视口） |

合计 **709 项断言，0 失败**。

> ⚠️ `_probe_contrib.js` 的计数会在 **70 / 73** 之间浮动：它的 J 组（模拟 `*.github.io`
> 自动识别仓库）用带端口的 `--host-resolver-rules` 把假域名指到本机，映射偶尔不生效时
> 整组 **SKIP**（脚本自己判的，不算失败）。上面按 73 计。这是该脚本既有的偶发现象。

> ⚠️⚠️ 每个脚本都自带静态服务，**MIME 表里必须有 `'.css': 'text/css'`**。
> 少了这一条，浏览器会把 `assets/css/app.css` 当 `application/octet-stream` 直接丢掉 ——
> 于是整轮验收跑的是**没穿衣服的页面**：`flex-wrap` 报 `nowrap`、侧栏量出来是 0 宽，
> 失败项全是假的，而且极难看出原因。2026-09-21 实测：36 个脚本里只有 1 个有这一项。
> 新写脚本请照抄 `_regress.js` 里那份表。
>
> 另一条：写「等它播起来 / 播完绕回」这类断言前，先确认**当前模型确实有动作** ——
> 默认打开的那个可能一个动作都没有（比如目录下没有 `motions/` 的模型），
> 否则只会拿到 `cur=-1`。要跳动作就用 `window.__viewer.playMotion(i)`。
>
> 第三条：断言要拿**当前帧的真实值**时（部件不透明度、网格 `dynamicFlags` bit0），
> **先用 `window.__viewer.togglePlay()` 暂停**。动作在播时 SDK 每帧按绑定重算这些值，
> 靶子随时被压成 0 / 判成不可见 —— 断言就成了掷骰子。暂停会挂定格项、每帧重放同一个 `t`，
> 参数恒定，验完再 `togglePlay()` 恢复。

> ⚠️ `_probe_dragreal.js` 依赖 Chrome 的 `Input.dispatchDragEvent`（拖拽模拟）能力，
> 该能力随 Chrome 版本变化；若某版本把它整组 `SKIP`，前六套仍是本地预览的完整保证，
> 换 Chrome 后需复验这一套。

## 说明

- 渲染依赖 `Live2D Cubism Core`，其使用需遵守 [Live2D 专有软件许可协议](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html)。
- 请确保你对所使用的 Live2D 模型拥有相应的展示与分发授权。
- 本项目依赖的第三方库：PIXI.js（MIT）、pixi-live2d-display（MIT）。
