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

`models/manifest.json` 用于**名称映射**和**按模型隐藏图层**（见下一节），模型是否被收录与它无关。`alias` 用于给模型起中文名：

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

### 隐藏个别模型的图层（`hiddenParts` / `hiddenDrawables`）

有些模型**导出时丢掉了部分网格的「不透明度参数绑定」**：这些网格的静态不透明度是 1，
而 moc3 里没有任何参数能改变它 —— 于是本该只在特定动作里出现的备用图层永久显示，
看上去就是「多了一只手 / 一条手臂」。这属于模型自身的缺陷，**任何渲染器都会把它画出来**，
不是本页面的问题（排查过程见 `_regress.js` 之外的诊断脚本思路：把全部参数逐个推到
min/max，观察目标网格的不透明度、可见性、顶点三项是否变化，都不动就说明绑定不存在）。

既然网格侧无法自己恢复绑定，就只能在数据侧指定要隐藏谁：

```json
"hiddenParts": {
  "Azue Lane(JP)/zhala_2/zhala_2.model3.json": [
    "PartHandLCongxia",
    "PartHandLNakaiDuli"
  ]
}
```

- 键用模型完整 key（相对 `models/` 的 `路径/文件名`），也兼容只写目录或模型名。
- `hiddenParts` 填**部件**名，`hiddenDrawables` 填**网格**名，可同时使用。
- 隐藏是每帧重设的（SDK 每次 update 都会按绑定重算网格不透明度，会覆盖手工写进去的 0）。
- 名字写错不会报错，只是不起作用；用 `__viewer.hidden()` 可以看到实际生效的索引。

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

- 打包**不压缩**（zip STORE）。moc3 / png / mp3 本来就压过了，再 deflate 收益极小，
  却要额外引一个压缩库，不值。代价是 zip 体积≈原体积（一个模型 8~30 MB）。
- 全程在浏览器里完成，**没有服务端**（Pages 是静态托管，浏览器也没法列目录），
  所以只按引用收集；`model3.json` 没引用到的散落文件不会被打进去。
- 打包期间按钮会显示 `打包中 3/31` 的进度，完成后浮层会报「多少文件 · 多大」；
  个别文件 404 会跳过并在结果里注明，不会整包失败。
- 引用了但磁盘上没有的文件、以及 `.model3.json` 里没声明的多余文件，都不会进包。

### 播放行为说明

- **暂停 / 拖动定位**后按「播放」是**接着播**，不会跳回开头。
- **非循环动作播完后会停在最后一帧**（不会弹回初始姿势），稍后自动切到下一个动作。
- **每个动作都完整播一遍自己的时长**，然后自动切到下一个 —— 这与 `motion3.json` 里的
  `Meta.Loop` 无关。注意 `Meta.Loop = true` **不代表**这个动作要循环播放，
  它只是导出器的标记；真正的循环播放（如 `Idle`）由页面自己维护（见下文 SDK 坑 2）。
- 舞台背景三档（浅色 / 深色 / 黑色）会记在浏览器里，下次打开自动恢复。
- **「列表循环」开着**：当前模型的全部动作播完后自动换到列表里的下一个模型，
  到列表末尾绕回第一个，一直轮播下去。换模型期间会短暂显示「正在载入模型」。
- **「列表循环」关着**：播完最后一个动作就回到本模型的第 1 个继续播，**不会换模型**。
- 换模型（手动点、或自动轮播）后一律从第 1 个动作重新开始。
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

测试脚本都放在 `tmp/`（已 git 忽略，不进 Pages）。在项目根目录执行：

```bash
node tmp/_regress.js
```

它会起一个本地静态服务 + 无头 Chrome，逐项验证（当前 **92 项**）：动作列表确实已删除、GitHub 图标、
底部控制条（列表循环开关与「显示网格」同一套 UI、状态持久化、下载按钮的位置与可点性）、
全屏（含「原生全屏被拒绝时 CSS 全屏仍生效」这条分支）、模型能自动依次播完全部动作、
**列表循环开时播完自动切到下一个模型 / 关时只在本模型内绕回**、暂停/续播/定格不抖动、
三档舞台背景的切换与持久化、SDK 的自动 Idle 确实已关闭、以及**播放速度与真实时间一致**。

另有三个专项脚本：

