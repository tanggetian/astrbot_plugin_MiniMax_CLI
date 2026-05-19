# astrbot_plugin_minimax_cli

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
- `notify_background_status`：是否显示后台任务开始/结束提示
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

## 参考

- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot 插件配置文档](https://docs.astrbot.app/dev/star/guides/plugin-config.html)
- [MiniMax CLI 文档](https://platform.minimaxi.com/docs/token-plan/minimax-cli)
