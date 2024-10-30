"""
"""
import datetime
import os
from typing import Generator

from smartfs_tools import base

from .smart import MTDBlockLayer


class SmartHigh:
    """
    The class (high level) is responsible for working with a virtual device

    TODO: may be renamed to SmartVDevice, maybe this is FS Layer
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
            erase_block_size - in bytes, erase block size
            storage - the array of bytes for data, may be empty or with data
            formated - flag, if True, then the storage will be formatted
                else smart_config will be ignored
        """
        self._mtd_block_layer = MTDBlockLayer(
            smartfs_config=smartfs_config,
            formated=formated,
            storage=storage,
            erase_block_size=erase_block_size,
        )

    def cmd_ls(self, base_dir: str = "/") -> list:
        """
        Return:
            list of files and directories in selected directory
        """
        raise NotImplementedError()

    def cmd_file_create_write(
        self,
        path: str,
        body: bytes,
        mode: base.ModeBits = base.ModeBits(
            other=base.PBits(r=1, w=1, x=0),
            group=base.PBits(r=1, w=1, x=0),
            owner=base.PBits(r=1, w=1, x=0),
        ),
    ):
        """Created a new file with the specified name and content
        If the file exists, it will be overwritten
        name: smartfs_open; smartfs_write

        Args:
            path - full path to the file, include name of file
            mode - File mode bits (rwx)
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
            mode=mode,
        )

        # fill content
        # TODO: Fix size of sector header need to get from object
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
                # TODO: set sector type in CH

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
        """Reads the contents of the file

        Args:
            path - full path to the file, include name of file
        """
        raise NotImplementedError()

    def cmd_mkdir(
        self,
        path: str,
        mode: base.ModeBits = base.ModeBits(
            other=base.PBits(r=1, w=1, x=1),
            group=base.PBits(r=1, w=1, x=1),
            owner=base.PBits(r=1, w=1, x=1),
        ),
    ):
        """
        Create a directory
        name: smartfs_mkdir

        Args
            path - full path to the directory, include name of directory
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
            entry_type=base.SmartFSDirEntryType.dir,
            mode=mode)

    def dump(self) -> bytes:
        """
        Return:
            content of the virtual disk
        """
        return self._mtd_block_layer.dump

    @staticmethod
    def read_dump(dump: bytes) -> "SmartHigh":
        """Create object from the contents of the virtual disk"""
        raise NotImplementedError()

    def _finddirentry(self, path_abs: str) -> base.SmartFSEntry:
        """
        Finds an entry in the filesystem as specified by absolute path.

        TODO: My thinks about the object Entry
        dir_sector - the sector in which the description of directory is located
        dir_offset - offset to the object EntryHeader this directory
            inside the sector
        """
        if not path_abs.startswith("/"):
            raise ValueError("Path must be absolute")

        # Get root entry
        entry = self._create_smart_entry_root()

        if path_abs == "/":
            return entry

        for dir in path_abs.strip("/").split("/"):
            is_found: bool = False

            # find sub dir in entry dir
            for sector in self._walk_sectors_in_entry(entry):
                # const
                size_entry_header = base.SmartFSEntryHeader.get_size(
                    self._mtd_block_layer._smartfs_config.max_len_filename)
                ch_offset = base.ChainHeader.get_size()  # After chain header
                # ---
                dir_offset = 0

                # Read all entry header in sector
                while True:
                    eh = sector.read_object(
                        class_name=base.SmartFSEntryHeader,
                        offset=ch_offset + dir_offset,
                        size=size_entry_header,
                    )
                    # check entry exists
                    if eh.first_sector.to_bytes(2, "little") == b"\xff\xff":
                        break

                    # compare name
                    if eh.name == dir:
                        entry = base.SmartFSEntry(
                            first_sector=eh.first_sector,
                            dir_sector=sector._header.logical_sector_number,
                            dir_offset=dir_offset,
                            name=eh.name
                        )
                        is_found = True
                        break
                    dir_offset += size_entry_header

            if is_found is False:
                raise ValueError(f"Directory not found: {dir}")

        if entry is None:
            raise ValueError("Wrong something")
        return entry

    def _walk_sectors_in_entry(
        self, entry: base.SmartFSEntry
    ) -> Generator[base.Sector, None, None]:
        """
        Returns a generator that yields all sectors in the entry
        """
        sector_log_num = entry.first_sector
        while True:
            sector = self._mtd_block_layer._log_sector_get(sector_log_num)
            yield sector
            # Find next sector
            sector_log_num = sector.get_next_sector_number()
            if sector_log_num is None:
                break

    def _split_abs_dir(self, path_abs: str) -> Generator[str, None, None]:
        """Split absolute path to subdir, root will be inserted

        Example:
          path_abs = "/dir1/dir2/dir3"
          return ["/", "dir1", "dir2", "dir3"]
        """
        for item in path_abs.rstrip("/").split("/"):
            yield "/" if item == "" else item

    def _create_smart_entry_root(self) -> base.SmartFSEntry:
        sector = self._mtd_block_layer._log_sector_get(
            base.SCTN_ROOT_DIR_SECTOR)
        return base.SmartFSEntry(
            first_sector=sector._header.logical_sector_number,
            dir_sector=sector._header.logical_sector_number,
            dir_offset=0,
            name="/"
        )

    def _createentry(
        self,
        entry_parent: base.SmartFSEntry,
        name: str,
        entry_type: base.SmartFSDirEntryType,
        mode: base.ModeBits,
    ) -> base.SmartFSEntryHeader:
        """
        Creates a new entry in the specified parent directory
        name: smartfs_createentry

        Args:
            mode - File mode bits (rwx)
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
                            next_sector=65535,  # 0xffff
                            used=65535,  # 0xffff
                        ).get_pack()
                    )
                    # Add it to chain header
                    ch: base.ChainHeader = sector.read_object(
                        class_name=base.ChainHeader,
                        offset=0,
                        size=base.ChainHeader.get_size())
                    ch.next_sector = sector_new
                    sector.set_bytes(pfrom=0, value=ch.get_pack())
                    next_sector = sector_new

                # Process next sector
                sector = self._mtd_block_layer._log_sector_get(next_sector)
                offset = base.ChainHeader.get_size()

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
        entry.utc = datetime.datetime.now(tz=datetime.timezone.utc)
        entry.flags.empty = 0  # not empty
        entry.flags.type = entry_type
        entry.flags.mode = mode

        # Write entry on sector
        sector.set_bytes(
            pfrom=offset,
            value=entry.get_pack(
                max_name_len=self._mtd_block_layer._smartfs_config.max_len_filename  # noqa: E501
            )
        )

        return entry
