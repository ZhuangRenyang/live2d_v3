# 项目长期记忆 — live2d_3

## 项目定位
Live2D 看板娘模型的动作预览台。纯静态站点，托管到 GitHub Pages。

## 目录约定
```
index.html            单文件页面（UI + 全部逻辑，无构建步骤）
build_index.py        扫描 models/ 生成 index.json
assets/               第三方运行库（本地存放，不依赖 CDN）
models/index.json     自动生成的模型索引（提交进仓库）
models/manifest.json  仅用于模型的 alias / motions 名称映射（可选）
models/<模型目录>/      Live2D 导出原样结构，可多层嵌套
.nojekyll             禁止 GitHub Pages 走 Jekyll
```

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
im.update(dt * 1000, 0);   // ← dt 必须是真实帧间隔，elapsed 传 0
```
`model.autoUpdate = false`，更新循环由 `tickProgress` 独占。
当前时间 = `_doUpdateTime - entry.getStartTime()`。

## ⚠️⚠️ 抖动三定律（改这块代码前必读）
这三条是「人物持续快速抖动」的根因，任何一条写错都会复现：

1. **定格项的 `endTime` 必须是 `HOLD_END = 3600`，绝不能是 `holdTime` 本身。**
   `doUpdateMotion` 开头 `return !this.isFinished() && this.updateParameters(t, e)`，
   而 `isFinished()` 判定 `t >= endTime`。写成 `setEndTime(holdTime)` 会让求值时刻
   恰好等于终点 → 一入队就 finished → **参数一个都没写进去** → 姿势退回默认值，
   呼吸/物理继续叠加 → 抖动。**不是静止，是更会动。**
2. **`internalModel.update(deltaMS, elapsedMS)` 的第一个参数必须是真实帧间隔，不能传 0。**
   里面的 `physics.evaluate(cm, dt)` 是按 dt 迭代收敛的弹簧系统，
   `pose.updateParameters(cm, dt)` 的淡入淡出也按 dt 累积。传 0 会让它们永不收敛。
   **第二个参数（elapsed）仍必须传 0**，否则和 `doUpdateMotion` 的时间基打架。
3. **定格项只挂一次**（`S.pausedEntry` 守卫）。每帧 `startMotion` 会让动作
   在起始姿势与末帧之间来回横跳。

另外：「播完定格」分支必须加 `&& !isCurrentLoop()` ——
循环动作绕回起点瞬间 `isFinished()` 短暂为真，不排除会被误判成播完而自己停住。

**定格/暂停/拖动定位时参数变化数必须为 0**（见下节验证方法）。

## 播放状态的三个标志（别混）
- `S.playing` —— 是否在走时间轴。**动作自然播完要置 false**，否则第一次点「播放」
  会被当成「暂停」，用户觉得按钮失灵。
- `S.finished` —— 当前定格是「自然播完」还是「中途暂停」。
  自然播完 → 按播放**重播**；中途暂停 → 按播放**续播**（`resumeMotionAt`）。
- `S.pausedEntry` —— 挂在队列里的定格项。换动作/重播/取消暂停都要 `clearHoldEntry()`。

## 模型发现（三级降级）
1. **GitHub API** `git/trees/HEAD?recursive=1` —— 域名是 `*.github.io` 时启用
2. **`models/index.json`** —— 由 `build_index.py` 生成，最稳
3. **`window.MODELS_FALLBACK`** —— 内置兜底

统一结构：`{ path, file, name, group, motions, textures, mocVersion, key, missing }`，
`key = path + '/' + file`，是 localStorage 的记忆标识。

## ⚠️ 验证「画面静止」只能用参数快照
- `Page.captureScreenshot` 对 PNG 压缩噪声敏感 → 只能证明「有变化」，证明不了「没在抖」
- `gl.readPixels` / `ctx.drawImage(canvas)` 在无头 Chrome 里读到的是过期缓冲（实测全 0）
- **可靠判据**：读 `coreModel._model.parameters.values`，间隔 ~700ms 采样两次统计变化数。
  某 138 参数模型：正常播放 82–104 个在变；**暂停/定格/拖动定位后必须为 0**。

## 当前模型规模
42 个模型 / 2 个分组（顶层 1 + `Azue Lane(JP)` 41）。moc 版本 3.0 与 3.3，官方 Core 全支持。
动作分组命名不统一（`''` / `Idle` / `TapTouchHead` …），
**必须同时记 `group` + `localIndex`**，只按全局下标找会放错动作。
`bisimai_2` 目录下有**两个**独立模型；`Azue Lane(JP)/bisimai_2` 那支有 15 个动作、200 个参数、含循环动作。

## 页面功能（已实现）
模型分组树+搜索、动作列表+筛选、播放/暂停/上一个/下一个/重播、进度条拖动、
0.1–3× 变速、20–400% 缩放、拖动平移、滚轮缩放、双击复位、深色舞台、
播完自动下一个、播完定格最后一帧、参考网格、视线跟随鼠标、
快捷键（←/→/空格/R）、localStorage 记住模型/折叠/速度/主题

## 名称映射写法（`models/manifest.json`）
```json
"alias":  { "my_model": "我的看板娘", "Azue Lane(JP)/aaa": "阿祖的 aaa" },
"motions": { "idle": "待机", "touch_head": "摸摸头" }
```
`alias` 的键可为模型名、相对 `models/` 的路径、或完整 `路径/文件名`，按序匹配。
