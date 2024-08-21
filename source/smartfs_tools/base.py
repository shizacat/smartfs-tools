import struct
from enum import Enum
from dataclasses import dataclass
from typing import Optional

import crc


Signature = b"SMRT"


class SectorSize(int, Enum):
    """
    The valid values for the logical sector size

    The selected size is represented using 3 bits in the logical sector
    status byte and stored on each sector.

    #define SMART_SECTSIZE_256        0x00
    #define SMART_SECTSIZE_512        0x04
    #define SMART_SECTSIZE_1024       0x08
    #define SMART_SECTSIZE_2048       0x0c
    #define SMART_SECTSIZE_4096       0x10
    #define SMART_SECTSIZE_8192       0x14
    #define SMART_SECTSIZE_16384      0x18
    """
    b256 = 0b000
    b512 = 0b001
    b1024 = 0b010
    b2048 = 0b011
    b4096 = 0b100
    b8192 = 0b101
    b16384 = 0b110
    b32768 = 0b111

    @staticmethod
    def cnv_to_size(value: "SectorSize") -> int:
        """
        Convert SectorSize to size in bytes
        """
        return 2 ** (value.value + 8)


class Version(int, Enum):
    """
    The valid values for the version
    """
    v1 = 0b01
    v2 = 0b10
    v3 = 0b11


class CRCValue(Enum):
    """
    The valid values for the CRC value
    """
    crc_disable = "none"
    crc8 = "crc8"
    crc16 = "crc16"


class Commited(Enum):
    """
    The valid values for the commited flag
    """
    not_committed = 1
    committed = 0


class Released(Enum):
    """
    The valid values for the released flag
    """
    not_released = 1
    released = 0


@dataclass
class SectorStatus:
    """
    Sector status bit mask
    type C: uint8_t
        * Bit 7:   1 = Not committed
        *          0 = committed
        * Bit 6:   1 = Not released
        *          0 = released
        * Bit 5:   Sector CRC enable
        * Bit 4-2: Sector size on volume
        * Bit 1-0: Format version (0x1)
    """
    committed: Commited = 0
    released: Released = 0
    crc_enable: int = 0
    sector_size: SectorSize = SectorSize.b512
    format_version: Version = Version.v1

    def get_pack(self) -> bytes:
        """
        Returns the packed byte representation of the sector status
        """
        return struct.pack(
            "B",
            (self.committed.value << 7) |
            (self.released.value << 6) |
            (self.crc_enable << 5) |
            (self.sector_size.value << 2) |
            (self.format_version.value << 0)
        )

    def __repr__(self):
        return (
            f"SectorStatus("
            f"committed={self.committed}, "
            f"released={self.released}, "
            f"crc_enable={self.crc_enable}, "
            f"sector_size={self.sector_size}, "
            f"format_version={self.format_version}"
            f")"
        )

    @staticmethod
    def create_from_int(value: int) -> "SectorStatus":
        """
        Create a new instance of the sector status from the byte value
        """
        return SectorStatus(
            committed=Commited((value >> 7) & 0x1),
            released=Released((value >> 6) & 0x1),
            crc_enable=(value >> 5) & 0x1,
            sector_size=SectorSize((value >> 2) & 0x7),
            format_version=Version((value >> 0) & 0x3),
        )


class SectorHeader:
    """
    Base class for sector header
    """

    def __init__(
        self,
        sh_size: int,
    ):
        """
        Args:
            sh_size: int - The size of the sector header in bytes
        """
        self._sh_size = sh_size
        self.status: SectorStatus
        self.crc_value: int = 0
        self.crc: CRCValue = CRCValue.crc_disable

    @classmethod
    def create(
        cls, version: Version, *args, **kwargs
    ) -> "SectorHeader":
        """
        Create a new instance of the sector header
        """
        if version == Version.v1:
            return SectorHeaderV1(*args, **kwargs)
        raise ValueError("Invalid version")

    @property
    def size(self) -> int:
        """
        Return the size of the sector header, bytes
        """
        return self._sh_size

    def get_pack(self) -> bytes:
        raise NotImplementedError()


