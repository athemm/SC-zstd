#!/usr/bin/env python3
# forked from https://github.com/123456abcdef/cr-sc-dump
import argparse
import hashlib
import io
import zstandard
import os

from PIL import Image

if not os.path.isdir("In-SC"): os.mkdir("In-SC")
if not os.path.isdir("Out-SC"): os.mkdir("Out-SC")

class Reader(io.BytesIO):
    def __init__(self, stream):
        super().__init__(stream)
        self._bytes_left = len(stream)

    def __len__(self):
        return 0 if self._bytes_left < 0 else self._bytes_left

    def read(self, size):
        self._bytes_left -= size
        return super().read(size)

    def read_byte(self):
        return int.from_bytes(self.read(1), "little")

    def read_uint16(self):
        return int.from_bytes(self.read(2), "little")

    def read_uint32(self):
        return int.from_bytes(self.read(4), "little")

    def read_string(self):
        length = self.read_byte()
        return self.read(length).decode("utf-8")


def decompress(data):
    zstdctx = zstandard.ZstdDecompressor()
    decompressed = zstdctx.decompress(data)
    return decompressed

def create_image(width, height, pixels, sub_type):
    if sub_type == 0 or sub_type == 1:  # RGB8888
        return Image.frombytes("RGBA", (width, height), pixels, "raw")
    elif sub_type == 2:  # RGBA4444
        img = Image.new("RGBA", (width, height))
        ps = img.load()
        for h in range(height):
            for w in range(width):
                i = (w + h * width) * 2
                p = int.from_bytes(pixels[i : i + 2], "little")
                ps[w, h] = (
                    ((p >> 12) & 0xF) << 4,
                    ((p >> 8) & 0xF) << 4,
                    ((p >> 4) & 0xF) << 4,
                    ((p >> 0) & 0xF) << 4,
                )
        return img
    elif sub_type == 3:  # RBGA5551
        args = ("RGBA;4B", 0, 0)
        return Image.frombytes("RGBA", (width, height), pixels, "raw", args)
    elif sub_type == 4:  # RGB565
        img = Image.new("RGB", (width, height))
        ps = img.load()
        for h in range(height):
            for w in range(width):
                i = (w + h * width) * 2
                p = int.from_bytes(pixels[i : i + 2], "little")
                ps[w, h] = (
                    ((p >> 11) & 0x1F) << 3,
                    ((p >> 5) & 0x3F) << 2,
                    (p & 0x1F) << 3,
                )
        return img
    elif sub_type == 6:  # LA88
        return Image.frombytes("LA", (width, height), pixels)
    elif sub_type == 10:  # L8
        return Image.frombytes("L", (width, height), pixels)
    else:
        raise Exception(f"Unknown sub type '{sub_type}'")


def pixel_size(sub_type):
    if sub_type in [0, 1]:
        return 4
    elif sub_type in [2, 3, 4, 6]:
        return 2
    elif sub_type in [10]:
        return 1
    else:
        raise Exception(f"Unknown sub type '{sub_type}'")


def process_sc(base_name, data, path, old):
    decompressed = decompress(data[26:])

    reader = Reader(decompressed)

    if old:
        # Credits: https://github.com/Galaxy1036/Old-Sc-Dumper
        reader.read(17)
        count = reader.read_uint16()
        reader.read(count * 2)
        for i in range(count):  # skip strings
            reader.read_string()

    count = 0
    while len(reader):
        file_type = reader.read_byte()
        file_size = reader.read_uint32()

        if file_type not in [1, 24, 27, 28]:
            data = reader.read(file_size)
            continue

        sub_type = reader.read_byte()
        width = reader.read_uint16()
        height = reader.read_uint16()

        print(
            f"  file_type: {file_type}, file_size: {file_size}, "
            f"sub_type: {sub_type}, width: {width}, height: {height}"
        )

        if file_type == 27 or file_type == 28:
            pixel_sz = pixel_size(sub_type)
            block_sz = 32
            pixels = bytearray(file_size - 5)
            for _h in range(0, height, block_sz):
                for _w in range(0, width, block_sz):
                    for h in range(_h, min(_h + block_sz, height)):
                        i = (_w + h * width) * pixel_sz
                        sz = min(block_sz, width - _w) * pixel_sz
                        pixels[i : i + sz] = reader.read(sz)
            pixels = bytes(pixels)
        else:
            pixels = reader.read(file_size - 5)

        img = create_image(width, height, pixels, sub_type)
        img.save(os.path.join(path, f"{base_name}_{count}.png"))
        count += 1


def check_header(data):
    if data[0] == 0x5D:
        return "csv"
    if data[:2] == b"\x53\x43":
        return "sc"
    raise Exception("  Unknown header")


if __name__ == "__main__":
    path = os.path.normpath("Out-SC")
    file_list = os.listdir("In-SC")
    if len(file_list) == 0:
        print("Please put your _tex.sc files in", "In-SC", "folder")
    for file in file_list:
        try:
            if not file.endswith("_tex.sc"):
                print("Your file", file, "does not seem to be a _tex.sc file. You may experience errors")
            base_name, ext = os.path.splitext(os.path.basename(file))
            with open("In-SC/" + file, "rb") as f:
                print(f.name)
                data = f.read()
            process_sc(base_name, data, path, False)
        except Exception as e:
            print(f"{e.__class__.__name__} {e}")
