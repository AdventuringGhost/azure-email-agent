"""Entry point: load config, initialise clients, run poll loop."""
import logging
import sys
import time

from agent.config import load_config
from agent.email_processor import EmailProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting email agent — loading config and Key Vault secrets…")
    config = load_config()
    processor = EmailProcessor(config)
    logger.info(
        "Agent ready. Polling every %d s (deployment: %s).",
        config.poll_interval_seconds,
        config.foundry_deployment,
    )

    try:
        while True:
            try:
                count = processor.process_unread()
                if count:
                    logger.info("Poll complete — processed %d email(s).", count)
                else:
                    logger.debug("Poll complete — inbox quiet.")
            except Exception:
                logger.exception("Unhandled error in poll cycle; will retry next interval.")
            time.sleep(config.poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received — shutting down cleanly.")


if __name__ == "__main__":
    main()
