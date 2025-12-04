# AstrBot 插件开发指南（中文）

## 项目概览

这是一个 AstrBot 插件模板（`helloworld`），用于演示如何编写基于事件的聊天机器人插件。插件通过注册命令处理器和事件监听器来扩展功能。

## 关键结构与架构
- 入口文件：`main.py` — 包含继承自 `Star` 的插件类与命令处理器示例。
- 元数据：`metadata.yaml` — 插件的注册与发现信息（名称、版本、作者、仓库等）。
- 编程模式：事件驱动的异步架构，Handler 使用 `async` 函数并通过 `yield` 返回结果对象。

## 插件核心结构（可直接参考 `main.py`）

### 插件注册（装饰器形式）

```python
@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
```

装饰器参数含义：
- 第1项：插件唯一 ID（示例：`"helloworld"`）
- 第2项：作者名
- 第3项：描述（中文）
- 第4项：版本号

### 常见方法
- `__init__(self, context: Context)`：接收注入的 `Context` 对象。
- `async initialize(self)`：实例化后（可选）执行的异步初始化逻辑。
- `async terminate(self)`：插件卸载/停用时的清理逻辑（可选）。

## 命令处理器模式（在 `main.py` 中有示例）

### 注册命令
```python
@filter.command("helloworld")
async def helloworld(self, event: AstrMessageEvent):
    """命令说明（会被用作帮助描述）"""
    yield event.plain_result("response")
```

要点：
- 使用 `@filter.command("name")` 注册 `/name` 命令。
- 处理器接收 `AstrMessageEvent`，通过 `yield event.plain_result(...)` 发送纯文本结果。
- 处理函数必须是 `async`，内部如需执行异步调用请使用 `await`。

### 事件数据访问示例

```python
user_name = event.get_sender_name()    # 发送者昵称
message_str = event.message_str        # 纯文本消息
message_chain = event.get_messages()   # 消息链（包含富媒体组件）
```

调试建议：使用 `from astrbot.api import logger` 并调用 `logger.info(...)` 或 `logger.error(...)`。

## `metadata.yaml` 要点（示例位于仓库根目录）

```yaml
name: helloworld            # 插件识别名（建议小写、唯一）
display_name: helloworld    # 展示用名称（兼容性说明见上文）
desc: AstrBot 插件示例。
version: v1.3.0
author: Soulter
repo: https://github.com/Soulter/helloworld
```

注意：仓库里的示例没有强制 `astrbot_plugin_` 前缀，但在部分平台/版本中，插件命名可能要求特定前缀——以目标部署环境为准。

## 开发与调试工作流（基于本仓库可直接操作的最小流程）

1. 在 `main.py` 中修改或添加命令处理器。
2. 更新 `metadata.yaml`（版本号或描述变更）。
3. 将插件包部署到 AstrBot 实例或本地测试环境，触发命令（如发送 `/helloworld`）验证行为。
4. 查看 AstrBot 日志以排查问题；在 handler 内使用 `logger.info()` 输出关键数据。

（本仓库没有包含自动化测试或依赖管理文件；如果需要在项目中引入第三方库，请在仓库根目录新增 `requirements.txt` 并记录安装步骤。）

## 导入约定与常见组件

推荐统一从 `astrbot.api.*` 导入：
- 事件与过滤器：`from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult`
- 插件基类与注册：`from astrbot.api.star import Context, Star, register`
- 日志：`from astrbot.api import logger`
- 富消息组件（如需要）：`from astrbot.api.message_components import *`

## 常见模式与注意事项（来自仓库示例）

- 处理器通过 `yield event.plain_result(...)` 发送结果，而非直接 `return`。
- 若需要处理富媒体消息，使用 `event.get_messages()` 并按类型解析组件。
- 多个命令处理器可以写在同一个插件类内并通过多个 `@filter.command()` 注册。
- 建议在每个 handler 添加简短的 docstring，便于自动生成/显示帮助文本（示例已在 `main.py` 中使用）。

---

如果你希望我将这份中文指南进一步精简、补充到 README 中，或添加部署与本地测试命令，请告诉我要补充的方向。期待你的反馈以便迭代。 
