from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SceneSpec:
    scene_id: str
    name: str
    user_status: str
    proactive_level: str
    default_action: str
    description: str


SCENES: dict[str, SceneSpec] = {
    "coding": SceneSpec("coding", "写代码", "concentrated", "medium", "review", "安静陪写，连续工作一小时后提醒休息。"),
    "paper_writing": SceneSpec("paper_writing", "写论文/文档", "concentrated", "medium", "review", "陪 00 一起写，帮忙理清结构和进度。"),
    "research": SceneSpec("research", "查资料", "active", "medium", "review", "像学习搭子一样一起看资料。"),
    "ppt_defense": SceneSpec("ppt_defense", "答辩/PPT 准备", "concentrated", "high", "review", "帮 00 看结构、节奏和答辩准备状态。"),
    "error_debug": SceneSpec("error_debug", "报错/调试", "concentrated", "high", "failed", "先安慰，再直接帮 00 看错误线索。"),
    "video_relax": SceneSpec("video_relax", "看视频/摸鱼", "relaxed", "low", "idle", "陪 00 一起看，娱乐太久再轻轻拉回任务。"),
    "game": SceneSpec("game", "游戏", "relaxed", "silent", "waiting", "不打扰，只做待机小动作。"),
    "meeting": SceneSpec("meeting", "会议", "active", "silent", "idle", "腾讯会议或钉钉中完全静默。"),
    "idle_long": SceneSpec("idle_long", "长时间无操作", "idle", "medium", "waiting", "半小时无操作后轻声询问。"),
    "late_night": SceneSpec("late_night", "深夜使用电脑", "tired", "medium", "waiting", "关心休息，并提醒近期要忙的事情。"),
    "chat_social": SceneSpec("chat_social", "聊天/社交", "active", "low", "idle", "尽量不插话。"),
    "file_manage": SceneSpec("file_manage", "文件整理", "active", "low", "review", "轻量陪伴整理。"),
    "ai_chat": SceneSpec("ai_chat", "AI 对话", "active", "medium", "review", "像一起研究问题。"),
    "daily_unknown": SceneSpec("daily_unknown", "未知日常", "active", "low", "idle", "不强行猜测，保持轻陪伴。"),
}


BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "browser.exe",
    "360se.exe",
    "qqbrowser.exe",
}

CODE_PROCESSES = {
    "code.exe",
    "pycharm64.exe",
    "idea64.exe",
    "webstorm64.exe",
    "devenv.exe",
}

DOC_PROCESSES = {
    "winword.exe",
    "wps.exe",
    "wpp.exe",
    "et.exe",
}

PPT_PROCESSES = {
    "powerpnt.exe",
    "wpp.exe",
}

MEETING_PROCESSES = {
    "wemeetapp.exe",
    "tencentmeeting.exe",
    "dingtalk.exe",
}

GAME_HINTS = (
    "steam",
    "unity",
    "unreal",
    "genshin",
    "原神",
    "崩坏",
    "明日方舟",
    "minecraft",
    "league of legends",
    "英雄联盟",
)

VIDEO_HINTS = (
    "bilibili",
    "哔哩哔哩",
    "b站",
    "youtube",
    "douyin",
    "抖音",
    "爱奇艺",
    "腾讯视频",
    "优酷",
)

PAPER_HINTS = (
    "论文",
    "毕业设计",
    "实验报告",
    "开题",
    "文献综述",
    "系统设计",
    ".doc",
    ".docx",
)

RESEARCH_HINTS = (
    "搜索",
    "百度",
    "google",
    "必应",
    "bing",
    "论文",
    "文献",
    "资料",
    "教程",
    "csdn",
    "知乎",
    "github",
    "arxiv",
    "知网",
)

ERROR_HINTS = (
    "traceback",
    "exception",
    "error",
    "failed",
    "failure",
    "报错",
    "错误",
    "异常",
    "崩溃",
    "crash",
)

AI_HINTS = (
    "chatgpt",
    "deepseek",
    "kimi",
    "通义",
    "豆包",
    "claude",
    "gemini",
)

CHAT_HINTS = (
    "微信",
    "wechat",
    "qq",
)


def classify_scene(context: dict) -> dict:
    title = str(context.get("window_title", ""))
    process = str(context.get("process_name", "")).lower()
    app = str(context.get("app", ""))
    topic = str(context.get("topic", ""))
    vision_summary = str(context.get("vision_summary", ""))
    text = " ".join((title, process, app, topic, vision_summary)).lower()

    scene_id = _scene_id_from_text(text, process, app)
    spec = SCENES[scene_id]
    confidence = "high" if scene_id not in {"daily_unknown", "research"} else "medium"
    if context.get("perception_mode") == "vision" and vision_summary:
        confidence = "high"

    return {
        "id": spec.scene_id,
        "name": spec.name,
        "user_status": spec.user_status,
        "proactive_level": spec.proactive_level,
        "default_action": spec.default_action,
        "description": spec.description,
        "confidence": confidence,
    }


def _scene_id_from_text(text: str, process: str, app: str) -> str:
    if process in MEETING_PROCESSES or any(item in text for item in ("腾讯会议", "tencent meeting", "钉钉", "dingtalk")):
        return "meeting"
    if any(item in text for item in ERROR_HINTS):
        return "error_debug"
    if process in CODE_PROCESSES or app == "VS Code":
        return "coding"
    if any(item in text for item in ("powerpoint", "ppt", "答辩", "演示文稿")) or process in PPT_PROCESSES:
        return "ppt_defense"
    if process in DOC_PROCESSES or app in {"Word", "WPS"} or any(item in text for item in PAPER_HINTS):
        return "paper_writing"
    if any(item in text for item in AI_HINTS):
        return "ai_chat"
    if any(item in text for item in VIDEO_HINTS) or app == "Bilibili":
        return "video_relax"
    if any(item in text for item in GAME_HINTS):
        return "game"
    if any(item in text for item in CHAT_HINTS):
        return "chat_social"
    if "explorer.exe" in process or "资源管理器" in text or "文件资源管理器" in text:
        return "file_manage"
    if process in BROWSER_PROCESSES or app == "Browser" or any(item in text for item in RESEARCH_HINTS):
        return "research"
    return "daily_unknown"
