"""
"""

from typing import Optional

from smartfs_tools import base
from .smart import MTDBlockLayer


class SmartHigh:
    """
    Высокоуровневый класс для работы с виртуальным устроством
    TODO: может переименовать в SmartVDevice, а может это FS Layer
    """

    def __init__(
        self,
        erase_block_size: int,
        storage: bytearray,
        formated: bool = False,
        smartfs_config: base.SmartFSConfig = base.SmartFSConfig(),
    ):
        """
        Args:
            erase_block_size - в байтах, размер erase block
            storage - байтовый массив для данных, может быть как пустой
                так и с данными
            formated - форматировать раздел,
                если нет, то smart_config будет проигнорирован
        """
        self._mtd_block_layer = MTDBlockLayer(
            smartfs_config=smartfs_config,
            formated=formated,
            storage=storage,
            erase_block_size=erase_block_size,
        )

    def cmd_ls(self, base_dir: str = "/") -> list:
        """Возвращает список файлов и папок в указанной директории"""
        raise NotImplementedError()

    def cmd_file_write(self, path: str, body: bytes):
        """Создает файл с указанным именем и содержимым
        Если файл существует перезаписывает

        Args:
            path - полный путь к файлу включая имя файла
        """
        raise NotImplementedError()

    def cmd_file_read(self, path: str) -> bytes:
        """Читает содержимое файла

        Args:
            path - полный путь к файлу включая имя файла
        """
        raise NotImplementedError()

    def cmd_dir_create(self, path: str):
        """
        Создает директорию

        Args
            path - полный путь к директории включая имя директории
        """
        raise NotImplementedError()

    def dump(self) -> bytes:
        """Возвращает содержимое виртуального диска"""
        return self._mtd_block_layer.dump()

    @staticmethod
    def read_dump(dump: bytes) -> "SmartHigh":
        """Создает объект из содержимого виртуального диска"""
        raise NotImplementedError()
