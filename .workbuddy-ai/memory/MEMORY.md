# 项目长期记忆 — live2d_3

## 项目定位
Live2D 看板娘模型的动作预览台。纯静态站点，托管到 GitHub Pages。

## 目录约定
```
index.html            单文件页面（UI + 全部逻辑，无构建步骤）
build_index.py        扫描 models/ 生成 index.json
_regress.js           无头 Chrome 回归测试（Node + CDP 直连，57 项断言）
assets/               第三方运行库（本地存放，不依赖 CDN）
models/index.json     自动生成的模型索引（提交进仓库）
models/manifest.json  仅用于模型的 alias / motions 名称映射（可选）
models/<模型目录>/      Live2D 导出原样结构，可多层嵌套
.nojekyll             禁止 GitHub Pages 走 Jekyll
```
回归运行命令（`ws` 装在托管 Node 工作区，Chrome 用系统版）：
```bash
NODE_PATH="C:/Users/rain/.workbuddy-ai/binaries/node/workspace/node_modules" \
"C:/Users/rain/.workbuddy-ai/binaries/node/versions/22.22.2-2/node.exe" _regress.js
```
`--use-gl=swiftshader` 是必须的，否则无头 Chrome 起不来 WebGL。

## 硬性约定
- **依赖库一律本地存放**在 `assets/`，不用 CDN —— 保证 Pages 上稳定可用
- **Cubism Core 必须用官方版本**（`cubism.live2d.com`，207KB，含 MocVersion_50）。
  npm 的 `live2dcubismcore@1.0.2` 只支持到 Cubism 4.2，**不可用**
- **新增模型只需把文件夹拷进 `models/`**，不改任何代码（三级降级自动发现）
- 缩放在 `fitScale()` 里按 drawable 包围盒计算，**不要改回用画布尺寸**

## ⚠️ 动作时间轴：不要用 SDK 的时钟
`queueManager._userTimeSeconds` 是**死字段，永远为 0**。
`Cubism4MotionManager` 不累加时钟，且 `startMotion` 的第三个参数被忽略。
必须自己维护 `S.motionClock`，每帧：
```js
qe._doUpdateTime = S.motionClock;
qe.doUpdateMotion(coreModel, S.motionClock);
im.update(dt * 1000, S.motionClock * 1000);
//         ↑ 真实帧间隔   ↑ 必须等于动作时间轴位置！
```
`model.autoUpdate = false`，更新循环由 `tickProgress` 独占。
当前时间 = `_doUpdateTime - entry.getStartTime()`。

**口诀：错位看 elapsed，微抖看 delta。**

## ⚠️⚠️⚠️ 权重四定律（改这块代码前必读）

`weight = 0` 意味着**动作参数一个都写不进去**（参数混合是 `a = 当前值 + (目标值-当前值)*weight`）。
四种成因现象完全相同（画面只剩呼吸/物理/姿态 = 错位或抖动），**别只修一个**：

1. **`im.update` 的第二个参数 `elapsedMS` 必须等于动作时间轴位置，绝不能传 0。**
   `internalModel.update(deltaMS, elapsedMS)` 里 `motionManager.update(cm, e)`
   → `queueManager.doUpdateMotion(cm, e)`，会**在我们刚用 motionClock 写好参数之后，
   再用 elapsed 求值覆盖一次**。传 0 时时间 0 处 `ease(0) = 0` → weight = 0 → 错位。
   （第一个参数 `deltaMS` 仍必须是真实帧间隔：physics 是弹簧系统按 dt 收敛，
   pose 淡入淡出按 dt 累积，传 0 会永不收敛 → 微抖。）
2. **定格项的 `endTime` 必须是 `HOLD_END = 3600`，绝不能是 `holdTime` 本身。**
   `doUpdateMotion` 开头 `return !this.isFinished() && this.updateParameters(t, e)`，
   而 `isFinished()` 判定 `t >= endTime`。写成 `setEndTime(holdTime)` 会让求值时刻
   恰好等于终点 → 一入队就 finished → 参数一个都没写进去 → 姿势退回默认值。
3. **定格/暂停时必须把 `fadeInStartTime` 往回拨。**
   SDK 首次求值会把 `fadeInStartTime` 设成「当时的 t」，于是 `ease(0) = 0`。
   必须 `setIsStarted(true)` 阻止它，再 `setFadeInStartTime(holdTime - fadeInSec - 0.001)`。
