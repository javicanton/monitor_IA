import argparse
import logging
import time

from config import Config
from topic_processor import process_topics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_once(days_window=None):
    result = process_topics(days_window=days_window)
    logger.info(f"Ejecucion topics: {result}")
    return result


def run_worker_loop(interval_min, days_window=None):
    logger.info(f"Worker topics activo cada {interval_min} min")
    while True:
        try:
            run_once(days_window=days_window)
        except Exception as e:
            logger.error(f"Error en worker topics: {e}")
        time.sleep(interval_min * 60)


def main():
    parser = argparse.ArgumentParser(description="Worker de topics")
    parser.add_argument("--once", action="store_true", help="Ejecutar una sola vez")
    parser.add_argument("--interval", type=int, default=Config.TOPIC_POLL_INTERVAL_MIN)
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Solo mensajes de los últimos N días (sobreescribe TOPICS_DAYS_WINDOW)",
    )
    args = parser.parse_args()

    if args.once:
        run_once(days_window=args.days)
    else:
        run_worker_loop(args.interval, days_window=args.days)


if __name__ == "__main__":
    main()
