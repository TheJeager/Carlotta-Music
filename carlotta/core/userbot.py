from pyrogram import Client

from carlotta import config, logger


class Userbot(Client):
    def __init__(self):
        """
        Initializes the userbot with multiple clients.

        This method sets up clients for the userbot using predefined session strings.
        Each client is assigned a unique name based on the key in the `clients` dictionary.
        """
        self.clients = []
        clients = {"one": "SESSION1", "two": "SESSION2", "three": "SESSION3"}
        for key, string_key in clients.items():
            name = f"RadhaUB{key[-1]}"
            session = getattr(config, string_key)
            setattr(
                self,
                key,
                Client(
                    name=name,
                    api_id=config.API_ID,
                    api_hash=config.API_HASH,
                    session_string=session,
                    no_updates=True,
                ),
            )

    async def boot_client(self, num: int, ub: Client):
        """
        Boot a client and perform initial setup.
        Args:
            num (int): The client number to boot (1, 2, or 3).
            ub (Client): The userbot client instance.
        Raises:
            SystemExit: If the client fails to send a message in the log group.
        """
        clients = {
            1: self.one,
            2: self.two,
            3: self.three,
        }
        client = clients[num]
        await client.start()
        self.clients.append(client)
        try:
            await client.send_message(config.LOGGER_ID, "Assistant Started")
            client.id = ub.me.id
            client.name = ub.me.first_name
            client.username = ub.me.username
            client.mention = ub.me.mention
            try:
                await ub.join_chat("AnimeSprt")
            except Exception as ex:
                logger.debug("Assistant %s could not join optional chat: %s", num, ex)
            logger.info("Assistant %s started as @%s", num, client.username)
        except Exception as ex:
            self.clients.remove(client)
            try:
                if client.is_connected:
                    await client.stop()
            except Exception:
                logger.exception("Failed to stop assistant %s after startup error", num)
            raise SystemExit(
                f"Assistant {num} failed during startup: {type(ex).__name__}"
            ) from ex

    async def boot(self):
        """
        Asynchronously starts the assistants.
        """
        if config.SESSION1:
            await self.boot_client(1, self.one)
        if config.SESSION2:
            await self.boot_client(2, self.two)
        if config.SESSION3:
            await self.boot_client(3, self.three)

    async def exit(self):
        """
        Asynchronously stops the assistants.
        """
        for client in reversed(self.clients.copy()):
            try:
                if client.is_connected:
                    await client.stop()
            except Exception:
                logger.exception("Failed to stop assistant client")
            finally:
                self.clients.remove(client)
        logger.info("Assistants stopped.")
