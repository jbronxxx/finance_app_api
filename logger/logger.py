"""Модуль настройки и инициализации логирования."""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Получить или сконфигурировать логгер с единым форматом вывода.

    Аргументы:
        name (str): Имя логгера (как правило, __name__ вызывающего модуля).

    Возвращает:
        logging.Logger: Настроенный экземпляр логгера со стандартным выводом в stdout.
    """
    logger = logging.getLogger(name)

    # Если у логгера уже есть обработчики, не добавляем их повторно
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
