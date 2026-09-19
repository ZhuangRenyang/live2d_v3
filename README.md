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

## 自定义动作名称与模型名称

`models/manifest.json` 现在**只用于名称映射**，模型是否被收录与它无关。`alias` 用于给模型起中文名：

```json
"alias": {
  "my_model": "我的看板娘",
  "Azue Lane(JP)/aaa": "阿祖的 aaa"
}
```

键可以是模型名、相对 `models/` 的目录路径，或完整的 `路径/文件名`，按顺序匹配。`motions` 用于把动作文件名映射成可读名称：

```json
"motions": {
  "idle": "待机",
  "touch_head": "摸摸头"
}
```

未登记的项会自动把文件名转成首字母大写的可读形式。

## 界面功能

页面刻意做得很轻：**没有动作列表**，模型一载入就自动把全部动作依次播完、再从头循环，
打开就是在动的看板娘，不需要点任何东西。

| 功能 | 说明 |
| --- | --- |
| 模型列表 | 左侧按文件夹分组折叠展示，可搜索，点击切换模型 |
| 自动依次播完全部动作 | 载入模型后从第 1 个动作自动往下播，播完最后一个回到第 1 个，无限循环 |
| 播放控制 | 播放 / 暂停 |
| 速度 | 0.1× ~ 3× 变速播放 |
| 缩放 | 20% ~ 400%，也可用滚轮；拖动画面可平移，双击复位 |
| 深色舞台 | 切换舞台背景，便于查看浅色或深色角色 |
| **全屏播放** | 顶栏图标或底部「全屏播放」按钮，一键让整个屏幕只剩模型（浏览器原生全屏 + 隐藏全部面板） |
| GitHub 图标 | 顶栏右上角，点击打开本仓库 |
| 显示网格 | 叠加参考网格，方便定位 |
| 快捷键 | `←` `→` 跳到上/下一个动作、`空格` 播放/暂停、`R` 重播当前、`F` 全屏、`Esc` 退出全屏 |

舞台左上角的信息条会显示当前是第几个动作、叫什么名字、多长。

### 播放行为说明

- **暂停 / 拖动定位**后按「播放」是**接着播**，不会跳回开头。
- **非循环动作播完后会停在最后一帧**（不会弹回初始姿势），稍后自动切到下一个动作。
- **循环动作**（`Idle` 等）没有「播完」的瞬间，按固定停留时长（6 秒）继续往下走。
- 换模型后一律从第 1 个动作重新开始。
- 全屏时顶栏、侧栏、底部控制条、信息条、操作提示全部隐藏，舞台上只剩模型；
  右上角有一个几乎透明的退出按钮（鼠标移上去才显形），也可以按 `Esc`。

鼠标移动时角色的视线会跟随光标。

### 直接用链接指定模型

地址栏支持 `?model=` 参数，方便分享和调试：

```
http://localhost:8000/?model=Azue%20Lane(JP)/zhala_2/zhala_2.model3.json
```

`model` 的值可以是模型的完整 key（`相对路径/文件名`）、相对 `models/` 的目录路径，或模型名。
链接优先于本地上次记住的模型。

### 回归测试

```bash
node _regress.js
```

它会起一个本地静态服务 + 无头 Chrome，逐项验证：动作列表确实已删除、GitHub 图标、
全屏（含「原生全屏被拒绝时 CSS 全屏仍生效」这条分支）、模型能自动依次播完全部动作并绕回第 1 个、
暂停/续播/定格不抖动。**判据是队列项权重 `entry.getStateWeight()` 必须收敛到 1**，
不能只看「参数变化数」—— 权重为 0 时参数本来就不变，会假通过。

### ⚠️ 三个必须知道的 SDK 坑

改 `index.html` 里播放相关代码前请务必了解，否则很容易复现「错位」「抖动」「循环不动」「切完模型不播」：

**1. `im.update(deltaMS, elapsedMS)` 的第二个参数必须等于动作时间轴位置。**

