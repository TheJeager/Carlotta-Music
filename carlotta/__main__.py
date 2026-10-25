import asyncio
import os
import signal
import importlib
from contextlib import suppress

from aiohttp import web

from carlotta import anon, app, config, db, logger, stop, thumb, userbot, yt
from carlotta.plugins import all_modules


async def health(request):
    return web.Response(text="OK", status=200)


async def idle():
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()


async def main():
    health_app = web.Application()
    health_app.router.add_get("/", health)
    health_app.router.add_get("/health", health)
    health_runner = web.AppRunner(health_app)

    try:
        await health_runner.setup()
        port = int(os.getenv("PORT", "8000"))
        await web.TCPSite(health_runner, "0.0.0.0", port).start()
        logger.info("Health server listening on port %s.", port)

        await db.connect()
        await app.boot()
        await userbot.boot()
        await anon.boot()
        await thumb.start()

        for module in all_modules:
            importlib.import_module(f"carlotta.plugins.{module}")
        logger.info(f"Loaded {len(all_modules)} modules.")

        if config.COOKIES_URL:
            await yt.save_cookies(config.COOKIES_URL)

        sudoers = await db.get_sudoers()
        app.sudoers.update(sudoers)
        app.bl_users.update(await db.get_blacklisted())
        logger.info(f"Loaded {len(app.sudoers)} sudo users.")

        await idle()
    finally:
        try:
            await stop()
        finally:
            await health_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
