#!/usr/bin/env python3

import argparse
import binascii
import dataclasses
import io
import os
import subprocess
from pathlib import Path
import platform
import struct
import typing

print_enabled = False

def my_print(*args, **kwargs):
    if print_enabled:
        print(*args, **kwargs)
    pass


@dataclasses.dataclass(frozen=True)
class WinePathDirCache:
    path: Path
    names: typing.Dict[str, str]

    def lookup(self, name: str) -> Path:
        try:
            return self.path / self.names[name.lower()]
        except KeyError as e:
            raise FileNotFoundError from e

    @classmethod
    def create(self, windir: str) -> typing.Self:
        unixdir = subprocess.check_output(["winepath", "-u", windir], text=True, stderr=subprocess.DEVNULL).strip()
        unixdir_contents = os.listdir(unixdir)
        return WinePathDirCache(
            path=Path(unixdir),
            names={uf.lower(): uf for uf in unixdir_contents},
        )


class WinePathCacher:
    def __init__(self):
        self.cache: dict[str, WinePathDirCache] = {}

    def resolve(self, win_path: str) -> Path:
        win_path = win_path.replace("\\", "/")
        if not (win_path[0] == "/" or win_path[1:2] == ":"):
            win_path = os.path.join(os.getcwd(), win_path)
        win_path_dir, win_path_file = win_path.rsplit("/", 1)
        lower_win_path_dir = win_path_dir = win_path_dir.lower()
        win_path_dir_cache = self.cache.get(lower_win_path_dir)
        if not win_path_dir_cache:
            win_path_dir_cache = WinePathDirCache.create(win_path_dir)
            self.cache[lower_win_path_dir] = win_path_dir_cache
        result = win_path_dir_cache.lookup(win_path_file)
        assert result.resolve() == result
        return result


def read_cstr(f):
    result = io.BytesIO()
    while True:
        b = f.read(1)
        if b == b'\x00':
            return result.getvalue().decode()
        if not b:
            raise ValueError(f"Unexpected end (got '{result.getvalue()}'")
        result.write(b)

def read_word(f):
    b = f.read(2)
    w, = struct.unpack_from("<H", b)
    return w

def read_addr(f, mode):
    r = 0
    for i in range(mode):
        b = f.read(1)
        r |= ord(b) << (8 * i)
    return r

def read_dword(f):
    b = f.read(4)
    w, = struct.unpack_from("<I", b)
    return w

def read_opcode(f):
    b = f.read(1)
    if not b:
        return None
    return ord(b)

source_stack = []

def do_identifier(f, identifiers, opcode, addr_mode1, addr_mode2):
    global source_stack
    identifier_code = read_addr(f, addr_mode1)
    if identifier_code in (0x01, 0x02, 0x21, 0x22, 0x40, 0x60):
        # New identifier
        name_code = read_addr(f, addr_mode2)
        extra_str = f"{identifier_code:04X} {name_code:04X}"
        identifier_name = read_cstr(f)
        type_name = {
            0x01: "NAMESPACE",
            0x02: "GLOBAL_ARRAY",
            0x21: "LOCAL",
            0x22: "FUNCTION_GLOBAL",
            0x40: "GLOBAL",
            0x60: "TYPEDEF",
        }
        my_print(f"{opcode:02X} {type_name[identifier_code]} '{identifier_name}' ({extra_str})")
        if name_code in identifiers:
            assert identifiers[name_code] == identifier_name
        identifiers[name_code] = identifier_name
    elif identifier_code in identifiers:
        # Ref
        my_print(f"{opcode:02X} IDENTIFIER_REF ({identifier_code:04X})")
    else:
        raise ValueError(f"pos={hex(f.tell())} {identifier_code:04X}")

