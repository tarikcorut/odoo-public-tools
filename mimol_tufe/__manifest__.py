# -*- coding: utf-8 -*-
{
    'name': "Mimol TÜFE / ÜFE Endeksleri",
    'version': '17.0.1.0.0',
    'category': 'Technical',
    'summary': "Türkiye TÜİK TÜFE endeksleri — otomatik senkronizasyon ve sorgulama",
    'description': """
Türkiye TÜFE (Tüketici Fiyat Endeksi) verilerini hakedis.org üzerinden
otomatik çeker ve merkezî bir tabloda tutar. Kira artışı, aidat endeksleme,
sözleşme revizyonu gibi ihtiyaçlar için tüm modüllerden erişilebilir.
    """,
    'author': "Mimol Yazılım",
    'website': "https://www.mimol.com.tr",
    'depends': ['base'],
    'external_dependencies': {'python': ['bs4']},
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/mimol_tufe_index_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
