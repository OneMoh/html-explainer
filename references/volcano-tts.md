# 火山引擎语音合成 2.0（豆包）接入说明

`html-explainer` 支持两个配音引擎。**跑 `tts_build.py` 之前必须先问用户用哪个**（SKILL.md 确认点 3）。

| 引擎 | 密钥 | 音色 | 词级时间戳 | 什么时候用 |
|---|---|---|---|---|
| `edge`（默认） | 不需要 | edge-tts 内置音色 | 有（`WordBoundary`） | 默认。免费、开箱可用、够用 |
| `volcano` | **需要 API Key** | 豆包语音合成模型 2.0 | 有（`sentence.words[]`） | 想要更好的音质/更自然的语气 |

两个引擎产出的 `audio-manifest.json` **结构完全一致**（`boundaries` 都是「秒 + 原始坐标系」），
所以 `timeline_build.py` / `subs.py` / 渲染器**零改动**。

---

## 1. 密钥纪律（读这一节就够）

用户裁定：**agent 不许读取 `tts.env`，仓库不许记录它。**

这不是靠自觉，是靠结构保证的：

```
你（手工填一次）→ tts.env（被 .gitignore 忽略）
                      ↓  只有 scripts/tts_volcano.py 读它
               tts_volcano.synthesize()  ← agent 只调这个，永远拿不到密钥值
                      ↓
               openspeech.bytedance.com
```

- **agent 侧**：只调用 `scripts/tts_volcano.py`（或 `tts_build.py --provider volcano`）。
  不需要 `cat` / `grep` / 读 `tts.env` —— 接口包会自己读。
  想确认密钥状态时跑 `tts_setup.py --status`，它输出的是**脱敏摘要**。
- **密钥不进输出**：接口包保证不打印、不记录、不回显密钥；异常信息过 `_redact()` 脱敏
  （只抹「本次实际加载的密钥值」和 `AKLT…` 形态 token，reqid / logid 保留 —— 排查要线索）。
- **密钥不进仓库**：`.gitignore` 忽略 `tts.env` / `*.env` / `*.key` / `*.pem` / `secrets/`；
  `check_integrity.py` 有专门的**密钥防线**检查（见第 5 节）。
- **密钥不进分发**：`package_skill.py` 排除 `tts.env` / `*.env` / `*.key` / `*.pem`
  （模板 `tts.env.example` 保留，用户要照抄它）。
- **兜底层（真正的安全边界）**：万一还是泄了，损失要可控 —— 建议在火山控制台用
  **子账号只授 TTS 权限**、设**用量告警与限额**，并且密钥**可随时轮换**。

> 说句实话：合成代码是 agent 在本机执行的，运行时进程里密钥对脚本可见，
> 「agent 绝对读不到」做不到。上面保证的是**不进对话、不进仓库、不进日志、不进分发**，
> 把泄露半径收敛成一次可撤销的事故。

---

## 2. 三步配置

```bash
# ① 选方案（会问用户：edge 还是火山）
python <skill>/scripts/tts_setup.py --project .
#    选火山且缺 tts.env → 生成带注释的空模板并退出（退出码 2，NEXT_ACTION=fill_env）

# ② 用户手工填 tts.env（这一步 agent 不参与）
#    火山引擎控制台 → 语音技术 → API Key 管理
#    https://console.volcengine.com/speech/new/setting/apikeys

# ③ 回来测连接 + 选音色
python <skill>/scripts/tts_setup.py --project . --check       # 测连接
python <skill>/scripts/tts_setup.py --project . --list-voices # 列候选音色
python <skill>/scripts/tts_setup.py --project . --provider volcano --voice "解说小明 2.0"
```

配置写进 `project.json` 的 `provider` / `voice` / `rate` 三个字段。
**方案一旦选定立刻落盘** —— 因为填密钥会中断流程，若不落盘，用户回来跑 `--check` 时
`project.json` 还写着 `edge`，会静默去测 edge（这个坑真踩过）。

非交互场景（agent 代跑）看这三个标记：`NEXT_ACTION=ask_user_provider` /
`NEXT_ACTION=fill_env` / `NEXT_ACTION=ask_user_voice` / `NEXT_ACTION=done`。

---

## 3. tts.env 格式

