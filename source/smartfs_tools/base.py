import struct
from enum import Enum
from dataclasses import dataclass
from typing import Optional


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
    committed: int = 0
    released: int = 0
    crc_enable: int = 0
    sector_size: SectorSize = SectorSize.b512
    format_version: Version = Version.v1

    def get_pack(self) -> bytes:
        """
        Returns the packed byte representation of the sector status
        """
        return struct.pack(
            "B",
            (self.committed << 7) |
            (self.released << 6) |
            (self.crc_enable << 5) |
            (self.sector_size.value << 2) |
            (self.format_version.value << 0)
        )


@dataclass
class SectorHeaderV1:
    """
    Sector header, size 5 bytes, for SmartFS Version 1
    Support only crc8

    uint8_t               logicalsector[2]; /* The logical sector number */
    uint8_t               seq;              /* Incrementing sequence number */
    uint8_t               crc8;             /* CRC-8 or seq number MSB */
    uint8_t               status;           /* Status of this sector:
    """
    logical_sector_number: int
    sequence_number: int
    status: SectorStatus
    crc_value: Optional[int] = None
    crc: CRCValue = CRCValue.crc_disable

    def get_pack(self) -> bytes:
        """
        Return the packed byte representation of the sector header
        """
        if self.crc_value == CRCValue.crc_disable:
            return struct.pack(
                "<HBB",
                self.logical_sector_number,
                self.sequence_number & 0x00FF,
                self.sequence_number >> 8,
            ) + self.status.get_pack()

        if self.crc_value == CRCValue.crc8:
            return struct.pack(
                "<HBB",
                self.logical_sector_number,
                self.sequence_number & 0x00FF,
                self.crc_value,
            ) + self.status.get_pack()

        raise ValueError("CRC value is not supported")

    @staticmethod
    def get_len() -> int:
        """
        Return the length of the sector header
        """
        return 5


Signature = b"SMRT"
