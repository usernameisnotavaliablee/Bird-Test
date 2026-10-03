package da;

import android.content.Context;

import java.util.Map;

/**
 * 编译期桩：只为让 qx/*.java 能通过 javac（javac 读不了 dex）。
 * 运行时解析到的是 454 明文 dex 里的真 Lda/b;（同名字、同描述符），桩不会被打进 dex。
 * 方法签名取自 /tmp/qx_build/flat/smali_classes3/da/b.smali。
 */
public class b {

    public b(Context context) {
    }

    public void A(String method) {
    }

    public void B(String url) {
    }

    public void v(f callback) {
    }

    public void y(Map params) {
    }

    public String q(Context context, String tag, e mode) {
        return null;
    }

    public String s(Context context, String tag, e mode, String loadingText) {
        return null;
    }

    /** Lda/b$f; */
    public interface f {
        void callback(String str);

        void callbackError(Exception exc);

        boolean validate(String str);
    }

    /** Lda/b$e; —— 常量 a 对应 HTTP_DEFALUT（见真实类 <clinit>）。 */
    public enum e {
        a, b
    }
}