4. **连续切换模型必须用 `S.primed` 挡住 `tickProgress`。**
   新模型上舞台到 `playMotion` 之间，若照常推进就会用**上一个模型遗留的
   `S.motionClock`** 初始化新队列项 → `startTime = fadeInStartTime = 旧时钟`
   → `t - fadeInStart < 0` → 权重永久 0。
   `loadIntoStage` 末尾置 `S.primed = false`，`playMotion` 末尾置 `true`。

另外：**定格项只挂一次**（`S.pausedEntry` 守卫）。每帧 `startMotion` 会让动作
在起始姿势与末帧之间来回横跳。

## ⚠️ 循环动作必须自己实现：这个 build 的 `_isLoop` 恒为 false
`assets/cubism4.min.js` 里 `setIsLoop(` **只有方法定义，全文件没有任何调用点**。
所以 `Cubism4Motion._isLoop` 永远是构造时的 `false`，与 `motion3.json` 的 `Meta.Loop` 无关：
```js
getDuration() { return this._isLoop ? -1 : this._loopDurationSeconds; }   // 永远返回真实时长
// 到时：this._isLoop ? 绕回起点 : (setIsFinished(true) + 被 splice 出队列)   // 永远走 else
```
即 `Idle` 播一遍就停住。

修法：`S.motions[i].loop`（扫 model3.json 时读 `Meta.Loop`）是**唯一权威来源**；
`isCurrentLoop()` 优先用它，**不要**读 SDK 的 `isLoop()`。
它现在的唯一用途是「别给循环动作挂定格项」。

### ⚠️⚠️ `Meta.Loop = true` ≠「要循环播」—— 不要按它分叉
zhala_2 的 **全部 15 个动作**都标了 `Meta.Loop = true`。曾经按「是循环动作 → 用固定
`LOOP_DWELL = 6s` 计时推走」处理，结果 wedding(31.17s) / login(22.33s) / home(20.17s)
全在第 6 秒被硬切。
**正确语义：不管 `Meta.Loop` 是什么，都完整播一遍自己的时长，然后自动切下一个。**
`LOOP_DWELL` / `loopEnterAt` / `loopEnterIndex` / `tickPlayAllLoopDwell()` 已全部删除。

## ⚠️⚠️⚠️ 第五定律：动作对象是异步加载的，切模型后队列可能为空
`motionPreload: 'ALL'` 并不意味着「载完就能播」。`setupMotions` 先把
`motionGroups[group]` 全置成空数组，再逐个 `loadMotion().then()` 填回去 ——
所以 `loadIntoStage` 刚 resolve 的那一瞬间 `findMotionObject()` 返回 `null`。

更阴的是：**如果新旧模型的组名 + 文件名相同**（例如都是 `''` 组 +
`motions/complete.motion3.json`），`playMotion` 的 `reserve` 检查不会冲突，
动作会被启动到**上一支模型遗留的 `mm` 队列**上 → `activeEntry()` 看起来非空、
日志一切正常，但**新模型的队列永远是空的**，画面永久静止。
（`motionManager()` 在 `S.l2dModel` 还是旧模型时返回旧 mm，`stopAllMotions()` 也打偏。）

**修法：不要用一次性定时重试，改成渲染循环里自愈。**
```js
var START_RETRY_MS = 300;
var lastStartAt = 0, startRecoveryCount = 0;

function tickStartRecovery() {
  if (!S.playing) return;                        // 暂停时不打扰
  if (activeEntry() || S.pausedEntry) return;     // 队列里有东西 = 正常状态
  if (Date.now() - lastStartAt < START_RETRY_MS) return;
  lastStartAt = Date.now();
  startRecoveryCount++;
  playMotion(S.current < 0 ? 0 : S.current, true);
}
```
`tickProgress` 里调用：`if (!holding && !e && !S.pausedEntry) tickStartRecovery();`
**不设次数上限** —— 动作一可用就自动接上，比「重试 N 次后放弃」稳得多。
诊断看 `window.__viewer.info().startRecoveryCount`。

## ⚠️⚠️ SDK 会自己偷偷起 Idle 动作，必须三重关闭
`MotionManager.update()` 里写死了：
```js
this.state.shouldRequestIdleMotion() && this.startRandomMotion(this.groups.idle, IDLE)
// shouldRequestIdleMotion() { return currentGroup === undefined && reservedIdleGroup === undefined }
```
**只要动作队列空了，SDK 就自己从 Idle 组随机起一个动作。** 它插入的队列项 `startTime`
是在首次求值时写成「当时的 elapsed」的 → `currentTime() = elapsed - startTime` **恒为 0**
→ 页面永远等不到「播完」。
现象：zhala_2 的 login(22.33s) 播完后**每 12 秒**（正好是它 Idle 的时长）自己重启一次。

