package qx;

import android.content.Context;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Set;

/**
 * 进程内脱壳（无需 root / frida）。
 * 三条路，任一条命中即拿到壳运行时解出的明文 dex：
 *   1. copyZprotect —— 壳把 origin.apk 解到 /data/data/<pkg>/.zprotect/<seed>/，本进程可读，直接搬走；
 *   2. scanMemory   —— 扫 /proc/self/mem 里的 dex 魔数（InMemoryDexClassLoader 场景内存里就是明文）；
 *   3. listMaps     —— 存一份 maps，留证。
 * 产物落 /sdcard/Android/data/<pkg>/files/qxdump/，adb pull 可直取（Android 11+ 亦可用）。
 */
public final class Dumper {

    private static final String TAG = "qx";
    private static final int CHUNK = 4 * 1024 * 1024;
    private static final long MIN_REGION = 64L * 1024;
    private static final long MAX_REGION = 128L * 1024 * 1024;
    private static final long MAX_DEX = 64L * 1024 * 1024;
    private static final long MAX_COPY = 400L * 1024 * 1024;

    private Dumper() {
    }

    public static void dump(Context ctx) {
        File out = outDir(ctx);
        Log.i(TAG, "dump start -> " + out);
        try {
            listMaps(out);
        } catch (Throwable t) {
            Log.e(TAG, "listMaps failed", t);
        }
        try {
            copyZprotect(ctx, out);
        } catch (Throwable t) {
            Log.e(TAG, "copyZprotect failed", t);
        }
        try {
            scanMemory(out);
        } catch (Throwable t) {
            Log.e(TAG, "scanMemory failed", t);
        }
        Log.i(TAG, "dump done -> " + out);
    }

    static File outDir(Context ctx) {
        File base = ctx.getExternalFilesDir(null);
        if (base == null) {
            base = ctx.getFilesDir();
        }
        File d = new File(base, "qxdump");
        d.mkdirs();
        return d;
    }

    // ---------------------------------------------------------------- maps

    private static void listMaps(File out) throws IOException {
        byte[] maps = readFile(new File("/proc/self/maps"), 8 * 1024 * 1024);
        writeFile(new File(out, "maps.txt"), maps);
        Log.i(TAG, "maps.txt written (" + maps.length + " bytes)");
        String[] lines = new String(maps, "UTF-8").split("\n");
        for (String l : lines) {
            String low = l.toLowerCase();
            if (low.contains("dex") || low.contains("zprotect") || low.contains("origin.apk")) {
                Log.i(TAG, "map: " + l);
            }
        }
    }

    // ----------------------------------------------------------- .zprotect

    private static void copyZprotect(Context ctx, File out) throws IOException {
        File src = new File(ctx.getApplicationInfo().dataDir, ".zprotect");
        if (!src.exists()) {
            Log.w(TAG, "no " + src);
            return;
        }
        File dst = new File(out, "zprotect");
        long[] budget = new long[]{MAX_COPY};
        int n = copyTree(src, dst, budget);
        Log.i(TAG, "zprotect copied files=" + n + " left budget=" + budget[0]);
    }

    private static int copyTree(File src, File dst, long[] budget) throws IOException {
        int n = 0;
        File[] kids = src.listFiles();
        if (kids == null) {
            return 0;
        }
        for (File k : kids) {
            if (k.isDirectory()) {
                n += copyTree(k, dst, budget);
                continue;
            }
            long len = k.length();
            if (len <= 0 || len > budget[0]) {
                Log.w(TAG, "skip " + k + " len=" + len);
                continue;
            }
            byte[] b = readFile(k, (int) Math.min(len, MAX_DEX * 2));
            File target = new File(dst, k.getName());
            writeFile(target, b);
            budget[0] -= b.length;
            n++;
            Log.i(TAG, "copied " + k + " (" + b.length + ") -> " + target);
        }
        return n;
    }

    // ------------------------------------------------------------- memory

