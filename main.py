from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("OneHANZIdaily", "YourName", "一个简单的插件,定时检索一个汉字并解释推送至对应群聊", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("oneHANZIdaily")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
# 1. 定义插件类，继承astrbot的Plugin基类
class DailyCharacterPlugin(Plugin):
    def __init__(self, bot: Bot):
        super().__init__(bot)
        # 初始化定时任务调度器
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        # 配置核心参数（需替换为自己的信息）
        self.target_qq = 123456789  # 推送目标QQ号/群号（群号需加前缀，如'group_123456'）
        self.llm_api_url = "https://api.xxx.com/chat/completions"  # 大模型API地址
        self.llm_api_key = "your_api_key_here"  # 大模型API密钥
        # 常用汉字库（可扩展，建议选常用字）
        self.character_list = [
            "山", "水", "风", "云", "日", "月", "星", "辰", "人", "心",
            "情", "理", "道", "德", "智", "勇", "信", "义", "和", "平"
        ]

    # 2. 注册插件（astrbot的插件注册规范）
    def register(self):
        # 添加定时任务：每天20:00执行推送任务
        self.scheduler.add_job(
            self.send_daily_character,
            "cron",
            hour=20,
            minute=0,
            second=0
        )
        self.scheduler.start()
        self.bot.logger.info("每日一字插件已加载，定时任务已启动")

    # 3. 随机获取一个汉字
    def get_random_character(self):
        return random.choice(self.character_list)

    # 4. 调用大模型API解读汉字
    def get_character_explanation(self, char):
        # 构造大模型Prompt（明确要求返回格式）
        prompt = f"""请详细解读汉字「{char}」，包含以下内容：
        1. 核心含义（分本义、引申义）；
        2. 词源（起源、字形演变简要说明）；
        3. 相关常用词汇（至少5个）；
        4. 实用造句（至少2个，覆盖不同场景）。
        要求语言简洁易懂，格式清晰，无需多余内容。"""

        # 调用大模型API（以OpenAI格式为例，其他平台需调整参数）
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.llm_api_key}"
        }
        data = {
            "model": "gpt-3.5-turbo",  # 替换为你的模型名（如spark-3.5、ernie-4.0等）
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }

        try:
            response = requests.post(self.llm_api_url, headers=headers, json=data, timeout=10)
            response.raise_for_status()  # 抛出HTTP错误
            result = response.json()
            # 提取大模型回复（不同平台返回字段不同，需适配）
            explanation = result["choices"][0]["message"]["content"].strip()
            return explanation
        except Exception as e:
            self.bot.logger.error(f"调用大模型失败：{str(e)}")
            return f"「{char}」解读获取失败，错误原因：{str(e)}"

    # 5. 拼接消息并推送
    async def send_daily_character(self):
        try:
            char = self.get_random_character()
            explanation = self.get_character_explanation(char)
            # 拼接最终消息
            msg_content = f"【每日一字】\n今日汉字：「{char}」\n\n{explanation}"
            # 调用astrbot的发送消息接口
            await self.bot.send_message(
                target=self.target_qq,
                message=Message(content=msg_content)
            )
            self.bot.logger.info(f"每日一字推送成功：{char}")
        except Exception as e:
            self.bot.logger.error(f"推送每日一字失败：{str(e)}")

# 6. 插件入口（astrbot加载插件的规范）
def setup(bot: Bot):
    plugin = DailyCharacterPlugin(bot)
    plugin.register()