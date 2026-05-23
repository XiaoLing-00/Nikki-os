# 苏暖暖桌面情感陪伴系统

这是一个面向毕业设计演示的桌面情感陪伴系统。系统以“苏暖暖（Nikki）”为角色，通过感知、对话、记忆、主动交互四个闭环，展示多智能体桌宠在桌面场景中的情境理解与陪伴能力。

## 1. 项目定位

系统采用多智能体架构：

- Observer Agent：后台观察用户当前桌面情境，判断是否需要主动关怀。
- Persona Agent：扮演苏暖暖，结合上下文、短期记忆和长期记忆生成回复。
- Memory Layer：短期 List 保存最近 15 轮上下文，SQLite 保存长期事实记忆。
- UI Layer：PyQt6 展示透明置顶 Codex pet sprite 桌宠、NPC 气泡输入框和动作状态。

苏暖暖的人设为：温柔、清醒、有陪伴感的设计师型桌宠伙伴，会称呼用户为“00”，说话自然克制，在学习、写作、查资料和报错时提供安静但及时的陪伴。

## 2. 功能闭环

### 感知闭环

低频后台感知使用 `pygetwindow` 获取活跃窗口标题，并归类为 VS Code、Bilibili、Browser 等场景。

高频主动感知由用户点击苏暖暖触发：系统截图当前屏幕，并调用 DashScope Qwen-VL 模型生成视觉摘要。

### 对话闭环

用户在悬浮气泡输入框中输入文本后，Persona Agent 会调用 DashScope Qwen-Max 生成结构化 JSON 回复。UI 根据 `emotion` 和 `action` 切换表情与动作，并展示对话气泡。

语音输入由气泡中的“语音”按钮触发：系统录制一段短音频，调用 DashScope Paraformer ASR 转为文本，再进入同一条 Persona Agent 对话链路。

当文本、语音或屏幕视觉请求正在等待模型返回时，气泡会显示“暖暖正在思考中/看屏幕中”的状态，输入按钮暂时禁用，避免界面看起来卡顿。

### 记忆闭环

短期记忆保留最近 15 轮对话。长期记忆使用 SQLite 存储用户事实、偏好和情绪标签，演示时不依赖 ChromaDB，降低部署复杂度。

### 主动交互闭环

Observer Agent 根据桌面场景和节奏触发主动关怀：

- 学习/工作模式：写代码、写论文、查资料、准备答辩 PPT 时给出低打扰鼓励。
- 休闲模式：看视频时以陪看和吃薯片表现为主；游戏、会议保持静默或小动作。
- 深夜/久坐模式：深夜关心休息，并结合当前任务提醒 00 最近做到哪一步。

## 3. 运行方式

建议使用 Python 3.10+。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

在项目根目录创建 `.env`：

```env
DASHSCOPE_API_KEY=sk-your-dashscope-api-key
```

启动：

```powershell
python main.py
```

可选配置：

```env
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
SOULPET_TEXT_MODEL=qwen-max-latest
SOULPET_VISION_MODEL=qwen3-vl-plus
SOULPET_ASR_MODEL=paraformer-realtime-v2
SOULPET_ASR_RECORD_SECONDS=5
SOULPET_ASR_SAMPLE_RATE=16000
```

## 4. 接口协议

Persona Agent 与 UI、Memory、Observer 之间统一使用以下 JSON：

```json
{
  "context": {
    "app": "VS Code",
    "topic": "毕业设计开发",
    "user_status": "concentrated",
    "perception_mode": "window_title"
  },
  "response": {
    "text": "你已经写了好久代码啦，暖暖陪你歇一小会儿呀。",
    "emotion": "gentle",
    "action": "motion_tilt_head"
  },
  "memory_update": {
    "key_info": "用户正在开发基于多智能体的桌宠系统",
    "sentiment": "positive"
  }
}
```

字段说明：

- `context.app`：当前活跃应用。
- `context.topic`：窗口标题或视觉摘要形成的主题。
- `context.user_status`：用户状态，如 `concentrated`、`relaxed`、`tired`。
- `response.text`：气泡中展示的文本。
- `response.emotion`：语义情绪标识，保留 `wink/love/cry/awkward/dizzy/rose/punch` 等兼容值，由 UI 映射到 sprite 状态。
- `response.action`：动作语义或 sprite 状态，如 `motion_think`、`reading`、`comfort`、`snack`，由 `ActionController` 统一归一化。
- `memory_update.key_info`：需要写入 SQLite 的长期事实记忆。

## 5. 模块实现

| 模块 | 文件 | 职责 |
| --- | --- | --- |
| 配置 | `config/settings.py` | 读取 `.env` 和环境变量，管理模型、数据库、资源路径 |
| 日志 | `utils/logger.py` | 写入 `data/logs/soulpet.log` |
| 短期记忆 | `memory/short_memory.py` | 保存最近 15 轮对话 |
| 长期记忆 | `memory/long_memory.py` | SQLite 事实记忆与应用活跃时长 |
| 感知 | `perception/context_builder.py` | 生成低频窗口上下文与高频视觉上下文 |
| 模型服务 | `services/llm_service.py` | 调用 DashScope OpenAI 兼容接口 |
| 语音识别 | `services/asr_service.py` | 录制短音频并调用 DashScope Paraformer ASR |
| Observer | `agents/observer_agent.py` | 勤奋、休闲、深夜主动触发 |
| Persona | `agents/persona_agent.py` | 人设提示词、结构化回复、记忆写入 |
| UI | `ui/main_window.py` | 透明置顶窗口、气泡输入、右键菜单、后台线程 |
| Sprite Pet | `ui/sprite_pet_widget.py` | Codex pet atlas 与自定义动作 strip 渲染 |
| 动作控制 | `ui/action_controller.py` | 情绪、场景与动作语义到 sprite 状态的映射 |
| 气泡 | `ui/speech_bubble.py` | NPC 对话框、输入框、语音按钮和菜单 |

## 6. 技术难点

1. 多源上下文统一：窗口标题和视觉摘要都被规整为 `context`，使 Agent 不关心感知来源。
2. 结构化大模型输出：Persona Agent 强制模型输出 JSON，保证 UI 和记忆层稳定消费。
3. 非阻塞交互：DashScope 请求在线程池中执行，避免 PyQt 主线程卡顿。
4. 截图隐私保护：高频视觉感知使用临时截图文件，Qwen-VL 调用结束后立即删除，不做本地持久化。
5. 桌宠渲染稳定性：通过固定 8x9 Codex pet atlas 和可选动作 strip，避免 Live2D 图层与动作库限制。
6. 记忆轻量化：SQLite 支撑演示所需长期记忆，ChromaDB 可作为后续向量检索优化方向。

## 7. 目录结构

```text
agents/        Observer Agent 与 Persona Agent
assets/        Codex pet atlas、动作 strip 与旧资源归档
config/        配置读取
memory/        短期记忆、长期记忆、记忆触发
perception/    窗口标题、截图、上下文构建
services/      DashScope 与 ASR 服务接口
ui/            PyQt6 桌宠窗口、sprite 渲染、动作控制与气泡
utils/         日志工具
```
