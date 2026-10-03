package qx;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.util.AttributeSet;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

/**
 * 首页右上角「觅Ta」入口按钮。
 * 由 res/layout/home_page_grid.xml 直接实例化（插在标题栏右侧 @id/blue 的左边），
 * 不需要任何 Java 侧钩子；类被加到 classes3.dex，父加载器可见即可被 LayoutInflater 反射构造。
 */
public class MitaEntry extends TextView {

    /** 2.6.454 manifest 里确认存在的觅Ta主页活动。 */
    private static final String MITA_HOME =
            "com.kingosoft.activity_kb_common.ui.activity.new_wdjx.new_kebiao.MitaNew2Activity";

    public MitaEntry(Context context, AttributeSet attrs) {
        super(context, attrs);
        setText("觅Ta");
        setTextSize(15f);
        setTextColor(Color.parseColor("#333333"));
        setGravity(Gravity.CENTER);
        int pad = (int) (getResources().getDisplayMetrics().density * 8);
        setPadding(pad, 0, pad, 0);
        setClickable(true);
        setOnClickListener(new OnClickListener() {
            @Override
            public void onClick(View v) {
                open(v.getContext());
            }
        });
    }

    /** 打开觅Ta服务；入口与首页「更多」菜单里的觅Ta项一致。 */
    public static void open(Context ctx) {
        Intent i = new Intent();
        try {
            // 壳把内嵌 dex 直接注进宿主 ClassLoader（libzprotect: makeInMemoryDexElements），
            // 两条路都通：先按类名解析，失败再走组件名交给框架解析。
            i.setClass(ctx, Class.forName(MITA_HOME));
        } catch (Throwable t) {
            Log.w("qx", "Class.forName failed, fallback to component name", t);
            i.setClassName(ctx.getPackageName(), MITA_HOME);
        }
        if (!(ctx instanceof Activity)) {
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        }
        try {
            ctx.startActivity(i);
            Log.i("qx", "mita entry: start " + MITA_HOME);
        } catch (Throwable t) {
            Log.e("qx", "mita entry failed", t);
            Toast.makeText(ctx, "觅Ta 入口启动失败: " + t, Toast.LENGTH_LONG).show();
        }
    }
}
