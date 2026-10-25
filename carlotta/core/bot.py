import pyrogram

from carlotta import config, logger


class Bot(pyrogram.Client):
    def __init__(self):
        super().__init__(
            name="Radha",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            parse_mode=pyrogram.enums.ParseMode.HTML,
            max_concurrent_transmissions=7,
            link_preview_options=pyrogram.types.LinkPreviewOptions(is_disabled=True),
        )
        self.owner = config.OWNER_ID
        self.logger = config.LOGGER_ID
        self.bl_users = pyrogram.filters.user()
        self.sudoers = pyrogram.filters.user(self.owner)

    async def boot(self):
        """
        Starts the bot and performs initial setup.

        Raises:
            SystemExit: If the bot fails to access the log group or is not an administrator in the logger group.
        """
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        self.mention = self.me.mention

        try:
            await self.send_message(self.logger, "Bot Started")
            member = await self.get_chat_member(self.logger, self.id)
            if member.status != pyrogram.enums.ChatMemberStatus.ADMINISTRATOR:
                raise SystemExit("Please promote the bot as an admin in logger group.")
        except Exception as ex:
            if self.is_connected:
                await self.stop()
            raise SystemExit(
                f"Bot has failed during startup: {type(ex).__name__}"
            ) from ex
        except BaseException:
            if self.is_connected:
                await self.stop()
            raise
        logger.info("Bot started as @%s", self.username)

    async def exit(self):
        """
        Asynchronously stops the bot.
        """
        if self.is_connected:
            await super().stop()
            logger.info("Bot stopped.")
