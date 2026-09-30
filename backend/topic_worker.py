import argparse
import logging
import time

from config import Config
from topic_processor import assign_all_topics, process_topics, train_sample_topics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_once(days_window=None):
    result = process_topics(days_window=days_window)
    logger.info(f"Ejecucion topics: {result}")
    return result


def run_train_sample(sample_size=None, days_window=None, min_text_len=None, seed=None):
    result = train_sample_topics(
        sample_size=sample_size,
        days_window=days_window,
        min_text_len=min_text_len,
        seed=seed,
    )
    logger.info(f"Train-sample: {result}")
    return result


def run_assign_all(batch_size=None, days_window=None, reset_progress=False):
    result = assign_all_topics(
        batch_size=batch_size,
        days_window=days_window,
        reset_progress=reset_progress,
    )
    logger.info(f"Assign-all: {result}")
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
    parser.add_argument("--once", action="store_true", help="Ejecutar una sola vez (incremental)")
    parser.add_argument("--interval", type=int, default=Config.TOPIC_POLL_INTERVAL_MIN)
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Solo mensajes de los últimos N días (0 = sin límite; sobreescribe TOPICS_DAYS_WINDOW)",
    )
    parser.add_argument(
        "--train-sample",
        action="store_true",
        help="Entrenar modelo con submuestra SQL (no asigna el histórico completo)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Tamaño de la submuestra (default TOPICS_TRAIN_SAMPLE_SIZE)",
    )
    parser.add_argument(
        "--min-text-len",
        type=int,
        default=None,
        help="Longitud mínima de texto (default TOPICS_MIN_TEXT_LEN)",
    )
    parser.add_argument(
        "--seed",
        type=str,
        default=None,
        help="Semilla de muestreo (default TOPICS_SAMPLE_SEED)",
    )
    parser.add_argument(
        "--assign-all",
        action="store_true",
        help="Aplicar modelo existente a todo el histórico por lotes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Tamaño de lote para --assign-all (default TOPICS_ASSIGN_BATCH_SIZE)",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Con --assign-all, ignora checkpoint y empieza desde el principio",
    )
    args = parser.parse_args()

    if args.train_sample:
        run_train_sample(
            sample_size=args.sample_size,
            days_window=args.days,
            min_text_len=args.min_text_len,
            seed=args.seed,
        )
        return

    if args.assign_all:
        run_assign_all(
            batch_size=args.batch_size,
            days_window=args.days,
            reset_progress=args.reset_progress,
        )
        return

    if args.once:
        run_once(days_window=args.days)
    else:
        run_worker_loop(args.interval, days_window=args.days)


if __name__ == "__main__":
    main()