class SectorHeaderV1(SectorHeader):
    """
    Sector header, size 5 bytes, for SmartFS Version 1
    Support only crc8

    uint8_t               logicalsector[2]; /* The logical sector number */
    uint8_t               seq;              /* Incrementing sequence number */
    uint8_t               crc8;             /* CRC-8 or seq number MSB */
    uint8_t               status;           /* Status of this sector:
    """

    def __init__(
        self,
        logical_sector_number: int,
        sequence_number: int,
        status: SectorStatus,
        crc_value: int = 0,
        crc: CRCValue = CRCValue.crc_disable
    ):
        super().__init__(sh_size=5)
        self.logical_sector_number = logical_sector_number
        self.sequence_number = sequence_number
        self.status = status
        self.crc_value = crc_value
        self.crc = crc

    def get_pack(self) -> bytes:
        """
        Return the packed byte representation of the sector header
        """
        if self.crc == CRCValue.crc_disable:
            return struct.pack(
                "<HBB",
                self.logical_sector_number,
                self.sequence_number & 0x00FF,
                self.sequence_number >> 8,
            ) + self.status.get_pack()

        if self.crc == CRCValue.crc8:
            return struct.pack(
                "<HBB",
                self.logical_sector_number,
                self.sequence_number & 0x00FF,
                self.crc_value,
            ) + self.status.get_pack()

        raise ValueError("CRC value is not supported")


class Sector:
    """
    Сектор
    """

    def __init__(
        self,
        storage: bytearray,
        header: Optional[SectorHeader] = None,
        is_new: bool = False,
        fill_value: bytes = b'\xFF',
    ):
        """
        Args:
            is_new - будет заполнено новыми структурами
                иначе будет вычитывать и парсить
        """
        self._storage = storage
        self._fill_value = fill_value

        if is_new:
            if header is None:
                raise ValueError("Header is required")
            self._header = header
            self._fill()
            self._header.crc_value = self._calc_crc()
            self._save_header()
        else:
            # TODO: read storage and parse header
            raise NotImplementedError()

    # def save(self):
    #     """
    #     Save the sector to the storage
    #     """
    #     # TODO: calculation crc

    def set_bytes(self, pfrom: int, value: bytes):
        """
        Записывает в нужное место данные.
        Сразу рассчитывается crc если это нужно

        Args:
            pfrom - позиция считается после заголовка
        """
        start_position = self._header.size + pfrom
        end_position = self._header.size + pfrom + len(value)
        if end_position > len(self._storage):
            raise ValueError(
                f"The end position ({end_position}) is greater than the "
                f"length of the buffer ({len(self._storage)})"
            )
        self._storage[start_position:end_position] = value

        self._header.crc_value = self._calc_crc()
        self._save_header()

    def _fill(self):
        """
        Заполняет пустое место в секторе
        """
        self._storage[self._header.size:] = self._fill_value * (
            len(self._storage) - self._header.size
        )

    def _save_header(self):
        self._storage[0:self._header.size] = self._header.get_pack()

    def _calc_crc(self) -> int:
        """
        Return CRC value
        TODO: lenght 8, 16, 32
        """
        calc = None

        if self._header.crc == CRCValue.crc_disable:
            return
        if self._header.crc == CRCValue.crc8:
            calc = crc.Calculator(crc.Crc8.CCITT)

        if calc is None:
            raise ValueError("CRC value is not supported")

        # Calculation
        buffer: bytes = b''
        # __ Calculate CRC on data region of the sector
        buffer += self._storage[self._header.size:]
        # __ Add logical sector number and seq to the CRC calculation, 3 byte
        buffer += self._header.get_pack()[:3]
        # __ Add status to the CRC calculation, 1 byte
        buffer += self._header.status.get_pack()
        return calc.checksum(buffer)

    def get_size(self) -> int:
        """
        Возвращает размер доступного места в секторе
        """
        return len(self._storage) - self._header.size
