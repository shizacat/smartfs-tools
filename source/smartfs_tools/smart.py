import logging

from .base import LSSize


def make_dump(
    size: int,
    ls_size: LSSize = LSSize.b512,
) -> bytes:
    """
    Создает пустай дамп с отформатированной файловой системой
    заданного размера.

    Так как сама файловая система используется на носителях
    небольшого размера, весь дамп создается в памяти.

    Args
        size: int - Размер в байтах, образа файловой системы
        ls_size: LSSize - Logical sector size in bytes
    """
    # Definitions
    ls_total = size // ls_size.value

    # Checks
    # The total number of sectors on the device / partition
    # fits in a 16-bit word.
    if ls_total > 0xFFFF:
        raise ValueError(
            f"The total number of sectors on the device / partition "
            f"({ls_total}) does not fit in a 16-bit word."
        )