    private static void scanMemory(File out) throws IOException {
        File dexDir = new File(out, "dex");
        dexDir.mkdirs();
        Set<String> seen = new HashSet<String>();
        RandomAccessFile mem = new RandomAccessFile("/proc/self/mem", "r");
        int regions = 0;
        int hits = 0;
        try {
            String[] lines = new String(readFile(new File("/proc/self/maps"), 8 * 1024 * 1024), "UTF-8").split("\n");
            byte[] buf = new byte[CHUNK + 8];
            for (String line : lines) {
                long[] r = parseRegion(line);
                if (r == null) {
                    continue;
                }
                long start = r[0];
                long size = r[1] - r[0];
                if (size < MIN_REGION || size > MAX_REGION) {
                    continue;
                }
                regions++;
                long pos = start;
                while (pos < r[1]) {
                    int want = (int) Math.min(CHUNK, r[1] - pos);
                    int got = readAt(mem, pos, buf, want);
                    if (got <= 0) {
                        break;
                    }
                    int from = 0;
                    while (true) {
                        int idx = indexOfDex(buf, from, got);
                        if (idx < 0) {
                            break;
                        }
                        long addr = pos + idx;
                        int fs = readDexSize(mem, addr);
                        if (fs > 0) {
                            byte[] dex = new byte[fs];
                            if (readAt(mem, addr, dex, fs) == fs) {
                                String md5 = md5(dex);
                                if (seen.add(md5)) {
                                    File f = new File(dexDir, String.format("mem_%x_%s.dex", addr, md5.substring(0, 8)));
                                    writeFile(f, dex);
                                    hits++;
                                    Log.i(TAG, "dex found " + f + " size=" + fs + " head=" + head(dex));
                                }
                            }
                        }
                        from = idx + 4;
                    }
                    pos += Math.max(1, got - 8);
                }
            }
        } finally {
            mem.close();
        }
        Log.i(TAG, "scanMemory regions=" + regions + " hits=" + hits);
    }

    /** 解析 maps 行；只收可读区域，跳过系统性只读映射（跑不出 dex，纯浪费时间）。 */
    private static long[] parseRegion(String line) {
        int sp = line.indexOf(' ');
        if (sp <= 0) {
            return null;
        }
        String[] parts = line.split("\\s+");
        if (parts.length < 2 || parts[1].length() < 3 || parts[1].charAt(0) != 'r') {
            return null;
        }
        String path = parts.length > 5 ? parts[5] : "";
        String low = path.toLowerCase();
        if (low.startsWith("/system") || low.startsWith("/apex") || low.startsWith("/dev")
                || low.startsWith("/vendor") || low.startsWith("/product")
                || low.endsWith(".so") || low.endsWith(".oat") || low.endsWith(".vdex")
                || low.endsWith(".art") || low.endsWith(".ttf") || low.endsWith(".odex")
                || low.endsWith(".jar") || low.contains("boot.art") || low.contains("boot.oat")) {
            return null;
        }
        int dash = parts[0].indexOf('-');
        if (dash <= 0) {
            return null;
        }
        try {
            return new long[]{Long.parseLong(parts[0].substring(0, dash), 16),
                    Long.parseLong(parts[0].substring(dash + 1), 16)};
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static int indexOfDex(byte[] b, int from, int len) {
        for (int i = from; i + 8 <= len; i++) {
            if (b[i] == 'd' && b[i + 1] == 'e' && b[i + 2] == 'x' && b[i + 3] == '\n'
                    && b[i + 4] == '0' && b[i + 5] == '3') {
                return i;
            }
        }
        return -1;
    }

    /** 校验 dex 头，返回 file_size；非法返回 -1。 */
    private static int readDexSize(RandomAccessFile mem, long addr) {
        byte[] h = new byte[112];
        if (readAt(mem, addr, h, 112) != 112) {
            return -1;
        }
        if (u4(h, 36) != 0x70 || u4(h, 40) != 0x12345678) {
            return -1;
        }
        long fs = u4(h, 32);
        if (fs < 112 || fs > MAX_DEX) {
            return -1;
        }
        return (int) fs;
    }

    private static long u4(byte[] b, int off) {
        return (b[off] & 0xffL) | ((b[off + 1] & 0xffL) << 8)
                | ((b[off + 2] & 0xffL) << 16) | ((b[off + 3] & 0xffL) << 24);
    }

    private static String head(byte[] dex) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 8 && i < dex.length; i++) {
            sb.append(String.format("%02x", dex[i]));
        }
        return sb.toString();
    }

    private static int readAt(RandomAccessFile f, long pos, byte[] buf, int len) {
        try {
            f.seek(pos);
            int off = 0;
            while (off < len) {
                int n = f.read(buf, off, len - off);
                if (n <= 0) {
                    break;
                }
                off += n;
            }
            return off;
        } catch (IOException e) {
            return 0;
        }
    }

    // --------------------------------------------------------------- misc

    private static byte[] readFile(File f, int cap) throws IOException {
        InputStream in = new java.io.FileInputStream(f);
        try {
            java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
            byte[] b = new byte[64 * 1024];
            int n;
            while ((n = in.read(b)) > 0 && bos.size() < cap) {
                bos.write(b, 0, n);
            }
            return bos.toByteArray();
        } finally {
            in.close();
        }
    }

    private static void writeFile(File f, byte[] b) throws IOException {
        File parent = f.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }
        FileOutputStream out = new FileOutputStream(f);
        try {
            out.write(b);
        } finally {
            out.close();
        }
    }

    private static String md5(byte[] b) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] d = md.digest(b);
            StringBuilder sb = new StringBuilder();
            for (byte x : d) {
                sb.append(String.format("%02x", x));
            }
            return sb.toString();
        } catch (Exception e) {
            return "nohash";
        }
    }
}
