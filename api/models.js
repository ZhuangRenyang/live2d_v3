// GET /api/models —— 模型清单的「线上自动发现」通道（2026-09-24）。
//
// 为什么需要它：预览页要列出 models/ 下的全部 .model3.json，而静态托管没有
//   「列目录」能力，历史上只能依赖 models_tool.py 人肉跑出来的 models.json ——
//   忘了跑，新模型就「传上去了但页面看不见」。这个函数让清单**跟随仓库实时生成**：
//   访客请求 /api/models → Vercel 出网向 api.github.com 查仓库树（递归全文件）
//   → 现场筛出所有 *.model3.json → 按 models_tool.py 的同款规则组装成同构清单。
//   从此「新增/删除模型」只要 git push，清单永远新鲜，models.json 降级为兜底。
//
// 为什么在服务端查、而不是让浏览器直接查 api.github.com：
//   · 国内访客直连 api.github.com 常在 TLS 握手就被掐断（实测 17ms 即断），
//     服务端从 Vercel 出网不受影响，访客只跟站点自己通信；
//   · GitHub 匿名限流 60 次/小时/出口 IP —— 函数内置 5 分钟结果缓存，热实例
//     几乎不再打 GitHub。站点访问量大时，在 Vercel 项目里配 GITHUB_TOKEN
//     环境变量（细粒度 PAT，公共仓库只读不需要勾任何权限），限流升到 5000/小时。
//
// 页面侧的兜底关系（assets/js/app.js discoverFromApi）：
//   /api/models（本函数）→ 浏览器直连 GitHub Trees API → 仓库根 models.json
//   → index.html 内置清单。本函数挂了页面会自动走后面几步，不影响可用性。
//
// ⚠️ OWNER / REPO 与 assets/js/app.js 顶部的 REPO_OWNER / REPO_NAME 保持一致。
//    注意用 git remote 里的**当前**仓库全名（改名后旧名靠 GitHub 重定向，
//    jsDelivr / Trees API 对重定向的支持不可靠）。

var OWNER = 'ZhuangRenyang';
var REPO = 'live2d_v3';
var BRANCHES = ['master', 'main'];
var GITHUB_TIMEOUT_MS = 10000;
var CACHE_TTL_MS = 5 * 60 * 1000;

// 模块级缓存：每个热实例各存一份，冷启动才重新查 GitHub
var cache = { at: 0, body: null };

function pickHeader(token) {
  var h = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'live2d_v3-viewer'
  };
  if (token) h.Authorization = 'Bearer ' + token;
  return h;
}

function fetchTree(branch, token) {
  var url = 'https://api.github.com/repos/' + OWNER + '/' + REPO +
            '/git/trees/' + branch + '?recursive=1';
  var ctl = new AbortController();
  var timer = setTimeout(function () { ctl.abort(); }, GITHUB_TIMEOUT_MS);
  return fetch(url, { headers: pickHeader(token), signal: ctl.signal })
    .then(function (r) {
      if (!r.ok) throw new Error('GitHub Trees API HTTP ' + r.status + ' @ ' + branch);
      return r.json();
    })
    .then(function (d) {
      clearTimeout(timer);
      if (!d || !Array.isArray(d.tree)) throw new Error('Trees API 响应里没有 tree 字段 @ ' + branch);
      return d.tree;
    }, function (e) {
      clearTimeout(timer);
      throw e;
    });
}

// Trees API 的扁平文件列表 → models.json 同构清单条目。
// 字段口径与 models_tool.py scan_models 保持一致（path/file/name/group/parts），
// 这样页面 decorate() 消化两种来源的条目完全走同一条路。
// motions / mocVersion / missing 那些需要逐个打开 model3.json 才能统计的字段
// 这里**故意不给**（服务端逐个拉文件太贵）—— 页面对缺省值有现成的降级显示。
function treeToEntries(tree) {
  var blobs = [];                                  // models/ 下所有文件：{ segs, size }
  for (var i = 0; i < tree.length; i++) {
    var t = tree[i];
    if (!t || t.type !== 'blob') continue;
    var p = String(t.path || '');
    if (!/^models\/.+/i.test(p)) continue;
    blobs.push({ segs: p.split('/').slice(1), size: t.size || 0 });
  }

  var dirs = {};                                   // 目录 → 该目录下的 .model3.json 们
  var re = /\.model3\.json$/i;
  for (var j = 0; j < blobs.length; j++) {
    var b = blobs[j];
    if (!re.test(b.segs[b.segs.length - 1])) continue;
    var d = b.segs.slice(0, -1).join('/');
    (dirs[d] = dirs[d] || []).push(b);
  }

  // 每个模型目录的「体积」= 目录子树内全部文件之和（页面渲染其实不用它，
  // 但保留字段与 models.json 同构，排查时有意义）
  function dirSize(segs) {
    var n = 0;
    for (var k = 0; k < blobs.length; k++) {
      var s = blobs[k].segs;
      if (s.length <= segs.length) continue;
      var same = true;
      for (var q = 0; q < segs.length; q++) {
        if (s[q] !== segs[q]) { same = false; break; }
      }
      if (same) n += blobs[k].size;
    }
    return n;
  }

  var out = [];
  Object.keys(dirs).forEach(function (d) {
    dirs[d].forEach(function (b) {
      var file = b.segs[b.segs.length - 1];
      var parts = b.segs.slice(0, -1);            // 相对 models/ 的目录段
      out.push({
        path: parts.join('/'),
        file: file,
        name: file.replace(/\.model3\.json$/i, ''),
        group: parts.length > 1 ? parts.slice(0, -1).join('/') : '',
        parts: parts,
        size: dirSize(parts)
      });
    });
  });

  // 与 models_tool.py 的排序键一致：(group, name) 不区分大小写升序
  out.sort(function (a, b) {
    var ga = a.group.toLowerCase(), gb = b.group.toLowerCase();
    if (ga !== gb) return ga < gb ? -1 : 1;
    var na = a.name.toLowerCase(), nb = b.name.toLowerCase();
    return na < nb ? -1 : na > nb ? 1 : 0;
  });
  return out;
}

module.exports = function (req, res) {
  if (req.method !== 'GET') {
    res.status(405).json({ error: '只支持 GET' });
    return;
  }
  if (cache.body && Date.now() - cache.at < CACHE_TTL_MS) {
    res.setHeader('Cache-Control', 'public, max-age=60');
    res.status(200).json(cache.body);
    return;
  }

  var token = process.env.GITHUB_TOKEN || '';
  var idx = 0;
  // 串行回退：master 不行才试 main —— 成功的那个分支之外绝不多打 GitHub 一发
  function attempt() {
    if (idx >= BRANCHES.length) {
      res.status(502).json({ error: 'GitHub Trees API 不可用（master/main 都没成功）' });
      return;
    }
    var branch = BRANCHES[idx++];
    fetchTree(branch, token).then(function (tree) {
      var entries = treeToEntries(tree);
      if (!entries.length) throw new Error('models/ 下没有找到任何 .model3.json @ ' + branch);
      cache.body = {
        version: 1,
        count: entries.length,
        models: entries,
        meta: { branch: branch, generated: new Date().toISOString(), source: 'github-trees' }
      };
      cache.at = Date.now();
      res.setHeader('Cache-Control', 'public, max-age=60');
      res.status(200).json(cache.body);
    }).catch(function (e) {
      console.error('[api/models] ' + branch + ' 分支失败：' + (e && e.message));
      attempt();
    });
  }
  attempt();
};