```ini
VOLC_API_KEY=            # 必填。也可以用旧版鉴权（见下）
VOLC_RESOURCE_ID=seed-tts-2.0
VOLC_APP_ID=             # 可选：旧版鉴权（APP ID + Access Token）
VOLC_ACCESS_KEY=         # 可选：填了则与 VOLC_APP_ID 配对使用
```

探测顺序（`tts_volcano.env_candidates()`，与向导保持一致）：
`$TTS_ENV_FILE` → `<项目>/tts.env` → `<技能目录>/tts.env` → `~/.workbuddy/tts.env`

资源 ID：**预置音色用 `seed-tts-2.0`**；你自己克隆的音色用 `seed-icl-2.0`。

---

## 4. 接口规格（2026-09 核对官方文档）

```
POST https://openspeech.bytedance.com/api/v3/tts/unidirectional
Header: X-Api-Key / X-Api-Resource-Id / X-Api-Request-Id(uuid) / Content-Type: application/json
Body:   {user:{uid}, req_params:{text, speaker, audio_params:{format,sample_rate,bit_rate,speech_rate}}}
```

**为什么选这条路**：这是 **HTTP Chunked 单向流式**——一次性发文本、流式收音频。
与 edge-tts 的形态同构（发一次、收一串），所以 `tts_build.py` 的缓存 / 硬超时 /
退避重试 / 裁静音 / 两级时钟逻辑全部原样复用。

**不用双向流式**（`wss://.../api/v3/tts/bidirection`）：那是给 LLM 实时对话设计的
（文本流式进、可打断、多轮 session 状态机）。离线出片用不上，纯开销。

### 响应：NDJSON，逐行 JSON

```jsonc
{"code":0, "message":"OK", "data":"<base64 音频块>", "sentence":{"text":"你好","words":[
    {"word":"你","startTime":0.195,"endTime":0.335,"confidence":0.9}]}}
{"code":0, "message":"OK", "data":"<base64 音频块>"}
{"code":20000000, "message":"OK", "data":null, "usage":{"text_words":7}}   // ★ 结束标记
```

**四个必须知道的点**：

1. **结束标记的 `code` 是 `20000000`,不是 `0`。** 只判 `code===0` 收音频会丢最后一段
   （症状：合并出来的音频末尾「嘎然而止」）。本包按 `code` 显式区分。
2. **★ 字级时间戳必须显式开 `audio_params.enable_subtitle: true`。**
   官方文档的响应示例里 `words[]` 是有值的，**很容易误以为默认就给** ——
   实测不传该参数 `words` **恒为空数组**（同文本对照：`false` → `words=0`，`true` → `words=10`）。
   它**不报错**：音频、时长、`sentence.text` 全正常，只有时间戳是空的；
   下游会静默退回按字数插值，字幕开始飘。本包默认开启。
   开了之后拿到的是字级 `word` / `startTime` / `endTime` / `confidence`（单位**秒**），
   即 edge-tts `WordBoundary` 的等价物，**不需要「强制对齐」那一步**。
   → 映射成 `{"text","offset_sec","duration_sec"}`。
   仅豆包 2.0 的**中英文**音色支持；拿到音频却没有时间戳时本包会在结果里塞 `warning`。
3. **`usage` 挂在结束标记那一行。** 解析循环若「先判结束标记 → `continue`」，
   就会**永远读不到计费字数（恒为 0）**，容易被误判成「免费额度」。
   另外**不传请求头 `X-Control-Require-Usage-Tokens-Return: *`，服务端根本不返回 `usage`**。
4. **单请求文本上限 ~200 字。** 超了本包按标点切分（不在词中间劈开），
   后续片段的词边界按前面片段用 ffmpeg 量出的实际时长平移。

参数换算：语速 `speech_rate ∈ [-50,100]`，映射 `倍率 = 1 + speech_rate/100`
（100 = 2.0 倍、-50 = 0.5 倍，线性）。`parse_rate_percent()` 统一接受
`"+8%"` / `"8"` / `0.08` / `8` 四种写法，`tts_setup.py` 与 `tts_build.py` 共用这一份
（**不要各写一份**：`tts_volcano.py` CLI 曾把中文音色名直接当 `speaker` 发出去，
被服务端以 `55000000 resource ID is mismatched with speaker…` 拒绝，看不出是没解析）。
音色名解析同理走 `resolve_voice_token()`。
默认 `sample_rate=24000` / `format=mp3` / `bit_rate=160000`。

