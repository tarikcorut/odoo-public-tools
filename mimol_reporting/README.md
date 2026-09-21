# Raporlama Merkezi (mimol_reporting)

Odoo 17 için, herhangi bir iş modülüne bağımlı olmayan çalışma ve raporlama merkezi.
Tek kaynak **mail.activity**: raporlanmak isteyen süreç aktivite açar, merkez onu
kendiliğinden gösterir.

## Ne yapar
- **İşlerim → Benim İşlerim / Onaylarım / Görevlerim**: giriş yapan kullanıcının açık
  aktiviteleri; Geciken | Bugün | Planlanan sütunları (sayılar başlıkta), uygulama,
  belge, kimden geldiği, son tarih. "Aç" belgeye gider; görevlerde "Tamamlandı".
- **Geçmişim**: tamamlanan aktiviteler silinmez, arşivlenir. Kim, ne zaman, kaç günde,
  gecikmeli mi, sonuç (Tamamlandı / Reddedildi / İptal), geri bildirim.
- **Yönetim** (Yönetici grubu): tüm açık işler, tüm geçmiş, pivot/grafik raporlar.
- **Panolar**: sistemdeki mevcut panolar kategori kartları olarak. Görünürlük panonun
  kendi menüsünden gelir: menüyü modülünde görebilen burada da görür, göremeyen görmez.
  "Panoya Git" aynı panoyu açar, kopya yoktur. Kayıt kaydedilince Raporlama Merkezi /
  Panolar / Kategori altında aynı aksiyona bağlı menü üretilir.
- **Ayarlar**: aktivite tipi başına Raporlama Türü (Onay / Görev / Bilgi) ve gizleme,
  geçmişi saklama, gecikme eşikleri, merkezde gizlenecek modeller, Panoları Tara.

## Nasıl çalışır (Odoo standardı)
- Odoo 17 aktivite tipindeki **Keep Done** açıksa tamamlanan aktivite `active=False`
  ile arşivlenir. Kurulumda tüm tiplerde açılır; yeni tipler de varsayılan açık gelir.
- Eklenen alanlar: `mail.activity.type.reporting_kind / reporting_exclude`;
  `mail.activity.reporting_kind, res_model_name, deadline_state, done_user_id,
  date_done_dt, done_result, done_feedback, duration_days, was_late`.
- Süreç kodu red / iptal sonucunu bildirmek için context kullanır:
  `activity.with_context(activity_done_result='refused').action_feedback(feedback='...')`
  ya da aktiviteyi kaldırırken `with_context(activity_done_result='cancelled').unlink()`
  (tip geçmişi saklıyorsa silmek yerine arşivlenir).
- `deadline_state` saklı alandır; gece cron'u (00:10) Planlanan → Bugün → Geciken
  geçişlerini tazeler.
- Menüler sunucu aksiyonuyla `mail.activity.action_reporting_open(mode)` çağırır;
  domain ve görünümler orada kurulur (gizli tipler / modeller dışarıda).

## Yeni bir süreci merkeze almak
1. Süreç için bir aktivite tipi tanımlayın (Ayarlar → Aktivite Tipleri), Raporlama
   Türünü seçin (Onay / Görev), Keep Done açık olsun.
2. Süreç adımında `record.activity_schedule(activity_type_id=..., user_id=...)` ile
   aktivite açın; adım bitince `activity_feedback` / `activity_unlink` ile kapatın.
3. Başka bir şey gerekmez; Benim İşlerim, Geçmişim ve raporlar bunu otomatik gösterir.

## Güvenlik
- `group_reporting_user`: tüm iç kullanıcılar (kendi işleri, görebildiği panolar).
- `group_reporting_manager`: yönetim menüsü, ayarlar, pano kayıt defteri.
- Aktivite erişimi Odoo standardıdır (belgeyi okuyabilen aktivitesini görür).
- Pano açma sunucu tarafında kaynak menünün görünürlüğüyle denetlenir.