```js
// Cubism4InternalModel.update(deltaMS, elapsedMS)
//   → motionManager.update(cm, elapsedMS/1000)
//   → queueManager.doUpdateMotion(cm, e)
im.update(dt * 1000, S.motionClock * 1000);   // ← 第二个参数不能传 0
```

传 0 会让 SDK 在我们刚写好参数之后，**再用时间 0 求值并覆盖一次**。
而时间 0 处淡入权重 `ease(0) = 0`，动作贡献被完全抹掉，画面只剩呼吸/物理 —— 表现为**播放错位**。

第一个参数仍必须是**真实帧间隔**：`physics.evaluate` 是按 dt 迭代收敛的弹簧系统，
`pose.updateParameters` 的淡入淡出也按 dt 累积，传 0 会让它们永不收敛。

**2. 这个 SDK build 的 `_isLoop` 恒为 `false`，循环必须自己实现。**

`assets/cubism4.min.js` 里 `setIsLoop` **只有方法定义、没有任何调用点**，所以：

- `Cubism4Motion.getDuration()` 永远返回 `_loopDurationSeconds`（不是 -1）
- 动作走到 `duration` 时不会 `setStartTime` 绕回起点，而是直接 `setIsFinished(true)` 并把队列项摘掉

因此页面自己维护了循环：`S.motions[i].loop` 直接来自 `motion3.json` 的 `Meta.Loop`，
**它是唯一权威来源**。本页面固定处于「依次播完全部动作」模式，
非循环动作播完后由 `tickProgress` 自动 `playMotion` 下一个（到末尾绕回第 1 个），
循环动作则由 `LOOP_DWELL`（6 秒）计时推走。

> 相应地，`isCurrentLoop()` 里 **不要**把 `motion.isLoop()` 当主要判据 —— 它恒为 `false`。

**3. 动作对象是异步加载的，切完模型不能只启动一次。**

`Live2DModel.from(..., { motionPreload: 'ALL' })` 只是**发起**加载：`setupMotions` 先把
`motionGroups[group]` 全部置成空数组，再逐个 `loadMotion().then()`。所以模型刚挂上舞台的那一瞬间
`findMotionObject()` 会返回 `null`，动作根本起不来（时间轴永远是 0，画面停在默认姿势）。

更隐蔽的是：若新旧两个模型的**动作组名和文件名相同**（例如都是 `''` 组 + `motions/complete.motion3.json`，
`biaoqiang` / `aimierbeierding_2` 就属于这种），切换瞬间的 `playMotion` 可能把动作启动到**上一支模型遗留的
队列**上，`activeEntry()` 非空、看起来「启动成功」，但新模型的队列是空的 —— 于是永久卡住。

因此页面用 `tickStartRecovery()` 做兜底：只要发现**队列里既没有正在播的动作、也没有定格项**，
就每 300ms 重新启动一次当前动作，**不设次数上限**。动作一变得可用就自动接上。

## 目录结构

```
.
├── index.html                   预览页面（全部逻辑）
├── build_index.py               扫描 models/ 生成 index.json
├── _regress.js                  无头 Chrome 回归测试（node _regress.js）
├── assets/
│   ├── live2dcubismcore.min.js  Live2D Cubism Core（官方运行时）
│   ├── pixi.min.js              PIXI.js v6
│   └── cubism4.min.js           pixi-live2d-display 的 Cubism 4 渲染层
├── models/
│   ├── index.json               自动生成的模型索引（可提交）
│   ├── manifest.json            模型中文名 / 动作中文名映射（可选）
│   └── <模型目录>/
└── .nojekyll
```

> `_regress.js` 需要 `ws`（脚本内用 `NODE_PATH` 指向工作区里的 node_modules 即可），
> 以及 `C:\Program Files\Google\Chrome\Application\chrome.exe`。

## 说明

- 渲染依赖 `Live2D Cubism Core`，其使用需遵守 [Live2D 专有软件许可协议](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html)。
- 请确保你对所使用的 Live2D 模型拥有相应的展示与分发授权。
- 本项目依赖的第三方库：PIXI.js（MIT）、pixi-live2d-display（MIT）。