**代理**：`openspeech.bytedance.com` 是**境内端点，默认绕过系统代理直连**。
本机常驻代理会让境内域名绕远甚至失败（见 lessons）。要强制走代理就设 `VOLC_PROXY`。

---

## 5. 密钥防线的自动化检查

`python scripts/check_integrity.py` 多跑两项：

```
  ✓ 密钥防线：.gitignore 已忽略 tts.env / *.env / *.key
  ✓ 密钥防线：仓库内未发现真实密钥（模板里的空赋值不算）
```

第二项会遍历仓库（跳过 `.git`/`node_modules`/二进制），抓两类形态：
非空密钥赋值（`VOLC_API_KEY=…`）与 `AKLT…` token。**空模板不算违规**，所以
`tts.env.example` 可以入库。CI 也跑这个 —— 它在无密钥环境下能通过。

---

## 6. 音色

`tts_setup.py --list-voices` 会列内置常用音色（可自定义 ID）。默认 **云舟 2.0**。
2.0 音色的 `voice_type` 都以 `_uranus_bigtts` 结尾。

| 音色 | voice_type | 定位 |
|---|---|---|
| 云舟 2.0 | `zh_male_m191_uranus_bigtts` | 男声 · 沉稳通用（默认） |
| 温暖阿虎 2.0 | `zh_male_wennuanahu_uranus_bigtts` | 男声 · 温暖 |
| 解说小明 2.0 | `zh_male_jieshuoxiaoming_uranus_bigtts` | 男声 · 解说 |
| 磁性解说男声 2.0 | `zh_male_cixingjieshuonan_uranus_bigtts` | 男声 · 磁性解说 |
| 悬疑解说 2.0 | `zh_male_xuanyijieshuo_uranus_bigtts` | 男声 · 悬疑叙事 |
| 小何 2.0 | `zh_female_xiaohe_uranus_bigtts` | 女声 · 通用 |
| Vivi 2.0 | `zh_female_vv_uranus_bigtts` | 女声 · 活泼通用 |
| 知性灿灿 2.0 | `zh_female_cancan_uranus_bigtts` | 女声 · 知性 |

完整列表（上百个）见官方音色文档：<https://docs.volcengine.com/docs/DoubaoVoice/Tonelist-1>

**注意**：切了引擎要重跑 `tts_build.py`（缓存 sig 含 provider，不会串音）；
语速标定结论不能跨引擎沿用 —— edge 的 `RATE` 与火山的 `speech_rate` 是两套刻度，
换引擎后如需精密控速要重新标定。另外 edge 独有的「相邻数字补逗号」处理对火山**不启用**：
它会改动送进去的文本、影响词边界与解说词的逐字对齐，而火山不熔读相邻数字。

---

## 7. 排查

| 现象 | 原因 / 处理 |
|---|---|
| `没有找到 tts.env` | 跑 `tts_setup.py --project .` 生成模板后填写 |
| `HTTP 401` / `Invalid X-Api-Key` | 密钥错、未开通服务，或该用旧版鉴权（填 `VOLC_APP_ID` + `VOLC_ACCESS_KEY`） |
| `55000000 resource ID is mismatched with speaker related resource` | ① **音色名没被解析成 ID**（`speaker` 只认 ID；1.3.1 前 `tts_build.py` 走了未解析的路径，已修）② 音色与资源 ID 不匹配（预置音色要配 `seed-tts-2.0`）③ 该音色未在控制台开通。**先确认日志里打印的是不是 `xxx_uranus_bigtts` 形态的 ID**，再去查 ②③ —— 否则会白测一圈音色 |
| `HTTP 404` | 音色与资源 ID 不匹配 —— 预置音色要配 `seed-tts-2.0` |
| `网络不可达` | 本包默认直连；若确实需要代理，设 `VOLC_PROXY=http://127.0.0.1:<port>` |
| 音频末尾「嘎然而止」 | 结束标记 `code=20000000` 的处理问题（本包已处理；自研代码要留意） |
| 字幕与音频错位 | 检查 `sentence.words[]` 是否被正确映射成 `offset_sec`（单位是**秒**） |
| 想确认测的到底是哪个引擎 | `--check` 会先打印 `测试方案：<provider>` |
