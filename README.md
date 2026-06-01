# astrbot_plugin_MiniMax_CLI

基于 `mmx-cli` 的 AstrBot 插件，用来把 MiniMax 的文本、图片、视频、音乐、纯音乐、语音、视觉理解和搜索能力接入 AstrBot。

MiniMax 插件负责生成和媒体结果策略。如果需要跨容器/跨设备文件发送，推荐配合使用 `astrbot_plugin_file_sender`。

## 插件划分

### MiniMax CLI 插件

路径：当前目录根部。

负责：

- `/minimax` 指令入口
- `minimax_cli` LLM 工具入口
- 文本、图片、视频、音乐、纯音乐、语音生成
- 图像理解与网络搜索
- `mmx-cli` 安装、登录、超时控制
- 歌曲/视频结果走媒体通道还是文件通道的策略控制

### 跨容器/跨设备文件发送

如果需要跨容器/跨设备文件发送，推荐使用 `astrbot_plugin_file_sender`。

## MiniMax 配置

必要配置：

- `api_key`：MiniMax API Key

常用配置：

- `auto_install_cli`：找不到 `mmx` 时自动安装，默认关闭
- `auto_login`：插件启动时自动执行 `mmx auth login`
- `enable_llm_tool`：是否注册 `minimax_cli`
- `enable_video_generation`：是否允许生成视频，默认开启
- `enable_music_generation`：是否允许生成歌曲/纯音乐，默认开启
- `command_timeout`：普通命令超时时间
- `media_command_timeout`：视频、音乐、纯音乐超时时间
- `notify_background_status`：是否显示后台任务提交、排队、开始和结束提示
- `media_result_delivery`：歌曲/视频结果发送通道

`media_result_delivery` 可选：

- `media_message`：默认值。歌曲/纯音乐走音频消息，视频走视频消息。
- `file_message`：歌曲/纯音乐/视频走 AstrBot 标准文件组件。

## MiniMax 指令

```text
/minimax text <内容>
/minimax image <提示词>
/minimax video <提示词>
/minimax music <提示词>
/minimax instrumental <提示词>
/minimax speech <文本>
/minimax vision <图片路径/URL/file-id> [问题]
/minimax search <关键词>
/minimax quota
/minimax status
```

示例：

```text
/minimax image 赛博朋克城市夜景，16:9
/minimax video 一只猫在窗边看夕阳
/minimax music 一首轻快的电子流行歌曲
/minimax speech 晚安，早点休息
```

## LLM 工具调用

插件注册了 `minimax_cli` LLM 工具，开启后 LLM 可根据用户语境自动调用 MiniMax 能力，无需手动输入 `/minimax` 指令。

通过配置 `enable_llm_tool` 控制是否注册此工具，默认开启。

### action 枚举

| action | 说明 | 对应 CLI 命令 |
|--------|------|---------------|
| `text` | 文本对话 / 写诗 / 写文案 | `mmx text chat --message` |
| `image` | 生成图片 / 文生图 | `mmx image generate --prompt` |
| `video` | 生成视频 / 文生视频 | `mmx video generate --prompt` |
| `music` | 生成带歌词歌曲 | `mmx music generate --prompt` |
| `instrumental` | 生成纯音乐 / 伴奏 / BGM | `mmx music generate --instrumental` |
| `speech` | 朗读 / 配音 / 文字转语音 | `mmx speech synthesize --text` |
| `vision` | 描述或理解图片 | `mmx vision describe` |
| `search` | 联网搜索 | `mmx search query` |
| `quota` | 查询 Token Plan 余额 | — |
| `status` | 查询 CLI 登录状态 | — |

### 参数说明

| 参数 | 适用 action | 必填 | 说明 |
|------|------------|------|------|
| `action` | 全部 | 是 | 枚举值，见上表 |
| `content` | text/image/video/music/instrumental/speech/search | 是 | 用户原始内容或提示词；speech 只填要朗读的文字；quota/status 留空 |
| `voice` | speech | 否 | 官方 voice_id，不确定时不要填写 |
| `voice_hint` | speech | 否 | 音色风格提示，如温柔女声、新闻播报、少年感男声等，优先于 voice |
| `speed` | speech | 否 | 语速，如 1.2 |
| `lyrics` | music | 否 | 用户提供的完整歌词，留空则自动生成 |
| `style` | music/instrumental | 否 | 音乐风格，如轻快爵士、Cinematic orchestral |
| `aspect_ratio` | image | 否 | 图片比例，如 16:9 |
| `count` | image | 否 | 生成图片数量 |

### 调用示例

用户说"画一只猫" → LLM 自动调用 `minimax_cli`，`action=image`，`content=一只猫`。

用户说"给我读一首诗" → LLM 自动调用 `minimax_cli`，`action=speech`，`content=（诗的正文）`，`voice_hint=温柔女声`。

## 输出行为

MiniMax 插件默认回传：

- 图片 -> 图片消息
- 视频 -> 视频消息
- 音乐 / 纯音乐 / 语音 -> 音频消息
- 无文件结果 -> 文本输出

如果 `media_result_delivery=file_message`：

- 视频 -> 标准文件组件
- 音乐 / 纯音乐 -> 标准文件组件
- 语音仍然走音频消息

如果需要跨容器/跨设备文件发送，推荐使用 `astrbot_plugin_file_sender`。

## 后台任务与排队

LLM 自动调用生成类任务时，插件会在后台执行生成，不阻塞 AstrBot 主线程。

- 图片、视频、语音分别按类型排队，同类型任务一个个生成。
- 音乐和纯音乐共用音乐队列，一个个生成。
- 图片、视频、音乐、语音属于不同队列，可以同时各自运行一个任务。
- 开启 `notify_background_status` 时，插件会主动提示当前同类队列任务数、前方等待数量、开始生成和完成状态。

## 常见问题

### 找不到 `mmx`

请确认：

- 已安装 Node.js / npm
- `npm install -g mmx-cli` 成功
- `mmx --version` 可正常输出

### 提示 API Key 未配置

请在 MiniMax 插件配置里填写 `api_key`。

### OneBot 文件发送出现 ENOENT

这类问题由独立 File Sender 插件处理。原因通常是协议端读取不到 AstrBot 容器内路径。

解决方向：

- OneBot 会话：File Sender 默认使用跨设备上传，请填写 NapCat HTTP 地址
- 跨容器/跨设备文件发送：推荐使用 `astrbot_plugin_file_sender`

### 视频、音乐生成太慢或超时

优先调大 MiniMax 插件的：

- `media_command_timeout`

## 更新日志

### v1.2.0

- 新增 LLM 自动调用生成任务的按类型后台队列：图片、视频、音乐、语音等同类任务串行处理，不同类型可并行处理。
- 新增生成任务排队状态提示：提交任务时提示当前同类队列数量和前方等待数量，排队任务开始生成时提示剩余数量。
- 优化视频、音乐等后台任务状态通知，避免只返回工具文本导致用户看不到排队情况。

## 参考

- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot 插件配置文档](https://docs.astrbot.app/dev/star/guides/plugin-config.html)
- [MiniMax CLI 文档](https://platform.minimaxi.com/docs/token-plan/minimax-cli)