```bash
node tmp/_probe_responsive.js   # 多端适配：桌面 / 平板 / 手机竖屏 / 手机横屏 / 回桌面复位（52 项）
node tmp/_probe_cycle.js        # 列表循环：模型列表的顺序、切下一个、绕回、搜索过滤兜底（20 项）
node tmp/_probe_zip.js          # 下载模型：真的打包一份 zip，解析结构 + 逐字节比对 + 交给系统解压器解（16 项）
```

`_probe_cycle.js` 会验证：可见列表的顺序与侧栏显示顺序一致（**不是 `S.models` 的原始顺序**）、
「下一个」的推算、播完真的换模型、到列表末尾绕回第一个、搜索过滤后的范围、
当前模型被过滤掉时回退到列表第一个、以及关掉开关后不再换模型。

**主判据是队列项权重 `entry.getStateWeight()` 必须收敛到 1**，
不能只看「参数变化数」—— 权重为 0 时参数本来就不变，「错位」和「正确定格」在这个指标上长得一模一样，会假通过。

> ⚠️ **不要用截图判断舞台背景色。** 无头 Chrome（swiftshader）在 `Page.captureScreenshot` 时会把
> WebGL canvas 的**透明区域合成为黑色**，于是浅色 / 深色 / 黑色三档的舞台在截图里看起来全是黑的。
> 这是截图环节的假象，页面本身没问题 —— 想验证背景色请读 `getComputedStyle(stage).backgroundImage`，
> 或把 `#live2d-canvas-host` 隐藏后再截图。
> 同理，`gl.readPixels` / `ctx.drawImage(canvas)` 在无头 Chrome 里读到的是过期缓冲，也不可靠。

> ⚠️ **不要用固定 `sleep` 断言「播放中权重 = 1」。** 无头 Chrome 的 rAF 比墙钟快，
> 5 秒的动作可能 2 秒就播完并摘掉队列项，此时 `entry === null` 是「播完了」而不是「错位」。
> 要**逐帧采样整个播放过程**，记录**最大权重**（应到 1）与**最大时钟**（应 > 0.5），
> 且采样循环必须有硬上限（如 3000 帧），否则永不 resolve 会卡死整套测试。

### ⚠️ 五个必须知道的 SDK 坑

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
每个动作播完自己的时长后由 `tickProgress` 自动 `playMotion` 下一个（到末尾绕回第 1 个）。

> 相应地，`isCurrentLoop()` 里 **不要**把 `motion.isLoop()` 当主要判据 —— 它恒为 `false`。
> 它的唯一用途是「别给循环动作挂定格项」。

> ⚠️ **`Meta.Loop = true` 不等于「要循环播」。** 有些导出器会给**全部**动作都标上
> `Meta.Loop = true`（`zhala_2` 的 15 个动作全中招），此时若按「是循环动作 → 用固定停留时长推走」
> 处理，`wedding`(31.17s) / `login`(22.33s) / `home`(20.17s) 会在第 6 秒被硬切。
> 正确语义：**不管 `Meta.Loop` 是什么，都完整播一遍自己的时长再走下一个。**

**3. 动作对象是异步加载的，切完模型不能只启动一次。**

`Live2DModel.from(..., { motionPreload: 'ALL' })` 只是**发起**加载：`setupMotions` 先把
`motionGroups[group]` 全部置成空数组，再逐个 `loadMotion().then()`。所以模型刚挂上舞台的那一瞬间
`findMotionObject()` 会返回 `null`，动作根本起不来（时间轴永远是 0，画面停在默认姿势）。

更隐蔽的是：若新旧两个模型的**动作组名和文件名相同**（例如都是 `''` 组 + `motions/complete.motion3.json`，
`biaoqiang` / `aimierbeierding_2` 就属于这种），切换瞬间的 `playMotion` 可能把动作启动到**上一支模型遗留的
队列**上，`activeEntry()` 非空、看起来「启动成功」，但新模型的队列是空的 —— 于是永久卡住。

因此页面用 `tickStartRecovery()` 做兜底：只要发现**队列里既没有正在播的动作、也没有定格项**，
就每 300ms 重新启动一次当前动作，**不设次数上限**。动作一变得可用就自动接上。

