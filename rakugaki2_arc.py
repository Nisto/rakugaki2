# Rakugaki Oukoku 2 (Graffiti Kingdom) .arc extractor

import os
import sys
import zlib
import struct

def get_u8(buf, off):
    return struct.unpack("B", buf[off:off+1])[0]

def get_u16_le(buf, off):
    return struct.unpack("<H", buf[off:off+2])[0]

def get_u32_le(buf, off):
    return struct.unpack("<I", buf[off:off+4])[0]

def main(argc=len(sys.argv), argv=sys.argv):
    if argc != 2:
        print("Usage: %s <arc>" % argv[0])
        return 1

    in_path = os.path.realpath(sys.argv[1])
    in_dir = os.path.dirname(in_path)

    with open(in_path, "rb") as arc:
        arcbuf = arc.read()

    unknown  = get_u32_le(arcbuf, 0x00)
    numfiles = get_u32_le(arcbuf, 0x04)
    metaoff  = get_u32_le(arcbuf, 0x08)

    if unknown != 0x100:
        print("expected 0x100 at 0x00")
        return 1

    for i in range(numfiles):
        fileoff    = get_u32_le(arcbuf, metaoff+0x00)
        namelen    = get_u16_le(arcbuf, metaoff+0x04)
        zlibflag   = get_u8    (arcbuf, metaoff+0x06)
        #fullsize  = get_u32_le(arcbuf, metaoff+0x0C)
        filesize   = get_u32_le(arcbuf, metaoff+0x10)
        nameoff    = get_u32_le(arcbuf, metaoff+0x14)

        name = arcbuf[nameoff:nameoff+namelen].decode("ASCII")
        data = arcbuf[fileoff:fileoff+filesize]
        if zlibflag:
            data = zlib.decompress(data)

        outpath = os.path.join(in_dir, name)

        outdir = os.path.dirname(outpath)

        if not os.path.isdir(outdir):
            os.makedirs(outdir)

        with open(outpath, "wb") as fout:
            fout.write(data)

        metaoff += 24

if __name__=="__main__":
    main()