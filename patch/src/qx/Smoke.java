package qx;

import android.content.Context;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

/**
 * 开发用自检：壳把内嵌 dex 注进宿主 ClassLoader，布局里的 qx.MitaEntry 能不能被 inflater 解析、
 * payload 类加载器与宿主是不是同一个——这两条决定「首页右上角按钮」方案成立与否。
 * 结论只写 logcat（qx 标签）。
 */
public final class Smoke {

    private Smoke() {
    }

    public static void run(Context ctx) {
        ClassLoader app = Smoke.class.getClassLoader();
        Log.i("qx", "smoke: host loader=" + app);
        try {
            Class<?> base = Class.forName("com.kingosoft.activity_kb_common.BaseApplication");
            ClassLoader payload = base.getClassLoader();
            Log.i("qx", "smoke: payload loader=" + payload + " sameAsHost=" + (payload == app));
            int i = 0;
            for (ClassLoader l = payload; l != null && i < 8; l = l.getParent(), i++) {
                Log.i("qx", "smoke:   chain[" + i + "]=" + l);
            }
            Log.i("qx", "smoke: payload loader sees qx.MitaEntry = "
                    + (payload.loadClass("qx.MitaEntry") != null));
        } catch (Throwable t) {
            Log.e("qx", "smoke: payload loader check failed", t);
        }
        try {
            int layout = ctx.getResources().getIdentifier("home_page_grid", "layout", ctx.getPackageName());
            Log.i("qx", "smoke: home_page_grid id=" + Integer.toHexString(layout));
            View v = LayoutInflater.from(ctx).inflate(layout, null);
            Log.i("qx", "smoke: inflated ok, root=" + v.getClass().getName()
                    + " hasMitaEntry=" + hasEntry(v));
            Log.i("qx", "smoke: blue(more) present="
                    + (v.findViewById(ctx.getResources().getIdentifier("blue", "id", ctx.getPackageName())) != null));
        } catch (Throwable t) {
            Log.e("qx", "smoke: inflate home_page_grid failed", t);
        }
    }

    private static boolean hasEntry(View v) {
        if (v.getClass().getName().equals("qx.MitaEntry")) {
            return true;
        }
        if (v instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) {
                if (hasEntry(g.getChildAt(i))) {
                    return true;
                }
            }
        }
        return false;
    }
}
