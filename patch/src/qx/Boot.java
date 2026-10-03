package qx;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.util.Log;

/**
 * 注入层入口：ContentProvider 由系统在进程启动时自动构造（早于 Application.onCreate，
 * 也早于壳把内嵌 dex 交给业务 Application 的那一刻），在这里挂签名绕过。
 * 变体：dump 版换成 qx.BootDump（多一段脱壳），见 build.sh。
 */
public class Boot extends ContentProvider {

    @Override
    public boolean onCreate() {
        Context ctx = getContext();
        Log.i("qx", "Boot.onCreate pid=" + android.os.Process.myPid());
        Killer.install(ctx);
        ProbeHook.install(ctx);
        afterInstall(ctx);
        return true;
    }

    /** 子类钩子（dump 版在此起脱壳线程）。 */
    protected void afterInstall(Context ctx) {
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
