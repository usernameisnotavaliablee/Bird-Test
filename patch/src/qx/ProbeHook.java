package qx;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.text.TextUtils;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/**
 * 在「人已经查到」的页面上挂一个「榨干Ta」按钮 → 打开 {@link ProbeActivity} 弹窗。
 *
 * 命中页面（都在 new_kebiao 包下）：
 *   TdkbActivity          Ta的课表（收藏/取消收藏所在页）
 *   TaWeekCourseActivity  他人周课表
 *   ClassmateInfoActivity 同学信息页
 *   TeaInfoActivity       教师信息页
 *   GrxxActivity          扫码落地身份页
 *
 * 实现走 ActivityLifecycleCallbacks，不改任何官方 smali/布局——按钮是运行时加在
 * android.R.id.content 上的浮层；目标身份从宿主 Intent 的 extras 里取（就是页面自己收到的那些）。
 */
public class ProbeHook implements Application.ActivityLifecycleCallbacks {

    private static final String TAG = "qx";
    private static final String PKG = "com.kingosoft.activity_kb_common.ui.activity.new_wdjx.new_kebiao.";
    private static final Set<String> HOSTS = new HashSet<String>(Arrays.asList(
            "TdkbActivity", "TaWeekCourseActivity", "ClassmateInfoActivity",
            "TeaInfoActivity", "GrxxActivity"));
    private static final String VIEW_TAG = "qx_probe_btn";

    /** 宿主 Intent 里可能承载目标身份的键（不同入口命名不一致，全试一遍）。 */
    private static final String[] K_NAME = {"Name", "name", "xm"};
    private static final String[] K_XB = {"XB", "xb"};
    private static final String[] K_BJMC = {"BJMC", "bjmc"};
    private static final String[] K_JID = {"JID", "mJid", "jid"};
    private static final String[] K_UUID = {"otheruuid", "uuid", "mUuid", "JIDimagePath"};
    private static final String[] K_TYPE = {"usertype", "userType", "sf", "type"};

    public static void install(Context ctx) {
        try {
            Application app = (Application) ctx.getApplicationContext();
            app.registerActivityLifecycleCallbacks(new ProbeHook());
            Log.i(TAG, "ProbeHook installed");
        } catch (Throwable t) {
            Log.e(TAG, "ProbeHook install failed", t);
        }
    }

    @Override
    public void onActivityResumed(Activity a) {
        try {
            if (!isHost(a) || a.getIntent() == null) {
                return;
            }
            ViewGroup content = (ViewGroup) a.findViewById(android.R.id.content);
            if (content == null || content.findViewWithTag(VIEW_TAG) != null) {
                return;
            }
            TextView btn = new TextView(a);
            btn.setTag(VIEW_TAG);
            btn.setText("榨干Ta");
            btn.setTextSize(12f);
            btn.setTextColor(Color.WHITE);
            btn.setGravity(Gravity.CENTER);
            btn.setBackgroundColor(Color.parseColor("#CC7B2FBE"));
            int px = dp(a, 10);
            btn.setPadding(px, px / 2, px, px / 2);
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.gravity = Gravity.TOP | Gravity.END;
            lp.topMargin = dp(a, 56);
            lp.rightMargin = dp(a, 10);
            btn.setLayoutParams(lp);
            btn.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    Activity host = (Activity) v.getContext();
                    Log.i(TAG, "probe: open from " + host.getClass().getName());
                    ProbeActivity.open(host, buildPayload(host));
                }
            });
            content.addView(btn);
            Log.i(TAG, "probe button injected into " + a.getClass().getSimpleName());
        } catch (Throwable t) {
            Log.e(TAG, "inject failed", t);
        }
    }

    private static boolean isHost(Activity a) {
        String cn = a.getClass().getName();
        if (!cn.startsWith(PKG)) {
            return false;
        }
        return HOSTS.contains(cn.substring(PKG.length()));
    }

    /** 把宿主页面收到的目标身份原样搬给弹窗。 */
    private static Intent buildPayload(Activity host) {
        Intent src = host.getIntent();
        Intent out = new Intent();
        out.putExtra("qx_host", host.getClass().getSimpleName());
        out.putExtra("qx_name", first(src, K_NAME));
        out.putExtra("qx_xb", first(src, K_XB));
        out.putExtra("qx_bjmc", first(src, K_BJMC));
        out.putExtra("qx_jid", first(src, K_JID));
        out.putExtra("qx_uuid", first(src, K_UUID));
        String type = first(src, K_TYPE);
        if (TextUtils.isEmpty(type)) {
            // 教师页没带身份时：有工号(gh) 或 页面是 TeaInfoActivity → 按教师试
            boolean tea = !TextUtils.isEmpty(src.getStringExtra("gh"))
                    || "TeaInfoActivity".equals(out.getStringExtra("qx_host"));
            type = tea ? "TEA" : "STU";
        }
        out.putExtra("qx_type", type);
        // 原始 extras 全量留档，弹窗里可对照
        Bundle b = src.getExtras();
        if (b != null) {
            StringBuilder sb = new StringBuilder();
            for (String k : b.keySet()) {
                Object v = b.get(k);
                sb.append(k).append('=').append(v).append('\n');
            }
            out.putExtra("qx_raw", sb.toString());
        }
        return out;
    }

    private static String first(Intent src, String[] keys) {
        for (String k : keys) {
            String v = src.getStringExtra(k);
            if (!TextUtils.isEmpty(v)) {
                return v;
            }
        }
        return "";
    }

    private static int dp(Context c, int v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                c.getResources().getDisplayMetrics());
    }

    // 其余生命周期回调留空
    @Override
    public void onActivityCreated(Activity a, Bundle b) {
    }

    @Override
    public void onActivityStarted(Activity a) {
    }

    @Override
    public void onActivityPaused(Activity a) {
    }

    @Override
    public void onActivityStopped(Activity a) {
    }

    @Override
    public void onActivitySaveInstanceState(Activity a, Bundle b) {
    }

    @Override
    public void onActivityDestroyed(Activity a) {
    }
}