def parse_sbr(f):
    identifiers = {}
    magic = f.read(5)
    if magic == b'\x00\x02\x00\x02\x00':
        # MSVC 12.0 C (Visual Studio 6)
        pass
    elif magic == b'\x00\x02\x00\x07\x00':
        # MSVC 12.0 C++ (Visual Studio 6)
        pass
    else:
        raise ValueError(f"Not a sbr file (magic={binascii.b2a_hex(magic)})")
    my_print(f"WD '{read_cstr(f)}'")
    files = []
    while True:
        opcode = read_opcode(f)
        if opcode is None:
            my_print("DONE")
            return files
        addr_mode = 2
        if opcode & 0x40:
            addr_mode = 3
            my_print(f"{opcode:02X} EXTEND ", end="")
            opcode &= ~0x40
        if opcode == 1:
            source = read_cstr(f)
            my_print(f"{opcode:02X} ENTER '{source}'")
            source_stack.append(source)
            files.append(source)
        elif opcode == 2:
            w = read_word(f)
            my_print(f"{opcode:02X} LINE {w}")
        elif opcode == 3:
            statement_opcode = read_opcode(f)
            if statement_opcode == 1:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} FUNCDECL '{name}' ({code1:04X} {code2:04X})")
                if code2 in identifiers:
                    assert identifiers[code2] == name
                identifiers[code2] = name
            elif statement_opcode == 3:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                if code2 in identifiers:
                    assert identifiers[code2] == name
                identifiers[code2] = name
            elif statement_opcode == 4:
                do_identifier(f, identifiers=identifiers, opcode=statement_opcode, addr_mode1=2, addr_mode2=addr_mode)
            elif statement_opcode == 5:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} MACRO '{name}' ({code1:04X} {code2:04X})")
                assert code2 not in identifiers
                identifiers[code2] = name
            elif statement_opcode == 6:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} MACRO_FUNC '{name}' ({code1:04X} {code2:04X})")
                assert code2 not in identifiers
                identifiers[code2] = name
            elif statement_opcode == 7:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} TYPEDEF '{name}' ({code1:04X} {code2:04X})")
                if code2 in identifiers:
                    assert identifiers[code2] == name
                identifiers[code2] = name
            elif statement_opcode == 8:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} STRUCT '{name}' ({code1:04X} {code2:04X})")
                assert name not in identifiers
                identifiers[code2] = name
            elif statement_opcode == 9:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} ENUM '{name}' ({code1:04X} {code2:04X})")
                if code2 in identifiers:
                    assert identifiers[code2] == name
                identifiers[code2] = name
            elif statement_opcode == 10:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} ENUM_MEMBER '{name}' ({code1:04X} {code2:04X})")
                if code2 in identifiers:
                    assert identifiers[code2] == name
                identifiers[code2] = name
            elif statement_opcode == 11:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} UNION '{name}' ({code1:04X} {code2:04X})")
                if code2 in identifiers:
                    assert identifiers[code2] == name
                identifiers[code2] = name
            elif statement_opcode == 15:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} CLASS '{name}' ({code1:04X} {code2:04X})")
                if code2 in identifiers:
                    assert identifiers[code2] == name
                identifiers[code2] = name
            elif statement_opcode == 16:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{statement_opcode:02X} CLASS_METHOD '{name}' ({code1:04X} {code2:04X})")
                if code2 in identifiers:
                    assert identifiers[code2] == name
                identifiers[code2] = name
            elif statement_opcode == 17:
                code1 = read_word(f)
                code2 = read_addr(f, mode=addr_mode)
                name = read_cstr(f)
                my_print(f"{opcode:02X} {statement_opcode:02X} STRUCTURED_MEMBER '{name}' ({code1:04X} {code2:04X})")
                if code2 in identifiers:
                    assert identifiers[code2] == name
                identifiers[code2] = name
            else:
                raise ValueError(f"{statement_opcode:02X}")
        elif opcode == 4:
            do_identifier(f, identifiers=identifiers, opcode=opcode, addr_mode1=addr_mode, addr_mode2=addr_mode)
        elif opcode == 7:
            my_print(f"{opcode:02X} OP7")
        elif opcode == 8:
            my_print(f"{opcode:02X} ENTER_SCOPE")
        elif opcode == 9:
            my_print(f"{opcode:02X} LEAVE_SCOPE")
        elif opcode == 10:
            my_print(f"{opcode:02X} LEAVE")
            source_stack.pop()
        elif opcode == 11:
            word1 = read_addr(f, mode=addr_mode)
            my_print(f"{opcode:02X} BODY ({word1:04X})")
        elif opcode == 12:
            descr = f"{opcode:02X} PARENT_CLASS"
            while True:
                parent_type = read_addr(f, mode=addr_mode)
                assert parent_type in identifiers
                parent_op = read_word(f)
                descr = f"{descr} ({parent_type:04X} {parent_op:04X})"
                if parent_op in (0x0C02, 0x0C03, 0x0C04, 0x0C05, 0x4C04):
                    if parent_op & 0x4000:
                        addr_mode = 3
                    else:
                        addr_mode = 2
                    continue
                if parent_op in (0x0904, 0x0902, ):
                    break
                if parent_op in (0x0203, 0x0204, 0x0205):
                    w = read_word(f)
                    descr = f"{descr} {w:04X}"
                    break
                raise ValueError(f"Unknown PARENT_CLASS op: {parent_op:04X}")
            my_print(descr)
        elif opcode == 13:
            word1 = read_addr(f, mode=addr_mode)
            my_print(f"{opcode:02X} UNKNOWN ({word1:04X})")
        else:
            my_print(f"{opcode:02X} UNKNOWN(pos={hex(f.tell())})")
            raise ValueError



def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("sbr", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    global print_enabled
    if args.verbose:
        print_enabled = True

    with args.sbr.open("rb") as f:
        try:
            files = parse_sbr(f)
        except:
            my_print(f"pos={hex(f.tell())}")
            my_print(f"source_stack={source_stack}")
            raise

    if args.source:
        os.chdir(args.source.parent)

    wine_path_cacher = WinePathCacher()
    for f in files[1:]:
        if platform.system() != "Windows":
            f = wine_path_cacher.resolve(f)
        print(f"Note: including file: {Path(f).resolve()}")


if __name__ == "__main__":
    raise SystemExit(main())
