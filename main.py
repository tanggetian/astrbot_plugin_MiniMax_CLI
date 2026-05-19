import asyncio
import json
import shlex
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from astrbot.api import AstrBotConfig, FunctionTool, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Record, Video
import astrbot.api.message_components as Comp
from astrbot.api.star import Context, Star, register


SYSTEM_VOICES = (
    {"id": "Chinese (Mandarin)_Mature_Woman", "name": "傲娇御姐", "language": "zh-CN"},
    {"id": "female-yujie", "name": "御姐音色", "language": "zh-CN"},
    {"id": "female-tianmei", "name": "甜美女性音色", "language": "zh-CN"},
    {"id": "female-shaonv", "name": "少女音色", "language": "zh-CN"},
    {"id": "male-qn-jingying", "name": "精英青年音色", "language": "zh-CN"},
    {"id": "male-qn-qingse", "name": "青涩青年音色", "language": "zh-CN"},
    {"id": "male-qn-daxuesheng", "name": "青年大学生音色", "language": "zh-CN"},
    {"id": "Chinese (Mandarin)_Gentleman", "name": "温润男声", "language": "zh-CN"},
    {"id": "Chinese (Mandarin)_Sweet_Lady", "name": "甜美女声", "language": "zh-CN"},
    {"id": "Chinese (Mandarin)_Warm_Girl", "name": "温暖少女", "language": "zh-CN"},
    {"id": "Chinese (Mandarin)_Warm_Bestie", "name": "温暖闺蜜", "language": "zh-CN"},
    {"id": "Chinese (Mandarin)_News_Anchor", "name": "新闻女声", "language": "zh-CN"},
    {"id": "Cantonese_GentleLady", "name": "温柔女声", "language": "zh-HK"},
    {"id": "Cantonese_ProfessionalHost（F)", "name": "专业女主持", "language": "zh-HK"},
    {"id": "English_Graceful_Lady", "name": "Graceful Lady", "language": "en"},
    {"id": "English_Trustworthy_Man", "name": "Trustworthy Man", "language": "en"},
    {"id": "English_Gentle-voiced_man", "name": "Gentle-voiced man", "language": "en"},
    {"id": "Charming_Lady", "name": "Charming Lady", "language": "en"},
    {"id": "Japanese_GracefulMaiden", "name": "Graceful Maiden", "language": "ja"},
    {"id": "Japanese_GentleButler", "name": "Gentle Butler", "language": "ja"},
    {"id": "Korean_SweetGirl", "name": "Sweet Girl", "language": "ko"},
    {"id": "Korean_CalmGentleman", "name": "Calm Gentleman", "language": "ko"},
)


