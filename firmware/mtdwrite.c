/*
 * mtdwrite — write a firmware image to a raw MTD partition on the Harmony Hub.
 *
 * Built for MIPS32 BE / uClibc (static). Run only from a root shell on the
 * device, with a verified backup. This is NOT installed on the Hub.
 *
 * Usage:
 *   mtdwrite --info /dev/mtd3
 *   mtdwrite --backup /dev/mtd3 root-backup.bin
 *   mtdwrite --write /dev/mtd3 harmony-image.custom.squashfs --yes
 *   mtdwrite --write /dev/mtd3 image.bin --yes --verify
 *
 * Safety: --write refuses to run without --yes. The image must fit the
 * partition. Erase is performed in the device's erase-block size.
 */
#include <errno.h>
#include <fcntl.h>
#include <mtd/mtd-user.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

#define CHUNK 65536

static void die(const char *msg) {
    fprintf(stderr, "mtdwrite: %s: %s\n", msg, strerror(errno));
    exit(1);
}

static uint64_t fnv1a(const unsigned char *p, size_t n) {
    uint64_t h = 1469598103934665603ULL;
    size_t i;
    for (i = 0; i < n; i++) {
        h ^= p[i];
        h *= 1099511628211ULL;
    }
    return h;
}

static unsigned char *read_file(const char *path, size_t *len) {
    FILE *f = fopen(path, "rb");
    unsigned char *buf;
    long sz;
    if (!f) die(path);
    if (fseek(f, 0, SEEK_END) != 0) die("fseek");
    sz = ftell(f);
    if (sz < 0) die("ftell");
    if (fseek(f, 0, SEEK_SET) != 0) die("fseek");
    buf = malloc((size_t)sz ? (size_t)sz : 1);
    if (!buf) die("malloc");
    if (sz && fread(buf, 1, (size_t)sz, f) != (size_t)sz) die("fread");
    fclose(f);
    *len = (size_t)sz;
    return buf;
}

static void write_all(int fd, const unsigned char *buf, size_t len) {
    size_t off = 0;
    while (off < len) {
        ssize_t n = write(fd, buf + off, len - off);
        if (n < 0) {
            if (errno == EINTR) continue;
            die("write");
        }
        if (n == 0) die("short write");
        off += (size_t)n;
    }
}

static void read_exact(int fd, unsigned char *buf, size_t len) {
    size_t off = 0;
    while (off < len) {
        ssize_t n = read(fd, buf + off, len - off);
        if (n < 0) {
            if (errno == EINTR) continue;
            die("read");
        }
        if (n == 0) die("short read");
        off += (size_t)n;
    }
}

int main(int argc, char **argv) {
    const char *mode = NULL, *dev = NULL, *file = NULL;
    int yes = 0, verify = 0, squashfs = 0;
    int fd, i;
    mtd_info_t info;
    unsigned char *image = NULL, *back = NULL;
    size_t image_len = 0;

    if (argc < 3) {
        fprintf(stderr,
            "usage:\n"
            "  %s --info <mtddev>\n"
            "  %s --backup <mtddev> <outfile>\n"
            "  %s --write <mtddev> <image> [--yes] [--verify] [--squashfs]\n", argv[0], argv[0], argv[0]);
        return 2;
    }
    mode = argv[1];
    dev = argv[2];
    for (i = 3; i < argc; i++) {
        if (!strcmp(argv[i], "--yes")) yes = 1;
        else if (!strcmp(argv[i], "--verify")) verify = 1;
        else if (!strcmp(argv[i], "--squashfs")) squashfs = 1;
        else if (!file) file = argv[i];
        else { fprintf(stderr, "mtdwrite: unexpected argument %s\n", argv[i]); return 2; }
    }
    if (strncmp(dev, "/dev/mtd", 8) != 0) {
        fprintf(stderr, "mtdwrite: refusing non-mtd path %s\n", dev);
        return 2;
    }
    fd = open(dev, O_RDWR);
    if (fd < 0) die(dev);
    if (ioctl(fd, MEMGETINFO, &info) != 0) die("MEMGETINFO");

    printf("device=%s size=%u erasesize=%u writesize=%u type=%u\n",
           dev, info.size, info.erasesize, info.writesize, info.type);

    if (!strcmp(mode, "--info")) {
        close(fd);
        return 0;
    }

    if (!strcmp(mode, "--backup")) {
        FILE *out;
        if (!file) { fprintf(stderr, "mtdwrite: --backup needs an output file\n"); close(fd); return 2; }
        out = fopen(file, "wb");
        if (!out) die(file);
        back = malloc(info.size ? info.size : 1);
        if (!back) die("malloc");
        read_exact(fd, back, info.size);
        if (fwrite(back, 1, info.size, out) != info.size) die("fwrite");
        fclose(out);
        printf("backup=%s bytes=%u fnv1a=%016llx\n", file, info.size,
               (unsigned long long)fnv1a(back, info.size));
        close(fd);
        return 0;
    }

    if (strcmp(mode, "--write") != 0) {
        fprintf(stderr, "mtdwrite: unknown mode %s\n", mode);
        close(fd);
        return 2;
    }
    if (!file) { fprintf(stderr, "mtdwrite: --write needs an image\n"); close(fd); return 2; }
    image = read_file(file, &image_len);
    if (squashfs && (image_len < 4 || memcmp(image, "hsqs", 4) != 0)) {
        fprintf(stderr, "mtdwrite: image is not a SquashFS (missing hsqs magic)\n");
        close(fd);
        return 1;
    }
    printf("image=%s bytes=%u fnv1a=%016llx\n", file, (unsigned)image_len,
           (unsigned long long)fnv1a(image, image_len));
    if (image_len > info.size) {
        fprintf(stderr, "mtdwrite: image (%u) larger than partition (%u)\n",
                (unsigned)image_len, info.size);
        close(fd);
        return 1;
    }
    if (!yes) {
        fprintf(stderr, "mtdwrite: refusing to write without --yes (dry run)\n");
        close(fd);
        return 1;
    }

    {
        size_t erase_len = (image_len + info.erasesize - 1) / info.erasesize * info.erasesize;
        size_t off;
        printf("erasing %u bytes in %u-byte blocks\n", (unsigned)erase_len, info.erasesize);
        for (off = 0; off < erase_len; off += info.erasesize) {
            struct erase_info_user e;
            e.start = (uint32_t)off;
            e.length = info.erasesize;
            if (ioctl(fd, MEMERASE, &e) != 0) die("MEMERASE");
        }
    }
    if (lseek(fd, 0, SEEK_SET) < 0) die("lseek");
    write_all(fd, image, image_len);
    if (fsync(fd) != 0) die("fsync");
    printf("write=ok\n");

    if (verify) {
        back = malloc(image_len ? image_len : 1);
        if (!back) die("malloc");
        if (lseek(fd, 0, SEEK_SET) < 0) die("lseek");
        read_exact(fd, back, image_len);
        if (memcmp(image, back, image_len) != 0) {
            fprintf(stderr, "mtdwrite: verify FAILED\n");
            close(fd);
            return 1;
        }
        printf("verify=ok fnv1a=%016llx\n", (unsigned long long)fnv1a(back, image_len));
    }
    close(fd);
    free(image);
    free(back);
    return 0;
}
