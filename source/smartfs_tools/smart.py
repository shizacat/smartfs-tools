import logging

from .base import (
    SectorSize,
    Version,
    SectorHeader,
    SectorStatus,
    Signature,
    CRCValue
)


# def make_dump(
#     size: int,
#     ls_size: LSSize = LSSize.b512,
# ) -> bytes:
#     """
#     Создает пустай дамп с отформатированной файловой системой
#     заданного размера.

#     Так как сама файловая система используется на носителях
#     небольшого размера, весь дамп создается в памяти.

#     Args
#         size: int - Размер в байтах, образа файловой системы
#         ls_size: LSSize - Logical sector size in bytes
#     """
#     # Definitions
#     ls_total = size // ls_size.value

#     # Checks
#     # The total number of sectors on the device / partition
#     # fits in a 16-bit word.
#     if ls_total > 0xFFFF:
#         raise ValueError(
#             f"The total number of sectors on the device / partition "
#             f"({ls_total}) does not fit in a 16-bit word."
#         )


class SmartVDevice:
    """
    Класс для работы с виртуальным устройством с файловой
    системой SmartFS.
    """

    def __init__(
        self,
        sector_size: SectorSize = SectorSize.b512,
        version: Version = Version.v1,
        crc: CRCValue = CRCValue.crc_disable,
        fill_value: int = 0xFF,
        max_len_filename: int = 16,
        number_root_dir: int = 10,
    ):
        """
        Args:
            number_root_dir - Record the number of root directory entries
                we have
        """
        self._sector_size = sector_size
        self._version = version
        self._crc = crc
        self._fill_value = fill_value
        self._max_len_filenaem = max_len_filename
        self._number_root_dir = number_root_dir

        # Stored all data
        self._storage: bytearray = bytearray()

        # runtime
        # __ Сколько секторов уже выделено
        self._rt_sector_total = 0

        self._ll_format()

    def _ll_format(self):
        """
        Low level format
        """
        # Construct a logical sector zero header
        sh = SectorHeader(
            logical_sector_number=0,
            sequence_number=0,
            crc=self._crc_enable,
            status=SectorStatus(
                committed=1,
                released=0,
                crc_enable=self._crc_enable,
                sector_size=self._sector_size,
                format_version=self._version,
            )
        )
        sector = self._create_sector(sh)

        # __ Add the format signature to the sector
        self._ba_set_bytes(
            sector, Signature, SectorHeader.get_len())
        self._ba_set_bytes(
            buffer=sector,
            value=self._version.value.to_bytes(length=1, byteorder="big"),
            start_position=SectorHeader.get_len() + len(Signature)
        )
        self._ba_set_bytes(
            buffer=sector,
            value=self._max_len_filenaem.to_bytes(length=1, byteorder="big"),
            start_position=SectorHeader.get_len() + len(Signature) + 1
        )
        self._ba_set_bytes(
            buffer=sector,
            value=self._number_root_dir.to_bytes(length=1, byteorder="big"),
            start_position=SectorHeader.get_len() + len(Signature) + 2
        )

    def _create_sector(self, sh: SectorHeader) -> bytearray:
        """
        Создает сектор с заданным заголовком
        """
        # Создаем сектор
        sector = bytearray(SectorSize.cnv_to_size(self._sector_size))
        self._ba_set_bytes(sector, sh.get_pack(), 0)
        return sector

    def _ba_set_bytes(
        self, buffer: bytearray, value: bytes, start_position: int
    ):
        end_position = start_position + len(value)
        if end_position > len(buffer):
            raise ValueError(
                f"The end position ({end_position}) is greater than the "
                f"length of the buffer ({len(buffer)})"
            )
        buffer[start_position:end_position] = value