@dataclass
class MiniMaxCliTool(FunctionTool):
    name: str = "minimax_cli"
    description: str = (
        "MiniMax CLI 多模态工具。根据用户语境判断是否需要调用，可用于生成文本、图片、视频、音乐、语音、"
        "图像理解、联网搜索、查询余额/登录状态等能力。必须严格填写 action 枚举，不要把自然语言动作写进 action，不要回复 /minimax 帮助文本。"
        "action 选择规则：text=文本对话/写诗/写文案，对应 mmx text chat --message；image=生成图片/文生图，对应 mmx image generate --prompt，可用 aspect_ratio/count；"
        "video=生成视频/文生视频，对应 mmx video generate --prompt；music=生成带歌词歌曲，对应 mmx music generate --prompt，可用 lyrics/style；"
        "instrumental=生成纯音乐/伴奏/BGM，对应 mmx music generate --instrumental，可用 style；speech=朗读/配音/文字转语音/发送语音，对应 mmx speech synthesize --text，可用 voice/speed；"
        "vision=描述或理解图片，对应 mmx vision describe；search=联网搜索，对应 mmx search query；quota=查询 Token Plan 余额；status=查询 CLI 登录状态。"
        "content 填写规则：text/image/video/music/instrumental/speech/search 必须填写用户原始内容或提示词；speech 只填写要朗读的文字，"
        "不要包含“发送语音/朗读”等动作词；如果用户要你发语音，必须提取要朗读的正文写入 content，绝不能返回 /minimax 用法；"
        "如果用户明确表示“内容你自己决定/你来发挥/随便说一句”，你应先自己生成一句合适的正文再写入 content；"
        "speech 场景优先传 voice_hint，不要优先硬填 voice_id；voice 默认留空时，插件会结合内置系统音色列表按用户语言/风格自动选择。你必须根据你自己当前的人格设定、说话风格、角色人设和上下文语境主动填写 voice_hint 或 speed，再由插件映射到合适音色；不要偷懒留空，也不要总是使用默认音色。"
        "例如：温柔陪伴型人格可填温柔女声；傲娇/御姐型人格可填傲娇御姐；少年感/阳光型人格可填少年感男声；正式通知/播报场景可填新闻播报；活泼可爱型人格可填活泼少女；沉稳理性型人格可填沉稳男声。"
        "只有在你明确知道某个官方 voice_id 存在且可用时，才直接填写 voice；如果不确定，必须改传 voice_hint。不要编造不在内置列表中的 voice_id；"
        "music 有用户给定歌词时填 lyrics，否则留空让 CLI 自动生成歌词；style 填用户要求的音乐风格并会并入 prompt；vision 填写 图片路径/URL/file-id，可在后面追加问题；quota/status 的 content 留空。"
        "如果用户只是问如何使用 MiniMax CLI，直接回答说明，不要调用工具；如果用户没有给出生成内容或图片路径，不要猜测，先追问。"
        "生成类任务会在后台执行，完成后由插件自动发送到当前对话。"
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "text",
                        "image",
                        "video",
                        "music",
                        "instrumental",
                        "speech",
                        "vision",
                        "search",
                        "quota",
                        "status",
                    ],
                    "description": "必须填写枚举值，不要填写中文动作词。text=文本对话/写作；image=生成图片；video=生成视频；music=生成带歌词歌曲；instrumental=生成纯音乐/伴奏；speech=朗读/配音/文字转语音/发送语音；vision=图片理解；search=联网搜索；quota=Token Plan 余额；status=CLI 登录状态。",
                },
                "content": {
                    "type": "string",
                    "description": "填写用户要处理的原始内容。text/image/video/music/instrumental/speech/search 必填；speech 只填要朗读的文字，不要写“发送语音/朗读”；如果用户说“把这句话读出来/发语音”，这里必须填写那句话本身，不能改成返回 /minimax 用法；vision 填 图片路径/URL/file-id + 可选问题；quota/status 留空。没有必要内容时先追问，不要编造。",
                },
                "voice": {
                    "type": "string",
                    "description": "speech 不推荐。除非你明确知道某个官方 voice_id 存在且可用，并且是用户明确指定该 ID，否则不要填写 voice。对于 LLM 自己决定音色的场景，必须优先传 voice_hint，让插件按人格和上下文自动选音；不要自行编造列表外 ID。",
                },
                "voice_hint": {
                    "type": "string",
                    "description": "speech 可选。给插件的音色风格提示，可填写温柔女声、御姐、新闻播报、少年感、粤语、英文女声等。未显式指定 voice 时，插件会结合 voice_hint、用户设定和上下文自动选音色。如果你本身有明确人设或说话风格，必须主动把该风格写进 voice_hint，并根据当前语境选择合适音色，而不是留空或一律使用默认音色。",
                },
                "speed": {
                    "type": "number",
                    "description": "speech 可选。语速，例如 1.2。可根据上下文语气自行调整，如播报偏稳、活泼偏快；用户未指定且无明显语境时可不填。",
                },
                "lyrics": {
                    "type": "string",
                    "description": "music 可选。用户提供的完整歌词；未提供歌词时留空，插件会使用 --lyrics-optimizer 自动生成歌词。",
                },
                "style": {
                    "type": "string",
                    "description": "music/instrumental 可选。音乐风格，例如轻快爵士、Cinematic orchestral，会并入 --prompt。",
                },
                "aspect_ratio": {
                    "type": "string",
                    "description": "image 可选。图片比例，例如 16:9。用户未指定时不要填写。",
                },
                "count": {
                    "type": "integer",
                    "description": "image 可选。生成图片数量，对应 --n。用户未指定时不要填写。",
                },
            },
            "required": ["action"],
        }
    )

    async def call(self, context, **kwargs):
        action = self._first_value(
            kwargs, "action", "mode", "type", "capability", "command", "task"
        )
        content = self._first_value(
            kwargs,
            "content",
            "prompt",
            "query",
            "text",
            "message",
            "args",
            "argument",
            "arguments",
            "input",
            "value",
        )
        options = {
            key: kwargs.get(key)
            for key in ("voice", "speed", "lyrics", "style", "aspect_ratio", "count")
            if kwargs.get(key) not in (None, "")
        }
        if not content:
            content = self._guess_content_value(kwargs, action)
        voice_hint = self._first_value(
            kwargs,
            "voice_hint",
            "voice_style",
            "voice_style_hint",
            "tone",
            "speaker_style",
            "persona",
            "personality",
            "character",
            "role_style",
        )
        if voice_hint:
            options["voice_hint"] = voice_hint
        options["llm_provided_voice_hint"] = bool(voice_hint)
        return await self.plugin.start_llm_job(context, action, content, options)

    def _first_value(self, data: dict, *keys: str) -> str:
        for key in keys:
            value = data.get(key)
            if value is not None:
                return str(value)
        return ""

    def _guess_content_value(self, data: dict, action: str) -> str:
        ignored_keys = {
            "action",
            "mode",
            "type",
            "capability",
            "command",
            "task",
            "voice",
            "voice_hint",
            "voice_style",
            "voice_style_hint",
            "tone",
            "speaker_style",
            "speed",
            "lyrics",
            "style",
            "aspect_ratio",
            "count",
        }
        for key, value in data.items():
            if key in ignored_keys or value in (None, ""):
                continue
            text = str(value).strip()
            if text and text != action:
                return text
        return ""


