import aiohttp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

@register("OneHANZIdaily", "YourName", "一个简单的插件,定时检索一个汉字并解释推送至对应群聊", "1.0.0")
class OneHANZIdailyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 配置核心参数（需替换为自己的信息）
        self.target_qq = 24257251944  # 推送目标QQ号/群号（群号需加前缀，如'group_123456'）
        #self.llm_api_url = "https://api.xxx.com/chat/completions"  # 大模型API地址
        #self.llm_api_key = "your_api_key_here"  # 大模型API密钥
        self.scheduler_job = None

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        # 启动定时任务：每天0:00执行推送任务
        scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self.scheduler_job = scheduler.add_job(
            self.send_daily_character, 
            CronTrigger(hour=24, minute=0, second=0)
        )
        scheduler.start()
        logger.info("每日一字插件已加载，定时任务已启动")

    # 注册指令的装饰器。指令名为 oneHANZIdaily
    @filter.command("oneHANZIdaily")
    async def oneHANZIdaily(self, event: AstrMessageEvent):
        """手动触发每日一字推送"""
        await self.send_daily_character()
        yield event.plain_result("每日一字已推送！")


    # 调用大模型API解读汉字
    async def get_character_explanation(self):
        umo = event.unified_msg_origin
        provider_id = await self.context.get_current_chat_provider_id(umo=umo)
        llm_resp = await self.context.llm_generate(
        chat_provider_id = provider_id, # 聊天模型 ID
        prompt=""选取随机的一个汉字(不能是汉语常用100字)，
        请详细解读这个字，按照繁体字，核心含义（本义，引申义，分编号列出），
        词源，相关词汇，实用造句的顺序给出解析。要求语言简洁易懂，格式清晰，尽量采用学术书面表达，无需多余内容。
        输出文本不超过1000字。去掉末尾ai风格的反问提问者的问句。"",
        )
        # print(llm_resp.completion_text) # 获取返回的文本
    
        # 构造大模型Prompt（明确要求返回格式）
        #prompt = """选取随机的一个汉字(不能是汉语常用100字)，
        #请详细解读这个字，按照繁体字，核心含义（本义，引申义，分编号列出)，
        #词源，相关词汇，实用造句的顺序给出解析。要求语言简洁易懂，格式清晰，尽量采用学术书面表达，无需多余内容。
        #输出文本不超过1000字；去掉末尾ai风格的反问提问者的问句。"""

        # 调用大模型API（以OpenAI格式为例，其他平台需调整参数）
        #headers = {
        #    "Content-Type": "application/json",
        #    "Authorization": f"Bearer {self.llm_api_key}"
        #}
        #data = {
           # "model": "gpt-3.5-turbo",  # 替换为你的模型名（如spark-3.5、ernie-4.0等）
            #"messages": [{"role": "user", "content": prompt}],
            #"temperature": 0.7
       # }

       # try:
          #  async with aiohttp.ClientSession() as session:
          #      timeout = aiohttp.ClientTimeout(total=10)
           #     async with session.post(
             #       self.llm_api_url,
             #       headers=headers,
             #       json=data,
              #      timeout=timeout
              #  ) as response:
              #      response.raise_for_status()
              #      result = await response.json()
               #     # 提取大模型回复（不同平台返回字段不同，需适配）
               #     content = result["choices"][0]["message"]["content"]
               #     explanation = content.strip()
               #     return explanation
        #except Exception as e:
        #    logger.error(f"调用大模型失败：{str(e)}")
        #    return f"解读获取失败，错误原因：{str(e)}"

    # 拼接消息并推送
    async def send_daily_character(self):
        try:
            # 拼接最终消息
            msg_content = f"【每日一字】\n\n{llm_resp.completion_text}"
            # 调用astrbot的发送消息接口
            await self.context.send_message(
                target_id=str(self.target_qq),
                message_str=msg_content
            )
            logger.info("每日一字推送成功")
        except Exception as e:
            logger.error(f"推送每日一字失败：{str(e)}")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        if self.scheduler_job:
            self.scheduler_job.remove()