```js
var NO_IDLE_GROUP = '__no_auto_idle__';
function disableAutoIdle(mm) {
  try { mm.stopAllMotions(); } catch (e) {}
  mm.groups && (mm.groups.idle = NO_IDLE_GROUP);        // 指向不存在的分组
  mm.startRandomMotion = function () { return false; };  // 封掉入口
}
// 装载时还要传 idleMotionGroup: NO_IDLE_GROUP
```
⚠️ **`idleMotionGroup` 传空串等于没传** —— SDK 是 `(t?.idleMotionGroup) && (...)`，
**空串是 falsy**，直接跳过赋值。必须传「非空且不存在于任何模型动作分组里」的哨兵值。

定位手段（值得复用）：`queueManager.startMotion` 装钩子抓 `new Error().stack`，
直接就能看出是页面代码还是 SDK 内部在起动作。

## ⚠️⚠️ PIXI ticker 的 delta 已按 60fps 归一化 → 秒 = `delta / 60`
```js
this.deltaMS   = t - lastTime;                 // 真实帧间隔（毫秒）
this.deltaTime = this.deltaMS * TARGET_FPMS;   // TARGET_FPMS = 0.06 = 1/16.667
n.emit(this.deltaTime);                        // 回调收到的就是这个
```
**绝不能除以 `ticker.FPS`** —— 那是「实测帧率」（`1000/elapsedMS`，高刷屏上是 144/165/240），
会让动作按 `60 / 实测帧率` 倍**慢放**：屏幕越流畅、动作越慢。
**这个 bug 在 60Hz 屏上完全看不出来，只在 144Hz 以上暴露。**

## ⚠️ 其它 SDK 陷阱
- `setIsStarted(true)` 后 SDK **不再补 `endTime`** → 必须显式
  `setEndTime(motionObjectDuration(motionObj, mo))`，否则 `isFinished()` 永假，
  「播完自动下一个 / 连播」永不触发
- `mm.getMotionFile(t)` 只接受**定义**对象；`motionGroups[group]` 里是**已加载的动作对象**
  （无 `.File`）。按文件名反查要走 `mm.definitions[group][i].File`（见 `findMotionObject`）
- `switchModel` 的 `busyModel` 互斥不能直接 `return`（用户连点会觉得没反应），
  要记 `S.pendingModel` 并在载完后 `drainPendingModel()` 补切
- **队列为空时 `tickProgress` 仍必须推进时钟**（`S.motionClock`），否则 SDK 摘掉队列项后
  时间轴冻结，「播完自动下一个」永不触发。但**不能无条件推进**：队列空 + 时钟离末尾还远
  = 动作压根没启动起来，此时推进会让 `holdTime` 涨到 `dur` 被误判成「播完了」而跳过这个动作。
  门控：`var stalled = !e && dur > 0 && S.holdTime < dur - 0.05;`
- **定格项挂不上时必须保持 `S.playing = true`**：`mountHoldEntry` 拿不到动作对象会直接 `return`，
  调用方若无条件 `S.playing = false` → 页面永久停住，`tickStartRecovery` 又被
  `if (!S.playing) return` 挡住。守卫：`if (S.pausedEntry) { S.playing = false; }`

## 播放状态的标志（别混）
- `S.playing` —— 是否在走时间轴。**动作自然播完要置 false**，否则第一次点「播放」
  会被当成「暂停」，用户觉得按钮失灵。
- `S.finished` —— 当前定格是「自然播完」还是「中途暂停」。
  自然播完 → 按播放**重播**；中途暂停 → 按播放**续播**（`resumeMotionAt`）。
- `S.pausedEntry` —— 挂在队列里的定格项。换动作/重播/取消暂停都要 `clearHoldEntry()`。
- `S.primed` —— 新模型的动作队列是否已由 `playMotion` 初始化好（见权重定律 4）。
- `S.autoPlayAll` —— **已改为常开 `true`**，不再有开关（见「动作列表已删除」）。
- `S.fullscreen` —— 页面内全屏状态（对应 `.app.fs` 类），与浏览器原生全屏分开记。
- ~~`S.autoNext` / `S.hideMotions`~~ —— 随动作列表一起删除，**不要再引用**。

## 模型发现（三级降级）
1. **GitHub API** `git/trees/HEAD?recursive=1` —— 域名是 `*.github.io` 时启用
2. **`models/index.json`** —— 由 `build_index.py` 生成，最稳
3. **`window.MODELS_FALLBACK`** —— 内置兜底

统一结构：`{ path, file, name, group, motions, textures, mocVersion, key, missing }`，
`key = path + '/' + file`，是 localStorage 的记忆标识。

