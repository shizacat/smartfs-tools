import logging
from typing import Optional

from .base import (
    SectorSize,
    Version,
    SectorHeader,
    SectorStatus,
    Signature,
    CRCValue,
    Sector,
    Commited,
    Released,
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

    Первые 3 сектора зарезервированы.
    """

    def __init__(
        self,
        device_size: Optional[int] = None,
        sector_size: SectorSize = SectorSize.b512,
        version: Version = Version.v1,
        crc: CRCValue = CRCValue.crc_disable,
        fill_value: bytes = b'\xFF',
        max_len_filename: int = 16,
        number_root_dir: int = 10,
    ):
        """
        Args:
            device_size: int - в байтах, если задан размер устройсва ограничен
                его значением
            number_root_dir - Record the number of root directory entries
                we have, if 1 - without multi directory
        """
        self._sector_size = sector_size
        self._sector_size_byte = SectorSize.cnv_to_size(self._sector_size)
        self._version = version
        self._crc = crc
        self._fill_value = fill_value
        self._max_len_filenaem = max_len_filename
        self._number_root_dir = number_root_dir

        # Device config
        self._device_size = device_size
        # __ Stored all data
        self._storage: bytearray = bytearray()

        # Runtime
        # __ Сколько секторов уже выделено
        self._phy_sectors_total: Optional[int] = None
        # __ Максимальное количество секторов
        self._phy_sector_max_number: Optional[int] = None
        if self._device_size is not None:
            self._phy_sector_max_number = self._device_size // self._sector_size_byte  # noqa: E501

        self._ll_format()

    def _ll_format(self):
        """
        Low level format
        """
        # Construct a logical sector zero header
        sector = self._phy_sector_get(
            phy_sector_number=0,
            logical_sector_number=0,
            sequence_number=0,
        )

        # __ Add the format signature to the sector
        sector.set_bytes(pfrom=0, value=Signature)
        # __ Add version
        sector.set_bytes(
            pfrom=len(Signature),
            value=self._version.value.to_bytes(length=1, byteorder="big")
        )
        # __ Add max length of file
        sector.set_bytes(
            pfrom=len(Signature) + 1,
            value=self._max_len_filenaem.to_bytes(length=1, byteorder="big"),
        )
        # __ Add root directory entries
        sector.set_bytes(
            pfrom=len(Signature) + 2,
            value=self._number_root_dir.to_bytes(length=1, byteorder="big"),
        )

    def _phy_sector_get(
        self,
        phy_sector_number: int,
        logical_sector_number: int = 0,
        sequence_number: int = 0,
    ) -> Sector:
        """
        Автоматически выделяет сектор из хранилища и возвращает
        указатель на его часть
        Не проверяет существование сектора, предпологается, что
        сектора не существует
        """
        # checks
        if (
            self._device_size is not None and
            phy_sector_number > self._phy_sector_max_number
        ):
            raise ValueError(
                f"The sector number ({phy_sector_number}) is greater than "
                f"the number of sectors on the device / partition "
                f"({self._phy_sector_max_number})"
            )

        # Get border
        b_start = phy_sector_number * self._sector_size_byte
        b_end = b_start + self._sector_size_byte
        # Expand storage if necessary
        if b_end > len(self._storage):
            self._storage.extend(
                bytearray(b_end - len(self._storage))
            )

        # TODO: может создавать в __init__
        view = memoryview(self._storage)
        return Sector(
            is_new=True,
            fill_value=self._fill_value,
            storage=view[b_start:b_end],
            header=SectorHeader.create(
                version=self._version,
                logical_sector_number=logical_sector_number,
                sequence_number=sequence_number,
                crc=self._crc,
                status=SectorStatus(
                    committed=Commited.committed,
                    released=Released.not_released,
                    crc_enable=0 if self._crc == CRCValue.crc_disable else 1,
                    sector_size=self._sector_size,
                    format_version=self._version,
                )
            )
        )

    def _write_fs_to_media(self):
        """
        Write the filesystem to media.
        Loop for each root dir entry and allocate the reserved Root Dir Entry,
        then write a blank root dir for it.
        """
        for i in range(self._number_root_dir):
            pass

    @property
    def dump(self) -> bytes:
        """Возвращает содержимое виртуального диска"""
        return bytes(self._storage)
