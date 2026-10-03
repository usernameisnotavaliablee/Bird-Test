package qx;

import android.util.Log;

/** dump 版 provider：多跑一段自检 + 进程内脱壳。 */
public class BootDump extends Boot {

    private static final int DELAY_MS = 25000;

    @Override
    protected void afterInstall(final android.content.Context ctx) {
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    Thread.sleep(DELAY_MS);
                } catch (InterruptedException ignored) {
                }
                try {
                    Smoke.run(ctx);
                } catch (Throwable t) {
                    Log.e("qx", "smoke failed", t);
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
    }
}
