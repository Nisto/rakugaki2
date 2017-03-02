# Rakugaki Oukoku 2 (Graffiti Kingdom) VFS extractor

import os
import sys
import struct

class ISOFS_IMAGE:
    #
    # DISCLAIMER:
    # Only supports reading the ISO filesystem / track (first track probably)
    # on NON-mixed-mode disk images.
    # -- Nisto
    #
    def __init__(self, path):
        self.path = path

        self.f = open(self.path, "rb")

        self.toc = {}

        self.f.seek(16 * 2352)
        pvd_raw = self.f.read(2352)

        self.f.seek(16 * 2048)
        pvd_user = self.f.read(2048)

        if self.is_raw_sector(pvd_raw) and self.is_pvd(pvd_raw[0x10:0x810]):
            #
            # Standard CD-ROM
            #
            pvd = pvd_raw[0x10:0x810]
            self.is_raw = 1
            self.is_xa = 0
            self.sector_size = 2352
            self.user_start = 0x10
            if pvd_raw[0x0F] == 1:
                self.user_size = 2048
                self.user_end = 0x810
            elif pvd_raw[0x0F] == 2:
                self.user_size = 2336
                self.user_end = 0x930
        elif self.is_raw_sector(pvd_raw) and self.is_pvd(pvd_raw[0x18:0x818]):
            #
            # CD-ROM XA
            #
            pvd = pvd_raw[0x18:0x818]
            self.is_raw = 1
            self.is_xa = 1
            self.sector_size = 2352
            self.user_start = 0x18
            # size of User Data is 2048 if Form 1, or 2324 if Form 2, and the
            # Form may vary across a track, so a global size / end offset of
            # the User Data doesn't really make sense for CD-ROM XA
            self.user_size = None
            self.user_end = None
        elif self.is_pvd(pvd_user):
            #
            # CD / DVD / ... (User Data only)
            #
            pvd = pvd_user
            self.is_raw = 0
            self.is_xa = 0
            self.sector_size = 2048
            self.user_start = 0x00
            self.user_size = 2048
            self.user_end = 2048
        else:
            print("Unrecognized disk image format")
            sys.exit(1)

        root_dr = self.drparse(pvd[0x9C:0xBE])

        self.seek_user(root_dr["lba"])

        root_dir = self.read_user(root_dr["size"])

        self.dirparse(root_dir)

    def is_raw_sector(self, buf):
        sync = buf[0x00:0x0C]
        if sync != b"\x00\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x00":
            return 0

        mm = buf[0x0C]
        if (mm>>4) & 0x0F > 9 or mm & 0x0F > 9:
            return 0

        ss = buf[0x0D]
        if (ss>>4) & 0x0F > 5 or ss & 0x0F > 9:
            return 0

        ff = buf[0x0E]
        if (ff>>4) & 0x0F > 7 or ff & 0x0F > 9 \
        or ((ff>>4) & 0x0F == 7 and ff & 0x0F > 4):
            return 0

        mode = buf[0x0F]
        if mode > 2:
            return 0

        return 1

    def is_pvd(self, buf):
        if len(buf) != 2048:
            return 0

        if buf[0x00:0x06] != b"\x01CD001":
            return 0

        return 1

    def set_xa(self, subcode):
        if subcode & 0b100000 == 0:
            self.user_size = 2048
            self.user_end = 0x818
        else:
            self.user_size = 2324
            self.user_end = 0x92C

    def read_user(self, size):
        usrbuf = b""
        if self.is_raw:
            offset_in_sector = self.f.tell() % self.sector_size
            if offset_in_sector != 0:
                if offset_in_sector < self.user_start:
                    self.f.seek(-offset_in_sector, os.SEEK_CUR)
                else:
                    if self.is_xa:
                        self.f.seek(-offset_in_sector, os.SEEK_CUR)
                        tmpbuf = self.f.read(offset_in_sector)
                        self.set_xa(tmpbuf[0x12])

                    if offset_in_sector < self.user_end:
                        user_remain = self.user_end - offset_in_sector

                        if size < user_remain:
                            return self.f.read(size)

                        usrbuf += self.f.read(user_remain)

                        size -= user_remain

                        self.f.seek(self.sector_size - (offset_in_sector + user_remain), os.SEEK_CUR)
                    else:
                        self.f.seek(self.sector_size - offset_in_sector, os.SEEK_CUR)

            if self.is_xa:
                while size > 0:
                    sectbuf = self.f.read(self.sector_size)
                    self.set_xa(sectbuf[0x12])
                    if size >= self.user_size:
                        usrbuf += sectbuf[self.user_start:self.user_end]
                        size -= self.user_size
                    else:
                        usrbuf += sectbuf[self.user_start:self.user_start+size]
                        self.f.seek(-self.sector_size + self.user_start + size, os.SEEK_CUR)
                        size = 0
            else:
                while size > 0:
                    if size >= self.user_size:
                        sectbuf = self.f.read(self.sector_size)
                        size -= self.user_size
                    else:
                        sectbuf = self.f.read(self.user_start + size)
                        size = 0
                    usrbuf += sectbuf[self.user_start:self.user_end]
        else:
            while size > 0:
                if size >= self.user_size:
                    usrbuf += self.f.read(self.user_size)
                    size -= self.user_size
                else:
                    usrbuf += self.f.read(size)
                    size = 0

        return usrbuf

    def seek_user(self, sectors, bytes=0):
        if self.is_xa:
            self.f.seek(sectors * self.sector_size)
            while bytes > 0:
                header = self.f.read(self.user_start)
                self.set_xa(header[0x12])
                if bytes >= self.user_size:
                    self.f.seek(self.sector_size - self.user_start, os.SEEK_CUR)
                    bytes -= self.user_size
                else:
                    self.f.seek(bytes, os.SEEK_CUR)
                    bytes = 0
        else:
            if self.is_raw and bytes > 0:
                sectors += bytes // self.user_size
                bytes = self.user_start + (bytes % self.user_size)
            self.f.seek(sectors * self.sector_size + bytes)

    def extract_user(self, lba, bytes, outpath):
        self.seek_user(lba)
        todo_size = bytes
        with open(outpath, "wb") as outfile:
            while todo_size > 0:
                read_size = min(2048, todo_size)
                buf = self.read_user(read_size)
                outfile.write(buf)
                todo_size -= read_size

    def drparse(self, drbuf):
        dr_size = get_u8(drbuf, 0x00)
        lba = get_u32_le(drbuf, 0x02)
        size = get_u32_le(drbuf, 0x0A)
        flags = get_u8(drbuf, 0x19)
        name_len = get_u8(drbuf, 0x20)
        name = drbuf[0x21 : 0x21 + name_len].decode("ASCII")

        if name == "\x00":
            name = '.'
        elif name == "\x01":
            name = '..'
        else:
            name = name.rsplit(';', 1)[0]

        return {"lba":lba, "size":size, "flags":flags, "name":name}

    def dirparse(self, dirbuf, dirname=''):
        i = 0
        subdirs = []
        while i < len(dirbuf) and dirbuf[i] > 0:
            dr_len = dirbuf[i]

            record = self.drparse(dirbuf[i:i+dr_len])

            if record["flags"] & 0b10 != 0 and record["name"] != '.' and record["name"] != '..':
                subdirs.append(record)
            elif record["flags"] & 0b10 == 0:
                self.toc[os.path.join('', dirname, record["name"]).replace(os.sep, '/')] = record
                self.toc[os.path.join('/', dirname, record["name"]).replace(os.sep, '/')] = record
                self.toc[os.path.join('./', dirname, record["name"]).replace(os.sep, '/')] = record

            i += dr_len

        for record in subdirs:
            self.seek_user(record["lba"])
            dirbuf = self.read_user(record["size"])
            self.dirparse(dirbuf, os.path.join(dirname, record["name"]))

