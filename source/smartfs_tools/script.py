#!/usr/bin/env python3

import argparse
from collections import deque
from pathlib import Path
from typing import List, Optional, TypedDict

from smartfs_tools import SmartHigh, base


class Args(TypedDict):
    base_dir: str
    out: Path
    storage_size: int
    smart_erase_block_size: int
    smart_sector_size: int
    smart_version: int
    smart_crc: int
    smart_max_len_filename: int
    smart_number_root_dir: int
    dir_mode: str
    file_mode: str


def arguments(args_list: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create dump smartFS partition from directory"
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        required=True,
        help="The directory, from which will be created dump",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="The file name to save dump",
    )
    parser.add_argument(
        "--storage-size",
        type=int,
        required=True,
        help="Size of partition in bytes",
    )

    parser_smart = parser.add_argument_group("smart")
    parser_smart.add_argument(
        "--smart-erase-block-size",
        type=int,
        default=4096,
        help="Size of erase block on flash in bytes",
    )
    parser_smart.add_argument(
        "--smart-sector-size",
        type=int,
        help="Size of sector smartFS in bytes",
        default=1024,
        choices=base.SectorSize.to_list(),
    )
    parser_smart.add_argument(
        "--smart-version",
        type=int,
        default=1,
        choices=list(base.Version),
        help="Version of smartFS",
    )
    parser_smart.add_argument(
        "--smart-crc",
        type=str,
        default="none",
        help="CRC of smartFS",
        choices=base.CRCValue.to_list(),
    )
    parser_smart.add_argument(
        "--smart-max-len-filename",
        type=int,
        default=16,
        help="Max length of filename in smartFS",
    )
    parser_smart.add_argument(
        "--smart-number-root-dir",
        type=int,
        default=0,
        help="The count of root directory"
    )

    parser_permissions = parser.add_argument_group("permissions")
    parser_permissions.add_argument(
        "--dir-mode",
        type=str,
        help="Mode of directory, default '%(default)s'",
        default="777"
    )
    parser_permissions.add_argument(
        "--file-mode",
        type=str,
        help="Mode of file, default '%(default)s'",
        default="666"
    )
    return parser.parse_args(args_list)


def walk_dir_find_files(path: Path):
    for p in path.glob("**/*"):
        if p.is_file():
            yield p


def walk_dir_find_all_dir(path: Path) -> List[str]:
    """
    Find uniqued directories

    Return
        List of directories relative to path,
        order from root to leaf
    """
    result = []
    visited = set()

    # Add root dir
    queue = deque([path])
    while queue:
        cdir = queue.popleft()
        if cdir in visited:
            continue
        # new dir
        result.append(str(cdir.relative_to(path)))
        subdirs = [p for p in cdir.iterdir() if p.is_dir()]
        queue.extend(subdirs)

    # Remove root dir
    return result[1:]


def check_mode(mode: str, help: str):
    """
    Raises:
        ValueError: if mode is not 3 symbols or not integer
    """
    if len(mode) != 3:
        raise ValueError(f"{help} mode must be 3 symbols")
    try:
        int(mode)
    except ValueError:
        raise ValueError("Mode must be integer")


def main(args_list: Optional[List[str]] = None):
    args: Args = arguments(args_list)

    dir_mode = base.ModeBits.create_from_str(args.dir_mode)
    file_mode = base.ModeBits.create_from_str(args.file_mode)

    smartfs = SmartHigh(
        storage=bytearray(args.storage_size),
        formated=True,
        erase_block_size=args.smart_erase_block_size,
        smartfs_config=base.SmartFSConfig(
            sector_size=base.SectorSize.create_from_int(
                args.smart_sector_size),
            version=base.Version(args.smart_version),
            crc=base.CRCValue(args.smart_crc),
            max_len_filename=args.smart_max_len_filename,
            number_root_dir=args.smart_number_root_dir,
        )
    )

    if not args.base_dir.exists():
        raise ValueError("Base dir not exists")

    for item in walk_dir_find_all_dir(args.base_dir):
        smartfs.cmd_mkdir(path="/" + item, mode=dir_mode)

    for item in walk_dir_find_files(args.base_dir):
        with item.open("rb") as f:
            smartfs.cmd_file_create_write(
                path="/" + str(item.relative_to(args.base_dir)),
                body=f.read(),
                mode=file_mode,
            )

    with args.out.open("wb") as f:
        f.write(smartfs._mtd_block_layer._storage)


if __name__ == "__main__":
    main()
