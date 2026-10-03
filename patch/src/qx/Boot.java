package qx;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.util.Log;

/**
 * 开发用钩子：作为 ContentProvider 由系统在进程启动时自动构造（早于 Application.onCreate），
 * 起一条后台线程延迟脱壳，把 454 壳运行时解出的明文 dex 落到外部私有目录，供 adb pull 取回。
 * 正式版（只是加觅Ta入口按钮）不装这个 provider。
 */
public class Boot extends ContentProvider {

    private static final int DELAY_MS = 25000;

    @Override
    public boolean onCreate() {
        final Context ctx = getContext();
        Log.i("qx", "Boot.onCreate pid=" + android.os.Process.myPid());
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    Thread.sleep(DELAY_MS);
                } catch (InterruptedException ignored) {
                }
                try {
                    Dumper.dump(ctx);
                } catch (Throwable t) {
                    Log.e("qx", "dump failed", t);
                }
            }
        }, "qx-dump");
        t.setDaemon(true);
        t.start();
        return true;
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        return null;
    }

    @Override
    public String getType(Uri uri) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }
}