> ⚠️ **但这个兜底必须排在「播完判定」之后，否则它会把刚播完的动作重新启动，让「播完自动下一个」永远不成立。**
>
> 动作播到末尾时，SDK 会把队列项摘掉。摘掉的那一帧 `activeEntry()` 变成 `null`，看起来和
> 「动作压根没启动起来」一模一样 —— 于是 `tickStartRecovery()` 抢先把**同一个**动作重新入队，
> 并**把 `S.motionClock` 清零**；紧接着下面按 `holdTime >= dur` 判断「播完了吗」就永远是假，
> 动作无限原地重播，换模型自然也一起失效。
>
> 这个竞态一直存在，只是 **1× 速度下 `t` 逼近 `dur` 的帧很多，通常是自动推进先赢**，
> 所以看不出来；**3× 速度或低帧率下必现**（实测 3× 时每 4 秒原地重播一次）。
> 正确写法是先算出 `ended = !holding && dur > 0 && S.holdTime >= dur - 0.02`，
> 再用 `if (!holding && !e && !S.pausedEntry && !ended) tickStartRecovery();`。
>
> 另外 `tickStartRecovery()` 里还要 `if (S.busyModel) return;` —— 换模型期间 `S.motions` /
> `S.l2dModel` 可能还是上一支模型的，照常重启会把旧动作重新入队，还会把 `S.primed` 置回 `true`
> 干扰新模型的装载。

**4. SDK 会在动作队列空掉时自己随机起一个 Idle 动作，必须关掉。**

`MotionManager.update()` 里写死了这么一句：

```js
this.state.shouldRequestIdleMotion() && this.startRandomMotion(this.groups.idle, IDLE)
// shouldRequestIdleMotion() { return currentGroup === undefined && reservedIdleGroup === undefined }
```

也就是说**只要队列空了，SDK 就自己从 Idle 组随机起一个动作**。它插入的队列项 `startTime`
是在首次求值时写成「当时的 elapsed」的，于是 `currentTime() = elapsed - startTime` 恒为 0 ——
页面永远等不到「播完」。表现就是：`zhala_2` 的 `login`(22.33s) 播完后，
每 12 秒（正好是它 Idle 的时长）自己重启一次，永远停在第一个动作。

关掉它需要**三重保险**，缺一个都可能漏：

```js
var NO_IDLE_GROUP = '__no_auto_idle__';

function disableAutoIdle(mm) {
  try { mm.stopAllMotions(); } catch (e) {}
  mm.groups && (mm.groups.idle = NO_IDLE_GROUP);        // 指向一个不存在的分组
  mm.startRandomMotion = function () { return false; };  // 直接封掉入口
}
// 装载时还要传 idleMotionGroup: NO_IDLE_GROUP
```

> ⚠️ **`idleMotionGroup` 传空串等于没传。** SDK 写的是 `(t?.idleMotionGroup) && (...)`，
> **空串是 falsy**，会直接跳过赋值。必须传一个「非空、且不存在于任何模型动作分组里」的哨兵值。

**5. PIXI ticker 回调收到的 `delta` 已经按 60fps 归一化过了，换算成秒是 `delta / 60`。**

```js
// TARGET_FPMS = 0.06 = 1 / 16.667
this.deltaMS   = t - lastTime;              // 真实帧间隔（毫秒）
this.deltaTime = this.deltaMS * TARGET_FPMS; // 归一化后的帧数
n.emit(this.deltaTime);                      // ← 回调收到的就是这个
```

所以 `dt = delta / 60`，**绝不能除以 `ticker.FPS`**。`ticker.FPS` 是「实测帧率」
（`1000 / elapsedMS`），在 144Hz / 165Hz / 240Hz 屏上就是 144 / 165 / 240，
拿它当除数会让动作按 `60 / 实测帧率` 倍**慢放** —— 屏幕越流畅、动作越慢。
这个 bug 在 60Hz 屏上完全看不出来，只在高刷屏上暴露。

## 目录结构

```
.
├── index.html                   预览页面（全部逻辑）
├── build_index.py               扫描 models/ 生成 index.json
├── tmp/                         本机测试 / 临时脚本（已 git 忽略，不进 Pages）
│   ├── _regress.js              无头 Chrome 回归测试（node tmp/_regress.js）
│   ├── _probe_responsive.js     多端适配专项测试
│   └── _probe_zip.js            下载模型（zip 打包）专项测试
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

## 说明

- 渲染依赖 `Live2D Cubism Core`，其使用需遵守 [Live2D 专有软件许可协议](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html)。
- 请确保你对所使用的 Live2D 模型拥有相应的展示与分发授权。
- 本项目依赖的第三方库：PIXI.js（MIT）、pixi-live2d-display（MIT）。
