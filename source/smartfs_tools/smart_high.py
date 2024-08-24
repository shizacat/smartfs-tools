"""
"""
import datetime
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

    def cmd_mkdir(self, path: str):
        """
        Create a directory
        name: smartfs_mkdir

        Args
            path - полный путь к директории включая имя директории
        """
        if not path.startswith("/"):
            raise ValueError("Path must be absolute")
        if path == "/":
            raise ValueError("Can't create root directory")

        sub_dir, new_dir = path.rsplit("/", maxsplit=1)
        if sub_dir == "":
            sub_dir = "/"

        entry = self._finddirentry(sub_dir)
        self._createentry(entry_parent=entry, name=new_dir)

    def dump(self) -> bytes:
        """Возвращает содержимое виртуального диска"""
        return self._mtd_block_layer.dump()

    @staticmethod
    def read_dump(dump: bytes) -> "SmartHigh":
        """Создает объект из содержимого виртуального диска"""
        raise NotImplementedError()

    def _finddirentry(self, path_abs: str) -> base.SmartFSEntry:
        """
        Finds an entry in the filesystem as specified by absolute path.

        TODO: Мои мыслки по объекту Entry
        dir_sector - сектор в котором находиться описание директории
        dir_offset - смещеение к объекту EntryHeader этой директории в секторе
        """
        if not path_abs.startswith("/"):
            raise ValueError("Path must be absolute")

        # Start from first root
        sector = self._mtd_block_layer._log_sector_get(
            base.SCTN_ROOT_DIR_SECTOR)
        sector_process = base.SCTN_ROOT_DIR_SECTOR

        entry = base.SmartFSEntry(
            first_sector=sector._header.logical_sector_number,
            dir_sector=sector._header.logical_sector_number,
            dir_offset=0,
            name="/"
        )

        if path_abs == "/":
            return entry

        for dir in path_abs.strip("/").split("/"):
            is_found: bool = False

            # find sub dir in entry dir
            # __ Check all dir_entry in sector
            sector = self._mtd_block_layer._log_sector_get(entry.dir_sector)
            offset = base.ChainHeader.get_size()  # After chain header
            size_header = base.SmartFSEntryHeader.get_size(
                self._mtd_block_layer._smartfs_config.max_len_filename)
            dir_offset = 0
            while True:
                if sector.borders_is_big(offset=offset, size=size_header):
                    # Закончились данные в этом секторе, пробуем следующий
                    next_sector = sector.get_next_sector_number()
                    if next_sector == -1:
                        raise ValueError(f"Directory not found: {dir}")
                    sector = self._mtd_block_layer._log_sector_get(next_sector)
                    offset = base.ChainHeader.get_size()
                    dir_offset = 0
                    sector_process = next_sector

                # __ Read dir_entry
                eh = sector.read_object(
                    class_name=base.SmartFSEntryHeader,
                    offset=offset,
                    size=size_header,
                )
                # check entry exists
                if eh.first_sector == -1:
                    break

                if eh.name == dir:
                    entry = base.SmartFSEntry(
                        first_sector=eh.first_sector,
                        dir_sector=sector_process,
                        dir_offset=dir_offset,
                        name=eh.name
                    )
                    break
                dir_offset += 1

            if is_found is False:
                raise ValueError(f"Directory not found: {dir}")

        if entry is None:
            raise ValueError("Wrong something")
        return entry

    def _createentry(
        self, entry_parent: base.SmartFSEntry, name: str
    ) -> base.SmartFSEntry:
        """
        Creates a new entry in the specified parent directory
        name: smartfs_createentry
        """
        if len(name) > self._mtd_block_layer._smartfs_config.max_len_filename:
            raise ValueError("Filename too long")
        # Find empty Entry
        sector = self._mtd_block_layer._log_sector_get(
            entry_parent.first_sector)
        offset = base.ChainHeader.get_size()  # After chain header
        size_header = base.SmartFSEntryHeader.get_size(
            self._mtd_block_layer._smartfs_config.max_len_filename)

        while True:
            if sector.borders_is_big(offset=offset, size=size_header):
                # To next sector, if need create it
                next_sector = sector.get_next_sector_number()
                if next_sector is None:
                    # Create
                    sector_new = self._mtd_block_layer._allocsector()
                    sector_new_obj = self._mtd_block_layer._log_sector_get(
                        sector_new)
                    sector_new_obj.set_bytes(
                        pfrom=0,
                        value=base.ChainHeader(
                            sector_type=base.SectorType.directory,
                            next_sector=-1,
                            used=-1,
                        ).get_pack()
                    )
                    # Add it to chain header
                    ch: base.ChainHeader = sector.read_object(
                        offset=0, size=base.ChainHeader.get_size())
                    ch.next_sector = sector_new
                    sector.set_bytes(pfrom=0, value=ch.get_pack())
                    next_sector = sector_new

                # Process next sector
                sector = self._mtd_block_layer._log_sector_get(next_sector)
                offset = 0

            entry = sector.read_object(
                class_name=base.SmartFSEntryHeader,
                offset=offset,
                size=size_header,
            )
            if entry.first_sector == -1:
                # Empty entry found
                break
            offset += size_header

        # Create new sectro for new entry
        sector_new_number = self._mtd_block_layer._allocsector()
        # __ add chain header
        sector_new_obj = self._mtd_block_layer._log_sector_get(
            sector_new_number)
        sector_new_obj.set_bytes(
            pfrom=0,
            value=base.ChainHeader(
                sector_type=base.SectorType.directory,
                next_sector=0xffff,
                used=0xffff,
            ).get_pack()
        )

        # Fill entry
        entry.name = name
        entry.first_sector = sector_new_number
        entry.utc = datetime.datetime.now(datetime.UTC)

        # Write entry on sector
        sector.set_bytes(
            pfrom=offset,
            value=entry.get_pack(
                max_name_len=self._mtd_block_layer._smartfs_config.max_len_filename
            )
        )

        return entry