## ⚠️ 验证方法（判据选错会「假通过」）
- `Page.captureScreenshot` 对 PNG 压缩噪声敏感 → 只能证明「有变化」，证明不了「没在抖」
- ⚠️⚠️ **截图绝对不能用来判断舞台背景色。** 无头 Chrome（swiftshader）在
  `Page.captureScreenshot` 时会把 **WebGL canvas 的透明区域合成为黑色** ——
  于是浅色 / 深色 / 黑色三档的舞台在截图里**看起来全是黑的**（实测：`getComputedStyle`
  三档值完全正确、`pixiBgAlpha: 0`，把 `#live2d-canvas-host` 隐藏后截图立刻就是正常的白色径向渐变）。
  验证背景色一律读 `getComputedStyle(stage).backgroundImage`，不要看截图。
- `gl.readPixels` / `ctx.drawImage(canvas)` 在无头 Chrome 里读到的是过期缓冲（实测全 0）
- **主判据：队列项权重 `entry.getStateWeight()` 必须收敛到 `1`。**

  | 场景 | `getStateWeight()` | 参数变化数 |
  | --- | --- | --- |
  | 正在播放 | `1` | 明显 > 0（138 参数约 85） |
  | 正确定格 / 暂停 | `1` | `0` |
  | **错位**（elapsed 传 0） | **`0`** | 播放中也接近 0 |
  | **定格 fadeInStart 没往回拨** | **`0`** | `0` |

  ⚠️ **只看「参数变化数 = 0」会假通过** —— `weight = 0` 时参数本来就不变，
  「错位」和「正确定格」在这个指标上长得一模一样。上一次「26/26 通过」就是这么骗过去的。
- **不要用固定 sleep 断言「播放中权重=1」**：无头 Chrome 的 rAF 比墙钟快，
  5 秒动作 2 秒就播完并摘掉队列项，此时 `entry=null` 是「播完了」不是「错位」。
  要**逐帧采样整个播放过程**，记录**最大权重**（应到 1）与**最大时钟**（应 > 0.5）；
  采样循环必须有硬上限（如 300 帧），否则永不 resolve 会卡死整套测试。
- **`switchModel` 有 `busyModel` 互斥**，连续调用第二次会被吞掉。用
  `window.__viewer.switchedTo(key)` 等到位再采样。
- **测连播要挑动作短的模型**：`biaoqiang` 平均 3.64s 最合适；
  `zhala_2` 平均 13.44s，观察 14 秒当然只看到 1 个动作。
- **断言要测「语义」，不要测「像素阈值」**：本轮首跑 7 项失败里有 4 项是断言写错而非产品 bug ——
  侧栏占比写 `< 0.6` 忽略了搜索框与 padding；GitHub 图标写「距右边缘 < 120px」
  忽略了右侧还有按钮；全屏写「舞台变大」忽略了无头视口反而更小。
  改成「侧栏只剩 3 个直接子元素」「图标在右半区且与主题按钮同排」「舞台 == 视口」后全绿。
- **`playMotion` 会清零 `S.motionClock`**，所以「绕回第 1 个后是否还在播」不能在切换那一帧读时钟 ——
  要再观察 30 帧取 `clkAfter`。

## 当前模型规模
**`models/index.json` 里是 41 个模型 / 2 个分组（顶层 1 + `Azue Lane(JP)` 40）。**
（更早记的 42 是因为 `Azue Lane(JP)/bisimai_2/3712cc44403f6c247db4d7c0edd16016.model3.json`
被**纯改名**成了 `.json` —— 内容一模一样，但页面只认 `*.model3.json`，所以少了一个。
这处改名在 git 里一直是 ` D` + `??` 未提交状态，**用户未表态，不要擅自改回**。）

moc 版本 3.0 与 3.3，官方 Core 全支持。
动作分组命名不统一（`''` / `Idle` / `TapTouchHead` …），
**必须同时记 `group` + `localIndex`**，只按全局下标找会放错动作。
`Azue Lane(JP)/bisimai_2` 那支有 15 个动作、200 个参数、含循环动作。

## 页面功能（已实现）
模型分组树 + 搜索、**载入即自动依次播完全部动作（无限绕回）**、
播放/暂停、0.1–3× 变速、20–400% 缩放、拖动平移、滚轮缩放、双击复位、
**舞台背景三档（浅色 / 深色 / 黑色）**、
参考网格、视线跟随鼠标、**全屏播放**、**顶栏 GitHub 仓库图标**、
快捷键（`F` 全屏 / `Esc` 退出 / 空格 播放暂停 / `R` 复位 / `T` 循环切换舞台背景）、`?model=` 深链、
localStorage 记住模型/折叠/速度/舞台背景

