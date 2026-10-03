package qx;

import android.content.Context;
import android.util.Log;

/**
 * 签名绕过入口：直接触发改版注入的 bin/mt/signature/KillerApplication 静态初始化
 * （static{} 里做 killPM：替换 PackageInfo.CREATOR 伪造官方证书；killOpen：加载
 * libSignatureKiller.so 并 hook open() 把 base.apk 读重定向到 assets/SignatureKiller/origin.apk）。
 * 该类来自改版（ApkSignatureKillerEx），自包含、无外部依赖，故不重写。
 */
final class Killer {

    private Killer() {
    }

    static void install(Context ctx) {
        try {
            Class.forName("bin.mt.signature.KillerApplication");
            Log.i("qx", "killer: static init ok");
        } catch (Throwable t) {
            Log.e("qx", "killer: init failed", t);
        }
    }
}