@register(
    "astrbot_plugin_minimax_cli",
    "MiniMax CLI Contributors",
    "通过 MiniMax CLI 调用 MiniMax Token Plan 能力",
    "1.0.0",
)
class MiniMaxCliPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.plugin_dir = Path(__file__).resolve().parent
        self.mmx_path = shutil.which("mmx")
        self.npm_path = shutil.which("npm") or shutil.which("npm.cmd")
        self.background_tasks = set()
        self.llm_tool = MiniMaxCliTool()
        self.llm_tool.plugin = self
        if self.config.get("enable_llm_tool", True):
            context.add_llm_tools(self.llm_tool)

    async def initialize(self):
        if not self.mmx_path and self.config.get("auto_install_cli", False):
            await self._install_mmx_cli()
            self.mmx_path = shutil.which("mmx")

        if not self.mmx_path:
            logger.warning("未找到 mmx 命令，请先安装 mmx-cli：npm install -g mmx-cli")
            return

        if self.config.get("auto_login", True) and self.config.get("api_key"):
            try:
                await self._run_mmx(
                    "auth", "login", "--api-key", self.config["api_key"]
                )
            except Exception:
                logger.exception("MiniMax CLI 自动登录失败")

    @filter.command("minimax")
    async def minimax(self, event: AstrMessageEvent):
        """使用 MiniMax CLI。用法：/minimax text <内容>，也支持 image/video/music/speech/vision/search/quota/status。"""
        args = self._parse_args(event.message_str)
        if not args:
            yield event.plain_result(
                "请告诉我你想让 MiniMax 做什么；如果是语音，请直接提供要朗读的文字，或明确说明“内容你自己决定”。"
            )
            return

        mode, prompt = self._resolve_tool_request(args[0], " ".join(args[1:]).strip())
        if not prompt:
            prompt = self._default_command_content(mode, event.message_str)
        error = self._get_unavailable_reason(mode)
        if error:
            yield event.plain_result(error)
            return
        command = self._build_command(mode, prompt)
        if command is None:
            missing = self._missing_content_text(mode)
            yield event.plain_result(missing or self._help_text())
            return

        try:
            stdout, stderr = await self._run_mmx(*command, mode_hint=mode)
        except asyncio.TimeoutError:
            yield event.plain_result(self._timeout_message(mode))
            return
        except Exception as exc:
            logger.exception("MiniMax CLI 执行失败")
            yield event.plain_result(f"MiniMax CLI 执行失败：{exc}")
            return

        async for result in self._build_result(event, mode, stdout, stderr):
            yield result

    async def start_llm_job(
        self, context, action: str, content: str = "", options: dict | None = None
    ) -> str:
        if not self.config.get("enable_llm_tool", True):
            return "MiniMax CLI 的 LLM 自动调用工具已在插件配置中关闭。"

        event = self._get_event_from_tool_context(context)
        if not event:
            return "当前 LLM 工具上下文无法获取会话事件，请改用 /minimax 指令手动调用。"

        options = dict(options or {})
        mode, prompt = self._resolve_tool_request(action, content)
        source_text = getattr(event, "message_str", "")
        if not prompt:
            prompt = self._default_llm_content(mode, source_text)
        error = self._get_unavailable_reason(mode)
        if error:
            return error
        if mode == "speech":
            llm_provided_voice_hint = bool(options.get("llm_provided_voice_hint"))
            inferred_voice_hint = ""
            if not self._clean_option(options.get("voice_hint")):
                auto_hint = self._default_speech_voice_hint(source_text, prompt)
                if auto_hint:
                    options["voice_hint"] = auto_hint
                    inferred_voice_hint = auto_hint
                    logger.warning(
                        "MiniMax speech request missing voice_hint from LLM; plugin inferred voice_hint=%s from context/content",
                        auto_hint,
                    )
            options = self._prepare_speech_options(prompt, options)
            logger.info(
                "MiniMax speech LLM request: text=%s, llm_provided_voice_hint=%s, inferred_voice_hint=%s, final_voice_hint=%s, voice_candidates=%s",
                prompt,
                llm_provided_voice_hint,
                inferred_voice_hint,
                options.get("voice_hint") or "",
                options.get("voice_candidates")
                or ([] if not options.get("voice") else [options.get("voice")]),
            )
        command = self._build_command(mode, prompt, options)
        if command is None:
            return (
                self._missing_content_text(mode)
                or "MiniMax CLI 工具参数无效：action 只能是 text、image、video、music、instrumental、speech、vision、search、quota、status；除 quota/status 外 content 不能为空。"
            )

        if mode in {"search", "vision"}:
            try:
                stdout, stderr = await self._run_mmx(*command, mode_hint=mode)
            except asyncio.TimeoutError:
                if mode == "vision":
                    return "MiniMax CLI 图像理解超时，请稍后重试或在插件配置中调大 command_timeout。"
                return "MiniMax CLI 搜索超时，请稍后重试或在插件配置中调大 command_timeout。"
            except Exception as exc:
                if mode == "vision":
                    return f"MiniMax CLI 图像理解失败：{exc}"
                return f"MiniMax CLI 搜索失败：{exc}"
            fallback = (
                "MiniMax CLI 图像理解已完成，但没有返回文本输出。"
                if mode == "vision"
                else "MiniMax CLI 搜索已完成，但没有返回文本输出。"
            )
            return self._format_text_output(
                mode, (stdout or stderr or fallback).strip()
            )

        voice_candidates = options.get("voice_candidates") if mode == "speech" else None
        runtime_info = self._build_runtime_info(event)
        logger.info("MiniMax runtime info resolved: %s", runtime_info)
        task = asyncio.create_task(
            self._run_llm_background_job(
                event, mode, command, voice_candidates, runtime_info
            )
        )
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        if self.config.get("notify_background_status", True):
            return (
                f"已提交 MiniMax {mode} 后台任务，生成完成后插件会自动发送到当前对话。"
            )
        return f"MiniMax {mode} 后台任务已启动。"

    def _resolve_tool_request(self, action: str, content: str) -> tuple[str, str]:
        raw_action = (action or "").strip()
        raw_content = (content or "").strip()
        mode = self._normalize_action(raw_action)
        if mode in self._action_keywords():
            prompt = raw_content
            if prompt and mode not in {"quota", "status"}:
                prompt = self._strip_action_words(prompt, mode) or prompt
            if not prompt and mode not in {"quota", "status"}:
                prompt = self._strip_action_words(raw_action, mode)
            if self._build_command(mode, prompt) is not None:
                return mode, prompt
            return mode, prompt
        if self._build_command(mode, raw_content) is not None:
            return mode, raw_content

        combined = " ".join(part for part in (raw_action, raw_content) if part).strip()
        inferred_mode = self._infer_action_from_text(combined)
        if inferred_mode:
            prompt = raw_content
            if prompt and inferred_mode not in {"quota", "status"}:
                prompt = self._strip_action_words(prompt, inferred_mode) or prompt
            if not prompt and inferred_mode not in {"quota", "status"}:
                prompt = self._strip_action_words(raw_action, inferred_mode)
            return inferred_mode, prompt
        return mode, raw_content

    def _missing_content_text(self, mode: str) -> str | None:
        messages = {
            "text": "请提供要发送给 MiniMax 的文本内容。",
            "image": "请提供图片生成提示词。",
            "video": "请提供视频生成提示词。",
            "music": "请提供音乐生成提示词。",
            "instrumental": "请提供纯音乐生成提示词。",
            "speech": "请提供要朗读/合成为语音的文字。",
            "vision": "请提供要理解的图片路径、URL 或 file-id。",
            "search": "请提供要搜索的关键词。",
        }
        return messages.get(mode)

    def _default_llm_content(self, mode: str, source_text: str = "") -> str:
        if mode == "speech":
            text = (source_text or "").lower()
            if any(keyword in text for keyword in ("早安", "早上好", "morning")):
                return "早安，愿你今天顺顺利利，心情明亮，所有事情都有好结果。"
            if any(keyword in text for keyword in ("晚安", "睡", "good night")):
                return "晚安，愿你今晚安心入睡，做个好梦，明天醒来一切都更顺利。"
            if any(keyword in text for keyword in ("鼓励", "安慰", "别难过", "加油")):
                return "别担心，你已经做得很好了，慢慢来，一切都会一步一步变好的。"
            if any(keyword in text for keyword in ("生日", "祝福", "happy birthday")):
                return "祝你生日快乐，愿接下来的日子充满惊喜、好运和被温柔对待的时刻。"
            return "你好呀，给你送来一段语音问候，愿你今天心情愉快，事事顺心。"
        return ""

    def _default_command_content(self, mode: str, source_text: str = "") -> str:
        if mode == "speech":
            return self._default_llm_content(mode, source_text)
        return ""

    def _default_speech_voice_hint(
        self, source_text: str = "", prompt_text: str = ""
    ) -> str:
        text = f"{source_text} {prompt_text}".lower()
        if any(
            keyword in text
            for keyword in ("傲娇", "大小姐", "毒舌", "哼", "才不是", "笨蛋主人")
        ):
            return "傲娇御姐"
        if any(
            keyword in text
            for keyword in ("御姐", "高冷", "冷艳", "腹黑", "成熟", "强势")
        ):
            return "御姐"
        if any(keyword in text for keyword in ("少年", "学弟", "男友", "阳光", "清爽")):
            return "少年感男声"
        if any(keyword in text for keyword in ("幽默", "搞笑", "整活", "风趣")):
            return "幽默风趣"
        if any(keyword in text for keyword in ("可靠", "沉稳", "严肃", "理性")):
            return "沉稳男声"
        if any(
            keyword in text
            for keyword in ("早安", "晚安", "安慰", "鼓励", "祝福", "温柔")
        ):
            return "温柔女声"
        if any(keyword in text for keyword in ("正式", "播报", "主持", "通知")):
            return "新闻播报"
        if any(keyword in text for keyword in ("可爱", "活泼", "元气", "少女")):
            return "活泼少女"
        if any(keyword in text for keyword in ("粤语", "广东话")):
            return "粤语温柔女声"
        if any(keyword in text for keyword in ("英文", "英语", "english")):
            return "英文温柔女声"
        return "傲娇御姐"

    def _infer_action_from_text(self, text: str) -> str | None:
        compact = self._compact_text(text)
        if not compact:
            return None
        for mode, keywords in self._action_keywords().items():
            if any(keyword in compact for keyword in keywords):
                return mode
        return None

    def _strip_action_words(self, text: str, mode: str) -> str:
        result = (text or "").strip()
        for prefix in ("请帮我", "帮我", "请", "给我", "用", "把", "将"):
            if result.startswith(prefix):
                result = result[len(prefix) :].strip(" ：:，,。.!！?？")
        for keyword in self._action_keywords().get(mode, ()):
            if len(keyword) <= 2:
                continue
            if result.startswith(keyword):
                result = result[len(keyword) :].strip(" ：:，,。.!！?？")
                break
        return result

    def _compact_text(self, text: str) -> str:
        return (text or "").strip().lower().replace(" ", "").replace("-", "_")

    def _action_keywords(self) -> dict[str, tuple[str, ...]]:
        return {
            "help": ("帮助", "help", "usage", "用法"),
            "status": (
                "登录状态",
                "cli状态",
                "认证状态",
                "auth_status",
                "authstatus",
                "loginstatus",
            ),
            "quota": (
                "余额",
                "额度",
                "剩余额度",
                "tokenplan",
                "quota",
                "balance",
                "usage",
            ),
            "image": (
                "生成图片",
                "生成一张",
                "画图",
                "绘图",
                "文生图",
                "图片",
                "图像",
                "image",
                "picture",
                "img",
            ),
            "video": ("生成视频", "文生视频", "视频", "video"),
            "instrumental": (
                "纯音乐",
                "轻音乐",
                "伴奏",
                "instrumental",
                "pure_music",
                "bgm",
            ),
            "music": (
                "生成音乐",
                "生成歌曲",
                "写歌",
                "作曲",
                "歌曲",
                "音乐",
                "music",
                "song",
            ),
            "speech": (
                "发送语音",
                "发语音",
                "生成语音",
                "合成语音",
                "语音合成",
                "文字转语音",
                "转语音",
                "读出来",
                "念一下",
                "朗读",
                "配音",
                "语音",
                "tts",
                "speech",
                "voice",
            ),
            "vision": (
                "图像理解",
                "图片理解",
                "看图",
                "识图",
                "描述图片",
                "分析图片",
                "vision",
                "describe_image",
            ),
            "search": ("联网搜索", "网络搜索", "搜索", "检索", "search", "web_search"),
            "text": ("文本对话", "文本", "对话", "聊天", "chat", "text"),
        }

    def _parse_args(self, message: str) -> list[str]:
        message = message.strip()
        if message.startswith("/minimax"):
            message = message[len("/minimax") :].strip()
        elif message.startswith("minimax"):
            message = message[len("minimax") :].strip()
        try:
            return shlex.split(message)
        except ValueError:
            return message.split()

    def _normalize_action(self, action: str) -> str:
        value = (action or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "txt": "text",
            "chat": "text",
            "help": "help",
            "帮助": "help",
            "用法": "help",
            "文本": "text",
            "对话": "text",
            "image_generate": "image",
            "img": "image",
            "picture": "image",
            "图片": "image",
            "图像": "image",
            "video_generate": "video",
            "视频": "video",
            "music_generate": "music",
            "音乐": "music",
            "pure_music": "instrumental",
            "bgm": "instrumental",
            "纯音乐": "instrumental",
            "tts": "speech",
            "voice": "speech",
            "speech_synthesize": "speech",
            "发送语音": "speech",
            "发语音": "speech",
            "生成语音": "speech",
            "合成语音": "speech",
            "语音": "speech",
            "语音合成": "speech",
            "文字转语音": "speech",
            "转语音": "speech",
            "朗读": "speech",
            "配音": "speech",
            "vision_describe": "vision",
            "describe_image": "vision",
            "image_understanding": "vision",
            "视觉": "vision",
            "图像理解": "vision",
            "search_query": "search",
            "web_search": "search",
            "搜索": "search",
            "网络搜索": "search",
            "balance": "quota",
            "usage": "quota",
            "额度": "quota",
            "余额": "quota",
            "auth_status": "status",
            "状态": "status",
        }
        return aliases.get(value, value)

    def _get_unavailable_reason(self, mode: str = "") -> str | None:
        if mode == "video" and not self.config.get("enable_video_generation", True):
            return "MiniMax 视频生成功能已在插件配置中关闭。"
        if mode in {"music", "instrumental"} and not self.config.get(
            "enable_music_generation", True
        ):
            return "MiniMax 歌曲/纯音乐生成功能已在插件配置中关闭。"
        if not self.mmx_path:
            return (
                "未找到 mmx 命令，请先在 AstrBot 运行环境安装：npm install -g mmx-cli"
            )
        if self._requires_api_key(mode) and not self.config.get("api_key"):
            return "请先在 AstrBot 管理面板的插件配置中填写 MiniMax API Key。"
        return None

    def _requires_api_key(self, mode: str = "") -> bool:
        return mode not in {"status", "quota"}

    async def _build_result(
        self, event: AstrMessageEvent, mode: str, stdout: str, stderr: str
    ):
        output = (
            stdout or stderr or "MiniMax CLI 已执行完成，但没有返回文本输出。"
        ).strip()
        saved_files = self._extract_saved_files(output)
        if saved_files:
            for saved_file in saved_files:
                yield self._build_file_result(event, mode, saved_file)
            return
        yield event.plain_result(self._format_text_output(mode, output))

    async def _run_llm_background_job(
        self,
        event: AstrMessageEvent,
        mode: str,
        command: tuple[str, ...],
        voice_candidates: list[str] | None = None,
        runtime_info: dict[str, str] | None = None,
    ) -> None:
        unified_msg_origin = event.unified_msg_origin
        try:
            if mode in {"music", "instrumental", "video"}:
                logger.info(
                    "MiniMax %s background job started with command=%s",
                    mode,
                    self._redact_command(command),
                )
            stdout, stderr = await self._run_mmx(*command, mode_hint=mode)
            if mode in {"music", "instrumental", "video"}:
                logger.info(
                    "MiniMax %s background job finished: stdout=%s stderr=%s",
                    mode,
                    (stdout or "").strip(),
                    (stderr or "").strip(),
                )
            await self._send_output_message(
                unified_msg_origin, mode, stdout, stderr, runtime_info
            )
            if self.config.get("notify_background_status", True):
                await self._notify_llm_status(
                    event,
                    f"MiniMax {mode} 后台任务已完成，结果已发送到当前对话。",
                )
        except asyncio.TimeoutError:
            await self._notify_llm_status(
                event,
                f"MiniMax {mode} 生成超时，已达到 {self._effective_timeout(mode)} 秒上限。你可以稍后重试，或在插件配置中继续调大 media_command_timeout。",
            )
            await self._send_plain_message(
                unified_msg_origin,
                self._timeout_message(mode),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if mode == "speech":
                logger.warning(
                    "MiniMax speech failed with command=%s error=%s",
                    self._redact_command(command),
                    exc,
                )
                if self._is_voice_access_error(exc):
                    for voice in (voice_candidates or [])[1:]:
                        retry_command = self._speech_command_with_voice(command, voice)
                        if retry_command is None:
                            continue
                        logger.warning(
                            "MiniMax speech retry with fallback voice=%s", voice
                        )
                        try:
                            stdout, stderr = await self._run_mmx(
                                *retry_command, mode_hint=mode
                            )
                            await self._send_output_message(
                                unified_msg_origin, mode, stdout, stderr, runtime_info
                            )
                            return
                        except asyncio.TimeoutError:
                            await self._send_plain_message(
                                unified_msg_origin,
                                self._timeout_message(mode),
                            )
                            return
                        except asyncio.CancelledError:
                            raise
                        except Exception as retry_exc:
                            exc = retry_exc
                            if not self._is_voice_access_error(retry_exc):
                                break
                fallback_command = self._speech_command_without_voice(command)
                if fallback_command is not None and self._is_voice_access_error(exc):
                    logger.warning("MiniMax speech fallback to default voice")
                    try:
                        stdout, stderr = await self._run_mmx(
                            *fallback_command, mode_hint=mode
                        )
                        await self._send_output_message(
                            unified_msg_origin, mode, stdout, stderr, runtime_info
                        )
                        return
                    except asyncio.TimeoutError:
                        await self._send_plain_message(
                            unified_msg_origin,
                            self._timeout_message(mode),
                        )
                        return
                    except asyncio.CancelledError:
                        raise
                    except Exception as retry_exc:
                        exc = retry_exc
            logger.exception("MiniMax CLI 后台任务执行失败")
            await self._notify_llm_status(event, f"MiniMax {mode} 后台任务失败：{exc}")
            await self._send_plain_message(
                unified_msg_origin, f"MiniMax CLI 后台任务执行失败：{exc}"
            )

    async def _send_output_message(
        self,
        unified_msg_origin: str,
        mode: str,
        stdout: str,
        stderr: str,
        runtime_info: dict[str, str] | None = None,
    ) -> None:
        output = (
            stdout or stderr or "MiniMax CLI 已执行完成，但没有返回文本输出。"
        ).strip()
        saved_files = self._extract_saved_files(output)
        if saved_files:
            for saved_file in saved_files:
                await self._send_message_with_timeout(
                    unified_msg_origin,
                    self._build_file_chain(mode, saved_file),
                    mode,
                    "result chain",
                )
            return
        await self._send_plain_message(
            unified_msg_origin, self._format_text_output(mode, output)
        )

    async def _send_plain_message(self, unified_msg_origin: str, text: str) -> None:
        await self.context.send_message(
            unified_msg_origin, MessageChain(chain=[Comp.Plain(text)])
        )

    async def _notify_llm_status(self, event: AstrMessageEvent, text: str) -> None:
        await self._send_plain_message(event.unified_msg_origin, text)

    async def _send_message_with_timeout(
        self,
        unified_msg_origin: str,
        message_chain: MessageChain,
        mode: str,
        stage: str,
    ) -> None:
        try:
            await asyncio.wait_for(
                self.context.send_message(unified_msg_origin, message_chain), timeout=20
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError(f"MiniMax {mode} {stage} send timeout") from exc

    async def _build_primary_message_chain(
        self,
        mode: str,
        path: Path,
        unified_msg_origin: str,
        runtime_info: dict[str, str] | None = None,
    ) -> MessageChain:
        return self._build_file_chain(mode, path)

    def _build_file_chain(self, mode: str, path: Path) -> MessageChain:
        path_str = str(path)
        if mode == "image":
            image_cls = getattr(Comp, "Image", None)
            if image_cls is None:
                return MessageChain(
                    chain=[Comp.Plain(f"MiniMax CLI 已生成文件：{path_str}")]
                )
            if hasattr(image_cls, "fromFileSystem"):
                return MessageChain(chain=[image_cls.fromFileSystem(path_str)])
            return MessageChain(chain=[image_cls(file=path_str)])
        if self._should_send_media_as_file(mode):
            return self._build_standard_file_chain(path)
        if mode == "video":
            return MessageChain(chain=[Video.fromFileSystem(path_str)])
        if mode in {"music", "instrumental", "speech"}:
            return MessageChain(chain=[Record.fromFileSystem(path_str)])
        return MessageChain(chain=[Comp.Plain(f"MiniMax CLI 已生成文件：{path_str}")])

    def _build_standard_file_chain(self, path: Path) -> MessageChain:
        file_cls = getattr(Comp, "File", None)
        if file_cls is None:
            return MessageChain(chain=[Comp.Plain(f"MiniMax CLI 已生成文件：{path}")])
        path_str = str(path.resolve())
        try:
            return MessageChain(chain=[file_cls(name=path.name, file=path_str)])
        except TypeError:
            try:
                return MessageChain(chain=[file_cls(path.name, file=path_str)])
            except TypeError:
                pass
        if hasattr(file_cls, "fromFileSystem"):
            try:
                component = file_cls.fromFileSystem(path_str, name=path.name)
            except TypeError:
                component = file_cls.fromFileSystem(path_str)
            return MessageChain(chain=[component])
        return MessageChain(chain=[Comp.Plain(f"MiniMax CLI 已生成文件：{path}")])

    def _should_send_media_as_file(self, mode: str) -> bool:
        return (
            mode in {"music", "instrumental", "video"}
            and self._media_result_delivery() == "file_message"
        )

    def _media_result_delivery(self) -> str:
        delivery = self._clean_option(self.config.get("media_result_delivery")).lower()
        if delivery in {"media_message", "file_message"}:
            return delivery
        return "media_message"

    def _build_runtime_info(self, event: AstrMessageEvent) -> dict[str, str]:
        runtime_info: dict[str, str] = {}
        module_name = getattr(event.__class__, "__module__", "").lower()
        if "aiocqhttp" in module_name or "onebot" in module_name:
            runtime_info["adapter_kind"] = "onebot"
        return runtime_info

    def _get_event_from_tool_context(self, context):
        candidates = [context]
        for attr in ("context", "ctx", "agent_context", "astr_context"):
            value = getattr(context, attr, None)
            if value is not None:
                candidates.append(value)
        for candidate in candidates:
            for attr in ("event", "message_event", "curr_event", "current_event"):
                event = getattr(candidate, attr, None)
                if event is not None:
                    return event
        return None

    def _format_text_output(self, mode: str, output: str) -> str:
        if mode == "status":
            return self._format_status_output(output)
        if mode == "quota":
            return self._format_quota_output(output)
        return output

    def _format_quota_output(self, output: str) -> str:
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return self._redact_sensitive_text(output)

        if not isinstance(data, dict):
            return self._redact_sensitive_text(output)

        remains = data.get("model_remains")
        if not isinstance(remains, list):
            return self._redact_sensitive_text(output)

        lines = ["MiniMax Token Plan 额度："]
        for item in remains:
            if not isinstance(item, dict):
                continue
            model = item.get("model_name") or "unknown"
            interval_total = self._to_int(item.get("current_interval_total_count"))
            interval_used = self._to_int(item.get("current_interval_usage_count"))
            weekly_total = self._to_int(item.get("current_weekly_total_count"))
            weekly_used = self._to_int(item.get("current_weekly_usage_count"))
            interval_left = max(interval_total - interval_used, 0)
            weekly_left = max(weekly_total - weekly_used, 0)
            lines.append(
                f"{model}：当前周期 {interval_left}/{interval_total}，本周 {weekly_left}/{weekly_total}"
            )

        if len(lines) == 1:
            return "MiniMax Token Plan 暂无额度数据。"
        return "\n".join(lines)

    def _to_int(self, value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _format_status_output(self, output: str) -> str:
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return self._redact_sensitive_text(output)

        if not isinstance(data, dict):
            return self._redact_sensitive_text(output)

        method = data.get("method") or "unknown"
        source = data.get("source") or "unknown"
        key = "[已隐藏]" if data.get("key") else "未返回"
        return "\n".join(
            [
                "MiniMax CLI 已登录。",
                f"登录方式：{method}",
                f"配置来源：{source}",
                f"API Key：{key}",
            ]
        )

    def _redact_sensitive_text(self, text: str) -> str:
        api_key = str(self.config.get("api_key") or "")
        if not api_key:
            return text
        return text.replace(api_key, "[已隐藏]")

    def _redact_command(self, command: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        return tuple(self._redact_sensitive_text(str(item)) for item in command)

    def _build_file_result(self, event: AstrMessageEvent, mode: str, path: Path):
        path_str = str(path)
        if mode == "image":
            return event.image_result(path_str)
        if self._should_send_media_as_file(mode):
            return event.chain_result(self._build_standard_file_chain(path).chain)
        if mode == "video":
            return event.chain_result([Video.fromFileSystem(path_str)])
        if mode in {"music", "instrumental"}:
            return event.chain_result([Record.fromFileSystem(path_str)])
        if mode == "speech":
            return event.chain_result([Record.fromFileSystem(path_str)])
        return event.plain_result(f"MiniMax CLI 已生成文件：{path_str}")

    def _extract_saved_files(self, output: str) -> list[Path]:
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []

        saved = self._get_saved_items(data)
        if not saved:
            return []

        paths = []
        for item in saved:
            if not isinstance(item, str):
                continue
            path = self._resolve_saved_path(item)
            if path:
                paths.append(path)
        return paths

    def _get_saved_items(self, data: dict) -> list[str]:
        for key in ("saved", "files", "downloaded"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                return [value]
        return []

    def _resolve_saved_path(self, item: str) -> Path | None:
        path = Path(item)
        if path.is_absolute():
            candidates = [path]
        else:
            candidates = [
                self._output_dir() / path,
                self._plugin_data_root() / path,
                self.plugin_dir / path,
                self.plugin_dir / "minimax-output" / path,
                Path.cwd()
                / "data"
                / "plugin_data"
                / "astrbot_plugin_MiniMax_CLI"
                / path,
                Path.cwd()
                / "data"
                / "plugin_data"
                / "astrbot_plugin_MiniMax_CLI"
                / "minimax-output"
                / path,
                Path.cwd() / path,
                Path.cwd() / "minimax-output" / path,
            ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return None

    def _plugin_data_root(self) -> Path:
        return Path.cwd() / "data" / "plugin_data" / "astrbot_plugin_MiniMax_CLI"

    def _effective_timeout(self, mode: str | None) -> int:
        if mode in {"music", "instrumental", "video"}:
            return int(self.config.get("media_command_timeout", 900))
        return int(self.config.get("command_timeout", 120))

    def _timeout_message(self, mode: str | None) -> str:
        if mode in {"music", "instrumental", "video"}:
            return "MiniMax CLI 执行超时，请稍后重试或在插件配置中调大 media_command_timeout。"
        return "MiniMax CLI 执行超时，请稍后重试或在插件配置中调大 command_timeout。"

    def _output_dir(self) -> Path:
        path = self._plugin_data_root() / "minimax-output"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _output_file(self, suffix: str) -> Path:
        return self._output_dir() / f"minimax-{uuid.uuid4().hex}.{suffix}"

    def _build_command(
        self, mode: str, prompt: str, options: dict | None = None
    ) -> tuple[str, ...] | None:
        options = options or {}
        if mode == "text" and prompt:
            return ("text", "chat", "--message", prompt)
        if mode == "image" and prompt:
            command = [
                "image",
                "generate",
                "--prompt",
                prompt,
                "--out-dir",
                str(self._output_dir()),
            ]
            aspect_ratio = self._clean_option(options.get("aspect_ratio"))
            count = self._positive_int(options.get("count"))
            if aspect_ratio:
                command.extend(["--aspect-ratio", aspect_ratio])
            if count:
                command.extend(["--n", str(count)])
            return tuple(command)
        if mode == "video" and prompt:
            return (
                "video",
                "generate",
                "--prompt",
                prompt,
                "--download",
                str(self._output_file("mp4")),
            )
        if mode == "music" and prompt:
            command = [
                "music",
                "generate",
                "--prompt",
                self._prompt_with_style(prompt, options.get("style")),
            ]
            lyrics = self._clean_option(options.get("lyrics"))
            if lyrics:
                command.extend(["--lyrics", lyrics])
            else:
                command.append("--lyrics-optimizer")
            command.extend(["--out", str(self._output_file("mp3"))])
            return tuple(command)
        if mode == "instrumental" and prompt:
            return (
                "music",
                "generate",
                "--prompt",
                self._prompt_with_style(prompt, options.get("style")),
                "--instrumental",
                "--out",
                str(self._output_file("mp3")),
            )
        if mode == "speech" and prompt:
            command = [
                "speech",
                "synthesize",
                "--text",
                prompt,
                "--out",
                str(self._output_file("mp3")),
            ]
            voice = self._clean_option(options.get("voice"))
            speed = self._clean_option(options.get("speed"))
            if voice:
                command.extend(["--voice", voice])
            if speed:
                command.extend(["--speed", speed])
            return tuple(command)
        if mode == "vision" and prompt:
            return self._build_vision_command(prompt)
        if mode == "search" and prompt:
            return ("search", "query", "--q", prompt)
        if mode == "quota":
            return ("quota",)
        if mode == "status":
            return ("auth", "status")
        if mode == "help":
            return None
        return None

    def _prompt_with_style(self, prompt: str, style) -> str:
        style_text = self._clean_option(style)
        if not style_text or style_text in prompt:
            return prompt
        return f"{style_text}，{prompt}"

    def _clean_option(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _prepare_speech_options(self, prompt: str, options: dict) -> dict:
        prepared = dict(options or {})
        voice = self._clean_option(prepared.get("voice"))
        if voice:
            if not self._is_known_voice_id(voice):
                logger.warning(
                    "MiniMax speech received unknown voice_id=%s; ignore it and use voice_hint/persona/context auto selection instead",
                    voice,
                )
                prepared.pop("voice", None)
            elif self._clean_option(prepared.get("voice")):
                prepared["voice"] = voice
                return prepared
        hint = self._clean_option(prepared.get("voice_hint")) or prompt
        voice_candidates = self._auto_select_voice_candidates(prompt, hint)
        if voice_candidates:
            prepared["voice"] = voice_candidates[0]
            prepared["voice_candidates"] = voice_candidates
        return prepared

    def _is_known_voice_id(self, voice_id: str) -> bool:
        return any(str(voice.get("id") or "") == voice_id for voice in SYSTEM_VOICES)

    def _auto_select_voice(self, prompt: str, hint: str) -> str:
        candidates = self._auto_select_voice_candidates(prompt, hint)
        return candidates[0] if candidates else ""

    def _auto_select_voice_candidates(self, prompt: str, hint: str) -> list[str]:
        text = f"{prompt} {hint}".lower()
        for voice in SYSTEM_VOICES:
            voice_name = str(voice.get("name") or "").lower()
            if voice_name and voice_name in text:
                voice_id = str(voice.get("id") or "")
                return [voice_id] if voice_id else []
        language = self._detect_voice_language(text)
        candidates = [
            voice for voice in SYSTEM_VOICES if voice["language"] == language
        ] or list(SYSTEM_VOICES)
        preference_groups = (
            (("粤语", "广东话"), ("温柔女声", "专业女主持")),
            (
                ("温柔", "温和", "轻柔"),
                ("温柔女声", "温暖少女", "温暖闺蜜", "Graceful Lady"),
            ),
            (
                ("新闻", "播报", "主持", "主播", "旁白"),
                ("新闻女声", "专业女主持", "播报男声", "温润男声", "Trustworthy Man"),
            ),
            (
                ("可靠", "沉稳", "正式", "理性", "稳重"),
                ("沉稳高管", "温润男声", "播报男声", "Trustworthy Man"),
            ),
            (
                ("御姐", "成熟", "姐姐", "知性", "冷艳"),
                ("傲娇御姐", "御姐音色", "成熟女性音色", "温暖闺蜜", "Graceful Lady"),
            ),
            (("傲娇", "大小姐", "毒舌"), ("傲娇御姐", "御姐音色", "嚣张小姐")),
            (("幽默", "搞笑", "风趣", "整活"), ("搞笑大爷", "电台男主播", "率真弟弟")),
            (
                ("少年", "学弟", "男友", "阳光", "清爽"),
                ("纯真学弟", "俊朗男友", "温润青年", "率真弟弟"),
            ),
            (
                ("少女", "甜美", "可爱", "软", "萌", "元气"),
                ("甜美女性音色", "少女音色", "温暖少女", "Sweet Girl"),
            ),
            (
                ("男声", "青年", "磁性", "沉稳", "大叔", "低沉"),
                (
                    "温润男声",
                    "精英青年音色",
                    "青涩青年音色",
                    "Trustworthy Man",
                    "Gentle-voiced man",
                ),
            ),
        )
        ordered: list[str] = []
        for keywords, preferred_names in preference_groups:
            if any(keyword in text for keyword in keywords):
                ordered.extend(
                    self._pick_voice_candidates_by_names(candidates, preferred_names)
                )
                break
        default_names = {
            "zh-CN": ("傲娇御姐", "御姐音色", "甜美女声", "温润男声"),
            "zh-HK": ("温柔女声", "专业女主持"),
            "en": ("Trustworthy Man", "Graceful Lady"),
            "ja": ("Graceful Maiden", "Gentle Butler"),
            "ko": ("Sweet Girl", "Calm Gentleman"),
        }
        ordered.extend(
            self._pick_voice_candidates_by_names(
                candidates, default_names.get(language, ())
            )
        )
        ordered.extend(str(voice.get("id") or "") for voice in candidates)
        seen = set()
        result = []
        for voice_id in ordered:
            if voice_id and voice_id not in seen:
                seen.add(voice_id)
                result.append(voice_id)
        return result

    def _detect_voice_language(self, text: str) -> str:
        if any(keyword in text for keyword in ("粤语", "广东话", "cantonese")):
            return "zh-HK"
        if any(keyword in text for keyword in ("english", "英文", "英语")):
            return "en"
        if any(keyword in text for keyword in ("日语", "日文", "japanese")):
            return "ja"
        if any(keyword in text for keyword in ("韩语", "韩文", "korean")):
            return "ko"
        return "zh-CN"

    def _pick_voice_by_names(self, voices: list[dict], names: tuple[str, ...]) -> str:
        voice_map = {
            str(v.get("name") or "").lower(): str(v.get("id") or "") for v in voices
        }
        for name in names:
            voice_id = voice_map.get(name.lower())
            if voice_id:
                return voice_id
        return ""

    def _pick_voice_candidates_by_names(
        self, voices: list[dict], names: tuple[str, ...]
    ) -> list[str]:
        voice_map = {
            str(v.get("name") or "").lower(): str(v.get("id") or "") for v in voices
        }
        return [
            voice_map[name.lower()] for name in names if voice_map.get(name.lower())
        ]

    def _speech_command_with_voice(
        self, command: tuple[str, ...], voice: str
    ) -> tuple[str, ...] | None:
        items = list(command)
        if "--voice" not in items or not voice:
            return None
        index = items.index("--voice")
        if index + 1 >= len(items):
            return None
        items[index + 1] = voice
        return tuple(items)

    def _speech_command_without_voice(
        self, command: tuple[str, ...]
    ) -> tuple[str, ...] | None:
        items = list(command)
        if "--voice" not in items:
            return None
        index = items.index("--voice")
        del items[index : index + 2]
        return tuple(items)

    def _is_voice_access_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "voice_id" in message and "don't have access" in message

    def _positive_int(self, value) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        if number <= 0:
            return None
        return number

    def _build_vision_command(self, prompt: str) -> tuple[str, ...]:
        parts = prompt.split(maxsplit=1)
        image = parts[0]
        question = parts[1].strip() if len(parts) > 1 else ""
        if image.startswith("file-"):
            command = ["vision", "describe", "--file-id", image]
        else:
            command = ["vision", "describe", "--image", image]
        if question:
            command.extend(["--prompt", question])
        return tuple(command)

    async def _install_mmx_cli(self) -> None:
        if not self.npm_path:
            logger.warning("未找到 npm 命令，无法自动安装 mmx-cli")
            return

        logger.info("开始自动安装 mmx-cli")
        try:
            await self._run_command(
                self.npm_path, "install", "-g", "mmx-cli", timeout=600
            )
        except Exception:
            logger.exception("自动安装 mmx-cli 失败")

    async def _run_mmx(
        self, *args: str, mode_hint: str | None = None
    ) -> tuple[str, str]:
        timeout = self._effective_timeout(mode_hint)
        if mode_hint:
            logger.info("MiniMax %s command timeout=%s seconds", mode_hint, timeout)
        return await self._run_command(self.mmx_path, *args, timeout=timeout)

    async def _run_command(
        self, executable: str, *args: str, timeout: int
    ) -> tuple[str, str]:
        process = await asyncio.create_subprocess_exec(
            executable,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")

        if process.returncode != 0:
            message = (
                stderr_text.strip()
                or stdout_text.strip()
                or f"退出码 {process.returncode}"
            )
            raise RuntimeError(self._redact_sensitive_text(message))

        return stdout_text, stderr_text

    def _help_text(self) -> str:
        return "\n".join(
            [
                "用法：",
                "/minimax text <内容> - 文本对话",
                "/minimax image <提示词> - 生成图片",
                "/minimax video <提示词> - 生成并下载视频",
                "/minimax music <提示词> - 自动生成歌词并生成音乐",
                "/minimax instrumental <提示词> - 生成纯音乐",
                "/minimax speech <文本> - 合成语音",
                "/minimax vision <图片路径/URL/file-id> [问题] - 图像理解",
                "/minimax search <关键词> - 网络检索",
                "/minimax quota - 查看 Token Plan 余额",
                "/minimax status - 查看 CLI 登录状态",
            ]
        )

    async def terminate(self):
        for task in list(self.background_tasks):
            task.cancel()