### 舞台背景三档的实现要点
- `STAGE_THEMES = ['light','dark','black']`；浅色是 `.stage` 基础样式（白色径向渐变），
  深色是 `.stage.dark`，黑色是 `.stage.black{ background:#000; }`
- `setStageTheme(name, silent)` 同时切 class + 按钮高亮；`cycleStageTheme()` 供快捷键 `T`
- ⚠️ **`setStageTheme` 必须支持 `silent`**：`boot()` 恢复时若照常 `saveState()`，
  那时 `S.speed` / `S.collapsed` 还没读回来，会把它们冲成默认值，**弄丢用户存的速度和折叠状态**
- `saveState()` 存字符串 `stage: S.stageTheme`；`boot()` 兼容老格式 `dark: true/false`
- ⚠️ **深/黑舞台上信息条文字必须显式提亮**：`.b1` 默认继承 `--text`（深色），
  深底压深字完全看不见。`.stage.dark .badge .b1, .stage.black .badge .b1{ color:#e8edf5; }`

### ⚠️ 「动作列表」模块已被整体删除，不要再加回来
用户要求「模型直接播放全部的动作」，因此以下内容**全部不存在**，回归测试专门断言它们
的 DOM 与函数都不存在：`#motionPane` / `#motionList` / `#motionSearch` / `#motionCount` /
`#playAllBar` / `#modeSeg` / `#btnPrev` / `#btnNext` / `#btnReplay` / `#progress` /
`#autoNext` / `#hideMotions`，以及 `renderMotions` / `startPlayAll` / `stopPlayAll` /
`updatePlayAllTxt` / `hideOverlaySoft` / `applyHideMotions` / `togglePlayTo` / `fmtSec` / `qs`。
侧栏现在**只有** `#modelList` 一个功能块；左上信息条由 `renderMotionBadge()` 更新
（格式 `2/15 · Idle · 12.0s`）。
**加新功能前先 grep 这些名字，避免复活悬空引用。**

### 自动推进（`S.autoPlayAll` 常开）
`playMotion(0, true)` 起步，之后靠 `tickProgress` 自动推进；播完即
`playMotion(next >= S.motions.length ? 0 : next, true)` **无限绕回**。
`S._advancing` 做 450ms 节流，防止同一帧被反复推进。
循环动作没有「播完」时刻，用 `LOOP_DWELL = 6s` + `tickPlayAllLoopDwell()` 推走。

### 全屏播放（双轨实现，别只留一条）
- **CSS 全屏**：`.app.fs` 隐藏 `.topbar / .sidebar / .controls / .badge / .stage-hint`，
  舞台铺满 —— **即使 `requestFullscreen()` 被拒（iframe 内）也生效**
- **原生全屏**：`requestFullscreen()`，`p` 上挂 `.catch(function(){})` 吞掉拒绝
- 进入/退出后必须 `requestAnimationFrame(relayout)` 延后一帧：
  `S.app.renderer.resize(box.w, box.h)` + 重画网格 + 按原百分比重新 `setZoomPercent`
- `fullscreenchange` 只在浏览器**确实已退出**时清 `.fs`（`Esc` 会先触发原生退出）
- 退出按钮 `#btnExitFs` 平时 `opacity:.2`，hover 变实 —— 全屏时**唯一**的可见控件
- 回归判据：**「舞台尺寸 == `innerWidth/innerHeight`」，不是「比之前更大」**
  （无头 Chrome 里原生全屏后视口尺寸可能反而变小，实测 1132×694 → 800×600，
  用「变大」判会假失败）

### 顶栏 GitHub 图标
`<a class="gh-link" id="ghLink">` + 官方 GitHub SVG。
`setupRepoLink()` 里 `inferRepo()` 从 `*.github.io/<repo>` 域名推断仓库地址，
非 Pages 环境回落常量 `REPO_URL = 'https://github.com/weiraing/live2d_3'`。
断言用「在顶栏右半区 + 与舞台背景选择器（`#stageSeg`）同排」，**不要**用「距右边缘 < N px」
（右侧还有其它按钮，阈值容易写死）。

## 名称映射写法（`models/manifest.json`）
```json
"alias":  { "my_model": "我的看板娘", "Azue Lane(JP)/aaa": "阿祖的 aaa" },
"motions": { "idle": "待机", "touch_head": "摸摸头" }
```
`alias` 的键可为模型名、相对 `models/` 的路径、或完整 `路径/文件名`，按序匹配。
