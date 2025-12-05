"""AstrBot 每日一字插件
每天定时向指定QQ群推送一个随机汉字的详细信息。
使用 APScheduler 实现定时任务，支持管理员通过命令主动触发推送。
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.message.components import Plain


@register(
    "daily_chinese_character",
    "LINZ-L",
    "每日一字推送插件 - 每天13:00向指定QQ群推送随机汉字学习内容",
    "1.1.0"
)
class DailyWordPlugin(Star):
    """每日一字定时推送插件 - 使用 APScheduler"""
    # 修复问题1：仅保留context参数，从context中读取配置（移除多余的config参数）
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        self.config = context.config  # 从上下文获取配置
        
        # 从配置文件中读取目标群号
        self.target_group = self.config.get("target_group_id", "")
        self.push_time_hour = int(self.config.get("push_time_hour", 13))  # 确保为整数
        self.push_time_minute = int(self.config.get("push_time_minute", 0))  # 确保为整数
        
        # 从配置中读取管理员 QQ 号列表（兼容字符串/列表格式）
        self.admin_qq_list = self.config.get("admin_qq_list", [])
        if isinstance(self.admin_qq_list, str):
            self.admin_qq_list = [qq.strip() for qq in self.admin_qq_list.split(",") if qq.strip()]
        # 统一转为字符串格式，避免类型不匹配
        self.admin_qq_list = [str(qq) for qq in self.admin_qq_list]
        
        # 日志输出配置信息
        logger.info("[每日一字] 插件已加载")
        logger.info(f"[每日一字] 目标群号: {self.target_group}")
        logger.info(f"[每日一字] 推送时间: {self.push_time_hour:02d}:{self.push_time_minute:02d}")
        logger.info(f"[每日一字] 管理员列表: {self.admin_qq_list}")
        
        # 初始化 APScheduler（指定时区，避免时间偏移）
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        
        # 添加定时任务 - 使用 Cron 触发器
        self.scheduler.add_job(
            self.push_daily_word,
            trigger=CronTrigger(
                hour=self.push_time_hour,
                minute=self.push_time_minute,
                second=0
            ),
            id='daily_word_push',
            name='每日一字推送任务',
            replace_existing=True
        )
        
        # 启动调度器
        self.scheduler.start()
        logger.info(f"[每日一字] 定时任务已启动，将在每天 {self.push_time_hour:02d}:{self.push_time_minute:02d} 推送")
    
    def is_admin(self, event: AstrMessageEvent) -> bool:
        """检查用户是否是管理员"""
        # 获取发送者的 QQ 号（兼容不同消息格式）
        sender_qq = None
        
        # 优先从message_obj获取
        if hasattr(event, 'message_obj') and event.message_obj:
            if hasattr(event.message_obj, 'sender') and hasattr(event.message_obj.sender, 'user_id'):
                sender_qq = str(event.message_obj.sender.user_id)
            elif hasattr(event.message_obj, 'user_id'):
                sender_qq = str(event.message_obj.user_id)
        
        # 备用：从unified_msg_origin解析（私聊场景）
        if not sender_qq:
            parts = event.unified_msg_origin.split(":")
            if len(parts) >= 3 and parts[1] == "private":
                sender_qq = parts[2]
        
        if not sender_qq:
            logger.warning(f"[每日一字] 无法获取发送者 QQ 号: {event.unified_msg_origin}")
            return False
        
        is_admin = sender_qq in self.admin_qq_list
        logger.info(f"[每日一字] 权限检查: QQ {sender_qq} {'是' if is_admin else '不是'}管理员")
        return is_admin
    
    async def push_daily_word(self):
        """推送每日一字核心逻辑"""
        logger.info("[每日一字] 开始生成今日推送内容")
        
        # 校验目标群号配置
        if not self.target_group or not self.target_group.strip():
            logger.error("[每日一字] 未配置有效目标群号,推送失败")
            return
        
        try:
            # 构建平台标识（适配QQ群消息）
            umo = f"aiocqhttp:group:{self.target_group.strip()}"
            
            # 获取当前LLM提供商ID
            provider_id = await self.context.get_current_chat_provider_id(umo=umo)
            if provider_id is None:
                logger.error("[每日一字] 未找到可用的 LLM 提供商,请在 AstrBot 中配置 LLM 服务")
                await self.send_error_message()
                return
            
            logger.info(f"[每日一字] 使用 LLM 提供商: {provider_id}")
            
            # 构建精准提示词（确保输出格式符合要求）
            prompt = (
                "请严格按照以下要求生成内容，无需多余文字，不添加反问句：\n"
                "1. 选择一个非汉语常用100字的随机汉字；\n"
                "2. 按以下结构输出：\n"
                "今日汉字: [字]\n\n"
                "1. 读音: [拼音+声调]\n\n"
                "2. 含义: \n"
                "   本义：[本义解释]\n"
                "   引申义：[分点列出引申义]\n\n"
                "3. 繁体: [繁体写法，无则写“同简体”]\n\n"
                "4. 词源: [字源及字形演变说明]\n\n"
                "5. 造词: [至少3个包含该字的词语]\n\n"
                "6. 造句: [至少1个实用例句]\n"
                "3. 语言简洁易懂，采用学术书面表达，总字数不超过1000字。"
            )
            
            # 调用LLM生成内容
            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )
            
            # 处理LLM返回结果
            if llm_resp and llm_resp.completion_text:
                content = llm_resp.completion_text.strip()
                if not content:
                    logger.error("[每日一字] AI 返回内容为空字符串")
                    await self.send_error_message()
                    return
                
                # 构建最终推送消息
                final_message = f"📚 每日一字已推送 📚\n\n{content}"
                logger.info(f"[每日一字] AI 生成成功,内容长度: {len(content)} 字符")
                
                # 发送到目标群
                await self.send_to_group(final_message)
            else:
                logger.error("[每日一字] AI 返回结果为空")
                await self.send_error_message()
                
        except Exception as e:
            logger.error(f"[每日一字] 推送失败: {type(e).__name__}: {str(e)}")
            logger.exception(e)  # 输出完整异常栈
            await self.send_error_message()
    
    async def send_to_group(self, message: str):
        """发送消息到目标QQ群"""
        try:
            # 获取所有平台适配器
            platforms = self.context.get_all_platforms()
            sent = False
            
            # 遍历适配器，找到QQ平台
            for platform_name, platform_adapter in platforms.items():
                if platform_name == "aiocqhttp":
                    logger.info(f"[每日一字] 开始发送消息到群 {self.target_group}")
                    # 构建消息链
                    msg_chain = MessageChain([Plain(message)])
                    # 发送消息（使用group_前缀的UID格式）
                    result = await platform_adapter.send_by_uid(
                        f"group_{self.target_group.strip()}",
                        msg_chain
                    )
                    
                    if result and result.get("success", False):
                        logger.info(f"[每日一字] 消息已成功发送到群 {self.target_group}")
                        sent = True
                    else:
                        logger.error(f"[每日一字] 消息发送失败，平台返回: {result}")
                    break
            
            if not sent:
                logger.error("[每日一字] 未找到可用的 QQ 平台适配器,请检查QQ平台配置")
                
        except Exception as e:
            logger.error(f"[每日一字] 发送消息时出错: {type(e).__name__}: {str(e)}")
            logger.exception(e)
    
    async def send_error_message(self):
        """发送推送失败的错误提示"""
        error_msg = "❌ 每日一字推送失败 ❌\n\n系统遇到错误，无法生成今日内容。请联系管理员检查配置或日志。"
        await self.send_to_group(error_msg)

    async def terminate(self):
        """插件停用/卸载时的清理逻辑：关闭调度器以避免残留任务"""
        try:
            if hasattr(self, "scheduler") and self.scheduler:
                # 如果调度器在运行，尝试优雅关闭
                try:
                    self.scheduler.shutdown(wait=False)
                except TypeError:
                    # 有些 APScheduler 版本的 shutdown 不接受 wait 参数
                    self.scheduler.shutdown()
                logger.info("[每日一字] 调度器已关闭")
        except Exception as e:
            logger.error(f"[每日一字] 关闭调度器时出错: {e}")
            logger.exception(e)
    
    # 修复问题2：确保命令处理器正确接收event参数并处理
    @filter.command("HANZI")
    async def manual_push(self, event: AstrMessageEvent):
        """管理员手动触发推送（/HANZI 命令）"""
        logger.info(f"[每日一字] 收到手动推送命令，来源: {event.unified_msg_origin}")
        
        # 权限校验
        if not self.is_admin(event):
            logger.warning("[每日一字] 非管理员尝试使用 /HANZI 命令")
            await event.reply("❌ 权限不足：您不是本插件的管理员，无法使用此命令。")
            return
        
        # 校验目标群配置
        if not self.target_group or not self.target_group.strip():
            await event.reply("❌ 错误：插件未配置有效目标群号，无法推送。")
            return
        
        # 反馈执行状态
        await event.reply("✅ 正在生成每日一字内容，请稍候...")
        
        try:
            # 执行推送逻辑
            await self.push_daily_word()
            await event.reply("✅ 每日一字内容已成功推送至目标群！")
        except Exception as e:
            logger.error(f"[每日一字] 手动推送失败: {str(e)}")
            await event.reply(f"❌ 手动推送失败：{str(e)}")
