
import shutil
from pathlib import Path

from carlotta import logger


def ensure_dirs():
    """
    Ensure that the necessary directories exist.
    """
    if not shutil.which("ffmpeg"):
        logger.warning("FFmpeg is not installed or not in PATH. Streaming might fail.")

    for directory in ["cache", "downloads"]:
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
        except Exception as ex:
            logger.error(f"Failed to create directory {directory}: {ex}")
    logger.info("Cache directories updated.")
