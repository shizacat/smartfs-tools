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


class Version(int, Enum):
    """
    The valid values for the version
    """
    v1 = 0b01
    v2 = 0b10
    v3 = 0b11


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
class SectorHeader:
    """
    Sector header, size 5 bytes

    uint8_t               logicalsector[2]; /* The logical sector number */
    uint8_t               seq;              /* Incrementing sequence number */
    uint8_t               crc8;             /* CRC-8 or seq number MSB */
    uint8_t               status;           /* Status of this sector:
    """
    logical_sector_number: int
    sequence_number: int
    status: SectorStatus
    crc8: Optional[int] = None
    crc_enable: bool = False

    def get_pack(self) -> bytes:
        """
        Return the packed byte representation of the sector header
        """
        return struct.pack(
            "<HBB",
            self.logical_sector_number,
            self.sequence_number & 0x00FF,
            self.crc8 if self.crc_enable else self.sequence_number >> 8,
        ) + self.status.get_pack()
