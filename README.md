 ## StreamBox
@@
-# chmod -R 777 /var/lib/streambox/hls
+# لا تستخدم 777
+# على السيرفر (اختياري لو تستخدم volume خارجي):
+# sudo mkdir -p /var/lib/streambox/hls
+# sudo chown -R 1000:1000 /var/lib/streambox/hls
@@
-# تشغيل
+# تشغيل
 docker compose up -d
+
+# تحقق
+# API
+# curl http://127.0.0.1:8000/health
+#
+# HLS
+# curl -I http://127.0.0.1:8081/health
+
+# ملاحظة:
+# إذا وضعت API_KEY في .env يجب إرسال الهيدر:
+# X-API-Key: <API_KEY>
