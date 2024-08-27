"""
"""
import datetime
import os

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

    def cmd_file_create_write(self, path: str, body: bytes):
        """Создает новый файл с указанным именем и содержимым
        Если файл существует перезаписывает
        name: smartfs_open; smartfs_write

        Args:
            path - полный путь к файлу включая имя файла
        """
        if not path.startswith("/"):
            raise ValueError("Path must be absolute")
        dirname, filename = os.path.split(path)

        # find dir_entry
        dir_entry = self._finddirentry(dirname)

        # create file entry
        entry_h_file = self._createentry(
            name=filename,
            entry_parent=dir_entry,
            entry_type=base.SmartFSDirEntryType.file,
        )

        # fill content
        # TODO: Fix размер заголовка сектора нужно получать из объекта
        empty_size_in_sector = (
            self._mtd_block_layer._sector_size_byte -
            5 -  # base.SectorHeader.size -
            base.ChainHeader.get_size()
        )
        is_first = True
        for i in range(0, len(body), empty_size_in_sector):
            if is_first:
                sector = self._mtd_block_layer._log_sector_get(
                    entry_h_file.first_sector)
                is_first = False
            else:
                # Add new sector in chain
                # __ allocate new sector
                sector_number = self._mtd_block_layer._allocsector()
                # __ fill old chain header
                chain_h = sector.read_object(
                    class_name=base.ChainHeader,
                    offset=0,
                    size=base.ChainHeader.get_size(),
                )
                chain_h.next_sector = sector_number
                sector.set_bytes(pfrom=0, value=chain_h.get_pack())

                # Set sector
                sector = self._mtd_block_layer._log_sector_get(sector_number)
                # TODO: задать тип сектора в CH

            # Write data
            data = body[i:i + empty_size_in_sector]
            sector.set_bytes(pfrom=base.ChainHeader.get_size(), value=data)
            # __ set chain
            chain_h = base.ChainHeader(
                sector_type=base.SectorType.file,
                next_sector=0xffff,
                used=len(data),
            )
            sector.set_bytes(pfrom=0, value=chain_h.get_pack())

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
        self._createentry(
            entry_parent=entry,
            name=new_dir,
            entry_type=base.SmartFSDirEntryType.dir)

    def dump(self) -> bytes:
        """Возвращает содержимое виртуального диска"""
        return self._mtd_block_layer.dump

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
                    is_found = True
                    break
                dir_offset += 1

            if is_found is False:
                raise ValueError(f"Directory not found: {dir}")

        if entry is None:
            raise ValueError("Wrong something")
        return entry

    def _createentry(
        self,
        entry_parent: base.SmartFSEntry,
        name: str,
        entry_type: base.SmartFSDirEntryType,
    ) -> base.SmartFSEntryHeader:
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

        # Create new sector for new entry
        sector_new_number = self._mtd_block_layer._allocsector()
        # __ add chain header
        sector_new_obj = self._mtd_block_layer._log_sector_get(
            sector_new_number)
        if entry_type == base.SmartFSDirEntryType.dir:
            sector_type = base.SectorType.directory
        else:
            sector_type = base.SectorType.file
        sector_new_obj.set_bytes(
            pfrom=0,
            value=base.ChainHeader(
                sector_type=sector_type, next_sector=0xffff, used=0xffff,
            ).get_pack()
        )

        # Fill entry
        entry.name = name
        entry.first_sector = sector_new_number
        entry.utc = datetime.datetime.now(datetime.UTC)
        entry.flags.empty = 0  # not empty
        entry.flags.type = entry_type

        # Write entry on sector
        sector.set_bytes(
            pfrom=offset,
            value=entry.get_pack(
                max_name_len=self._mtd_block_layer._smartfs_config.max_len_filename  # noqa: E501
            )
        )

        return entry
