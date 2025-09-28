## [Unreleased]

### Added
- Add more tests for script.py
- Add to script.py the mode_check_with_help function


## [0.4.0] - 2024-10-14

### Added

- Add, option '--smart-number-root-dir', the count of root directory.


## [0.3.1] - 2024-09-07

### Fixed
- Fix, crete mode ModeBits from str of int, and move it in class


## [0.3.0] - 2024-09-06

### Added
- Future: add support permissions bit in classes
- Add: mkdir, cmd_file_create_write add argument 'mode'
- Future: add config permissoin mode for script

### Fixed
- Fix: walk_dir_find_all_dir alogrithm update
- Fix: _create_entry, _find_entry - walk through sectors


## [0.2.0] - 2024-08-29
### Fixed
- Fix: _finddirentry didn't update dir_offset to the next entry


## [0.1.0] - 2024-08-27
### Added
- Create dump from directory (smartfs_mkdump)
