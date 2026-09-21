# -*- coding: utf-8 -*-
{
    'name': "Raporlama Merkezi",
    'version': '17.0.1.5.0',
    'category': 'Productivity',
    'summary': "İşlerim, onaylarım, geçmişim ve tüm panolar tek yerde — Odoo aktiviteleri üzerine kurulu",
    'description': """
Raporlama Merkezi
=================
Odoo'nun standart aktivite (mail.activity) altyapısını tek bir çalışma
merkezine dönüştürür:

- **Benim İşlerim**: onay, görev ve bilgi aktivitelerim; Geciken / Bugün / Planlanan
- **Onaylarım / Görevlerim**: aktivite tipinin "Raporlama Türü"ne göre ayrılmış listeler
- **Geçmişim**: tamamlanan aktiviteler silinmez, arşivlenir (kim, ne zaman, kaç günde,
  gecikmeli mi, sonuç: tamamlandı / reddedildi / iptal)
- **Yönetim**: tüm açık işler ve geçmiş; pivot / grafik raporlar
- **Panolar**: sistemdeki mevcut panolar (dashboard) kategorilere göre tek sayfada;
  panonun kendi menüsünü görebilen görür, göremeyen görmez (yetki kopyalanmaz)

Kural basittir: raporlanmak isteyen süreç aktivite açar. Yeni bir süreç
eklendiğinde kendi aktivite tipini tanımlar, merkez onu kendiliğinden gösterir.
Hiçbir iş modülüne bağımlılık yoktur.
    """,
    'author': "Mimol Yazılım",
    'website': "https://www.mimol.com.tr",
    'support': "info@mimol.com.tr",
    'license': 'LGPL-3',
    'depends': ['mail', 'base_setup'],
    'data': [
        'security/reporting_security.xml',
        'security/ir.model.access.csv',
        'data/reporting_data.xml',
        'views/mail_activity_type_views.xml',
        'views/mail_activity_views.xml',
        'views/reporting_dashboard_views.xml',
        'views/res_config_settings_views.xml',
        'views/reporting_menus.xml',
        'data/reporting_categories.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
    'auto_install': False,
}