def get_u8(buf, off):
    return struct.unpack("B", buf[off:off+1])[0]

def get_u16_le(buf, off):
    return struct.unpack("<H", buf[off:off+2])[0]

def get_u32_le(buf, off):
    return struct.unpack("<I", buf[off:off+4])[0]

def get_c_string(buf, off):
    end = off

    while buf[end] != 0:
        end += 1

    return buf[off:end].decode("ASCII")

def main(argc=len(sys.argv), argv=sys.argv):
    if argc != 2:
        print("Usage: %s <disk>" % argv[0])
        return 1

    in_path = os.path.realpath(argv[1])

    out_root = "%s - extracted" % os.path.splitext(in_path)[0]

    disk = ISOFS_IMAGE(in_path)

    disk.seek_user(disk.toc["DATATBL.BIN"]["lba"])

    datatbl = disk.read_user(disk.toc["DATATBL.BIN"]["size"])

    mapsect = disk.toc["CDVDMAP.BIN"]["lba"]

    # this stuff at the top seems to be irrelevant for what we want.
    # we just have to use some of the values to get to the table that we need.

    tbloff = 0
    table1_ent_cnt1 = get_u16_le(datatbl, tbloff+0x06)
    table1_ent_cnt2 = get_u16_le(datatbl, tbloff+0x08)
    table1_meta_off = get_u32_le(datatbl, tbloff+0x0C)

    tbloff = (((table1_meta_off + table1_ent_cnt1*24 + table1_ent_cnt2*24) - 1) & ~0xF) + 0x10
    table2_ent_cnt1 = get_u16_le(datatbl, tbloff+0x06)
    table2_ent_cnt2 = get_u16_le(datatbl, tbloff+0x08)
    table2_meta_off = get_u32_le(datatbl, tbloff+0x0C)

    numentries = table2_ent_cnt1 + table2_ent_cnt2

    metaoff = tbloff + table2_meta_off

    dupes = { }

    for i in range(numentries):
        nameoff    = get_u32_le(datatbl, metaoff+0x00)
        start_sect = get_u32_le(datatbl, metaoff+0x08)
        #end_sect  = get_u32_le(datatbl, metaoff+0x10)
        num_sects  = get_u32_le(datatbl, metaoff+0x18)

        vfs_path   = get_c_string(datatbl, tbloff + nameoff)
        vfs_path   = vfs_path.rsplit(";", 1)[0].strip("\\/")

        outpath    = os.path.join(out_root, vfs_path)
        outdir     = os.path.dirname(outpath)

        if not os.path.isdir(outdir):
            os.makedirs(outdir)

        # looks like there are some duplicate entries
        if os.path.isfile(outpath):
            if outpath not in dupes:
                dupes[outpath] = 0

            dupes[outpath] += 1

            outpath = "%s[%d]" % (outpath, dupes[outpath])

        disk.extract_user(mapsect+start_sect, num_sects*2048, outpath)

        metaoff += 32

if __name__=="__main__":
    main()