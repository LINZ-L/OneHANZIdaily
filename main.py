#AstrBot 每日一字插件
#每天13:00定时向指定QQ群推送一个随机汉字的详细信息
#使用 APScheduler 实现定时任务
#支持管理员通过命令主动推送


from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from astrbot.api import (
    register,
    Star,
    Context,
    AstrBotConfig,
    logger,
    AstrMessageEvent,
)
from astrbot.api.event import filter
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.message.components import Plain


@register(
    "daily_chinese_character",
    "LINZ-L",
    "每日一字推送插件 - 每天13:00向指定QQ群推送随机汉字学习内容",
    "1.1.0",
    "https://github.com/LINZ-L/OneHANZIdaily/tree/master"
)
class DailyWordPlugin(Star):
    """每日一字定时推送插件 - 使用 APScheduler"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.config = config
        
        # 从配置文件中读取目标群号
        self.target_group = config.get("target_group_id", "")
        self.push_time_hour = config.get("push_time_hour", 13)
        self.push_time_minute = config.get("push_time_minute", 0)
        
        # 从配置中读取管理员 QQ 号列表
        self.admin_qq_list = config.get("admin_qq_list", [])
        if isinstance(self.admin_qq_list, str):
            # 如果是字符串格式，尝试按逗号分割
            self.admin_qq_list = [qq.strip() for qq in self.admin_qq_list.split(",") if qq.strip()]
        
        logger.info(f"[每日一字] 插件已加载")
        logger.info(f"[每日一字] 目标群号: {self.target_group}")
        logger.info(f"[每日一字] 推送时间: {self.push_time_hour:02d}:{self.push_time_minute:02d}")
        logger.info(f"[每日一字] 管理员列表: {self.admin_qq_list}")
        
        # 初始化 APScheduler
        self.scheduler = AsyncIOScheduler()
        
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
        # 从 unified_msg_origin 中提取用户 ID
        # 格式: platform_name:message_type:session_id
        # 例如: aiocqhttp:private:123456789 或 aiocqhttp:group:987654321
        
        # 获取发送者的 QQ 号
        sender_qq = None
        
        # 尝试从 message_obj 获取
        if hasattr(event, 'message_obj') and event.message_obj:
            if hasattr(event.message_obj, 'sender'):
                sender_qq = str(event.message_obj.sender.user_id)
            elif hasattr(event.message_obj, 'user_id'):
                sender_qq = str(event.message_obj.user_id)
        
        # 如果没有获取到，尝试从 unified_msg_origin 解析
        if not sender_qq:
            parts = event.unified_msg_origin.split(":")
            if len(parts) >= 3:
                # 如果是群消息，session_id 是群号，需要从 message_obj 获取发送者
                if parts[1] == "private":
                    sender_qq = parts[2]
        
        if not sender_qq:
            logger.warning(f"[每日一字] 无法获取发送者 QQ 号: {event.unified_msg_origin}")
            return False
        
        is_admin = sender_qq in self.admin_qq_list
        logger.info(f"[每日一字] 权限检查: QQ {sender_qq} {'是' if is_admin else '不是'}管理员")
        return is_admin
    
    async def push_daily_word(self):
        """推送每日一字"""
        logger.info("[每日一字] 开始生成今日推送内容")
        
        if not self.target_group:
            logger.error("[每日一字] 未配置目标群号,推送失败")
            return
        
        try:
            # 构建 unified_msg_origin (平台标识)
            # 格式: platform_name:message_type:session_id
            # 对于 QQ 群消息: aiocqhttp:group:群号
            umo = f"aiocqhttp:group:{self.target_group}"
            
            # 获取当前会话使用的聊天模型 ID
            provider_id = await self.context.get_current_chat_provider_id(umo=umo)
            
            if provider_id is None:
                logger.error("[每日一字] 未找到可用的 LLM 提供商,请在 AstrBot 中配置 LLM 服务")
                await self.send_error_message()
                return
            
            logger.info(f"[每日一字] 使用 LLM 提供商: {provider_id}")
            
            # 构建提示词
            prompt = (
                "请选择一个随机的汉字(不能是常见的100个汉字),然后提供以下信息:\n\n"
                "1. 这个字的读音(包括拼音和声调)\n"
                "2. 字的含义和解释：包括本义和衍生义\n"
                "3. 繁体写法(如果有)\n"
                "4. 词源和字形演变\n"
                "5. 包含这个字的常用词语与专业或特殊词语\n"
                "请以清晰、有条理的格式输出,尽量采用学术书面表达，无需多余内容，输出文本不超过1000字。去掉末尾ai风格的反问提问者的问句"
            )
            
            logger.info(f"[每日一字] 正在调用 LLM 生成内容...")
            
            # 使用官方推荐的 llm_generate 方法调用大模型
            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )
            
            # 提取 AI 生成的内容
            if llm_resp and llm_resp.completion_text:
                content = llm_resp.completion_text.strip()
                
                # 构建最终消息
                final_message = f"📚 每日一字已推送 📚\n\n{content}"
                
                logger.info(f"[每日一字] AI 生成成功,内容长度: {len(content)} 字符")
                
                # 发送消息到目标群
                await self.send_to_group(final_message)
                
            else:
                logger.error("[每日一字] AI 返回内容为空")
                await self.send_error_message()
                
        except Exception as e:
            logger.error(f"[每日一字] 推送失败: {type(e).__name__}: {str(e)}")
            logger.exception(e)
            await self.send_error_message()
    
    async def send_to_group(self, message: str):
        """发送消息到目标群"""
        try:
            # 获取所有平台适配器
            platforms = self.context.get_all_platforms()
            
            sent = False
            for platform_name, platform_adapter in platforms.items():
                # 只处理 QQ 平台 (aiocqhttp)
                if platform_name == "aiocqhttp":
                    logger.info(f"[每日一字] 找到 QQ 平台适配器: {platform_name}")
                    
                    # 构建消息链
                    msg_chain = MessageChain([Plain(message)])
                    
                    # 发送到群
                    # 使用 group_群号 格式作为 uid
                    result = await platform_adapter.send_by_uid(
                        f"group_{self.target_group}",
                        msg_chain
                    )
                    
                    if result:
                        logger.info(f"[每日一字] 消息已成功发送到群 {self.target_group}")
                        sent = True
                    else:
                        logger.error(f"[每日一字] 消息发送失败")
                    
                    break
            
            if not sent:
                logger.error("[每日一字] 未找到可用的 QQ 平台适配器,请确保已正确配置 QQ 平台")
                
        except Exception as e:
            logger.error(f"[每日一字] 发送消息时出错: {type(e).__name__}: {str(e)}")
            logger.exception(e)
    
    async def send_error_message(self):
        """发送错误消息"""
        error_msg = "❌ 每日一字推送失败 ❌\n\n系统遇到错误，无法生成今日内容。请检查日志或联系管理员。"
        await self.send_to_group(error_msg)
    
    @filter.command("HANZI")
    async def manual_push(self, event: AstrMessageEvent):
        """管理员手动触发推送（/HANZI 命令）"""
        logger.info(f"[每日一字] 收到 HANZI 命令，来自: {event.unified_msg_origin}")
        
        # 权限检查
        if not self.is_admin(event):
            logger.warning(f"[每日一字] 非管理员尝试使用 HANZI 命令")
            await event.reply("❌ 权限不足：您不是本插件的管理员，无法使用此命令。")
            return
        
        # 检查是否配置了目标群
        if not self.target_group:
            await event.reply("❌ 错误：未配置目标群号，无法推送。请联系管理员配置。")
            return
        
        # 开始推送
        await event.reply("✅ 正在生成并推送每日一字内容...")
        logger.info(f"[每日一字] 管理员触发手动推送")
        
        try:
            await self.push_daily_word()
            await event.reply(f"✅ 推送完成！内容已发送到群 {self.target_group}")
        except Exception as e:
            logger.error(f"[每日一字] 手动推送失败: {e}")
            await event.reply(f"❌ 推送失败：{str(e)}")
    
    @filter.command("每日一字测试")
    async def test_push(self, event: AstrMessageEvent):
        """手动测试推送功能（需要管理员权限）"""
        logger.info(f"[每日一字] 收到测试命令，来自: {event.unified_msg_origin}")
        
        # 权限检查
        if not self.is_admin(event):
            logger.warning(f"[每日一字] 非管理员尝试使用测试命令")
            await event.reply("❌ 权限不足：您不是本插件的管理员，无法使用此命令。")
            return
        
        await event.reply("正在测试每日一字推送...")
        await self.push_daily_word()
        await event.reply("测试推送已完成,请查看目标群组是否收到消息。")
    
    @filter.command("每日一字状态")
    async def check_status(self, event: AstrMessageEvent):
        """查看定时任务状态"""
        jobs = self.scheduler.get_jobs()
        if jobs:
            job = jobs[0]
            next_run = job.next_run_time
            admin_list = ", ".join(self.admin_qq_list) if self.admin_qq_list else "未配置"
            status_msg = (
                f"📋 每日一字插件状态\n\n"
                f"✅ 调度器状态: 运行中\n"
                f"⏰ 下次推送时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🎯 目标群号: {self.target_group}\n"
                f"🕐 配置时间: 每天 {self.push_time_hour:02d}:{self.push_time_minute:02d}\n"
                f"👤 管理员列表: {admin_list}\n\n"
                f"💡 提示：管理员可使用 /HANZI 命令立即推送"
            )
        else:
            status_msg = "⚠️ 定时任务未运行"
        
        await event.reply(status_msg)
    
    def __del__(self):
        """插件卸载时关闭调度器"""
        try:
            if hasattr(self, 'scheduler') and self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("[每日一字] 调度器已关闭")
        except Exception as e:
            logger.error(f"[每日一字] 关闭调度器时出错: {e}")