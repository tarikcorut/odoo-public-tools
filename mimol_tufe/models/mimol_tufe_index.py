import logging
import ssl
import urllib.request

from bs4 import BeautifulSoup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

INDEX_SOURCES = {
    'tufe': (
        'TÜFE',
        "https://www.hakedis.org/endeksler/"
        "tuketici-fiyat-genel-endeksi-ve-degisim-oranlari-2003",
    ),
    'ufe': (
        'Yİ-ÜFE',
        "https://www.hakedis.org/endeksler/"
        "yi-ufe-yurtici-uretici-fiyat-endeksi",
    ),
}


class MimolTufeIndex(models.Model):
    _name = 'mimol.tufe.index'
    _description = 'Türkiye Ekonomik Endeksleri (TÜFE / Yİ-ÜFE)'
    _order = 'year desc, month desc, index_type'
    _rec_name = 'display_name'

    index_type = fields.Selection(
        [('tufe', 'TÜFE'), ('ufe', 'Yİ-ÜFE')],
        string='Endeks Tipi',
        required=True,
        default='tufe',
        index=True,
    )
    year = fields.Char(string='Yıl', required=True, index=True)
    month = fields.Selection(
        [
            ('1', 'Ocak'), ('2', 'Şubat'), ('3', 'Mart'), ('4', 'Nisan'),
            ('5', 'Mayıs'), ('6', 'Haziran'), ('7', 'Temmuz'), ('8', 'Ağustos'),
            ('9', 'Eylül'), ('10', 'Ekim'), ('11', 'Kasım'), ('12', 'Aralık'),
        ],
        string='Ay', required=True, index=True,
    )
    index_value = fields.Float(string='Endeks Değeri', digits=(16, 2))
    display_name = fields.Char(compute='_compute_display_name', store=True)

    last_fetched_at = fields.Datetime(string='Son Çekilme', readonly=True)
    source_url = fields.Char(string='Kaynak URL', readonly=True)

    _sql_constraints = [
        ('type_year_month_uniq', 'unique (index_type, year, month)',
         'Bir yıl, ay ve endeks tipi için sadece bir kayıt olabilir!'),
    ]

    @api.depends('index_type', 'year', 'month')
    def _compute_display_name(self):
        month_map = dict(self._fields['month'].selection)
        type_map = dict(self._fields['index_type'].selection)
        for rec in self:
            parts = [
                type_map.get(rec.index_type, ''),
                month_map.get(rec.month, ''),
                rec.year or '',
            ]
            rec.display_name = ' '.join(p for p in parts if p)

    # ---- lookup helpers --------------------------------------------------

    @api.model
    def get_index_value(self, index_type, year, month):
        """Return the index value for (index_type, year, month). Raises if
        the record does not exist; caller must handle missing months (e.g.
        when the current month is not yet published)."""
        rec = self.search([
            ('index_type', '=', index_type),
            ('year', '=', str(year)),
            ('month', '=', str(month)),
        ], limit=1)
        if not rec:
            raise UserError(_(
                "%(label)s endeks değeri bulunamadı: %(y)s/%(m)s",
                label=INDEX_SOURCES[index_type][0], y=year, m=month,
            ))
        return rec.index_value

    @api.model
    def get_yoy_change(self, index_type, reference_date):
        """Yıllık yüzde değişim: (ref / ref-12ay - 1) * 100.

        reference_date genelde bir önceki ayın endeksinin yayınlandığı dönem
        olmalıdır (örn. Nisan'da kira artışı için Mart endeksi alınır)."""
        cur_year, cur_month = reference_date.year, reference_date.month
        prev_year = cur_year - 1
        current = self.get_index_value(index_type, cur_year, cur_month)
        previous = self.get_index_value(index_type, prev_year, cur_month)
        if not previous:
            raise UserError(_(
                "%(label)s için bir önceki yıl (%(y)s/%(m)s) endeks değeri sıfır.",
                label=INDEX_SOURCES[index_type][0], y=prev_year, m=cur_month,
            ))
        return (current / previous - 1.0) * 100.0

    # ---- fetch core ------------------------------------------------------

    def _scrape_hakedis_table(self, url):
        """Fetch the URL and return the first data table with >5 rows.

        Returns the <tbody> (or table) element. Raises UserError on failure.
        """
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, context=ctx, timeout=30).read()
        soup = BeautifulSoup(html, 'html.parser')

        tables = soup.find_all('table')
        if not tables:
            raise UserError(_("Kaynakta hiçbir tablo bulunamadı: %s") % url)

        for tbl in tables:
            if len(tbl.find_all('tr')) > 5:
                return tbl.find('tbody') or tbl
        raise UserError(_("Kaynakta geçerli bir endeks tablosu bulunamadı: %s") % url)

    def _fetch_index_type(self, index_type):
        """Scrape one index type and upsert rows.

        Returns (created, updated) counts.
        """
        label, url = INDEX_SOURCES[index_type]
        body = self._scrape_hakedis_table(url)
        rows = body.find_all('tr')

        fetched_at = fields.Datetime.now()
        created = 0
        updated = 0

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 2:
                continue
            year_str = cols[0].text.strip()
            if not year_str.isdigit():
                continue
            for month_idx, col in enumerate(cols[1:13], start=1):
                val_str = col.text.strip()
                if not val_str:
                    continue
                try:
                    val_float = float(val_str.replace('.', '').replace(',', '.'))
                except ValueError:
                    raise UserError(_(
                        "%(label)s değeri dönüştürülemedi: '%(val)s' "
                        "(Yıl: %(year)s, Ay: %(month)s).",
                        label=label, val=val_str, year=year_str, month=month_idx,
                    ))
                month_str = str(month_idx)
                existing = self.search([
                    ('index_type', '=', index_type),
                    ('year', '=', year_str),
                    ('month', '=', month_str),
                ], limit=1)
                vals = {
                    'index_value': val_float,
                    'last_fetched_at': fetched_at,
                    'source_url': url,
                }
                if existing:
                    if existing.index_value != val_float:
                        existing.write(vals)
                        updated += 1
                        _logger.info(
                            "Updated %s for %s/%s: %s",
                            label, month_str, year_str, val_float,
                        )
                else:
                    self.create(dict(vals,
                                     index_type=index_type,
                                     year=year_str,
                                     month=month_str))
                    created += 1
                    _logger.info(
                        "Created %s for %s/%s: %s",
                        label, month_str, year_str, val_float,
                    )
        return created, updated

    def _fetch_all_indexes(self):
        """Scrape every index type defined in INDEX_SOURCES."""
        totals = {}
        for idx_type in INDEX_SOURCES:
            totals[idx_type] = self._fetch_index_type(idx_type)
        return totals

    # ---- entry points ----------------------------------------------------

    @api.model
    def _cron_fetch_tufe_indexes(self):
        """Daily cron — fetches all index types, logs per-type outcome,
        swallows exceptions so one source's failure does not block the other."""
        for idx_type, (label, _url) in INDEX_SOURCES.items():
            try:
                created, updated = self._fetch_index_type(idx_type)
                _logger.info(
                    "%s sync completed: %s created, %s updated",
                    label, created, updated,
                )
            except Exception:
                _logger.exception("%s sync failed", label)

    def action_fetch_tufe_indexes(self):
        """User-triggered fetch. Pulls every configured index type; raises
        the first UserError if any source fails."""
        try:
            totals = self._fetch_all_indexes()
        except UserError:
            raise
        except Exception as exc:
            raise UserError(_("Veri çekilirken hata oluştu:\n%s") % exc)
        lines = [
            _("%(label)s: %(c)s yeni, %(u)s güncellendi",
              label=INDEX_SOURCES[t][0], c=c, u=u)
            for t, (c, u) in totals.items()
        ]
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("İşlem Başarılı"),
                'message': '\n'.join(lines),
                'type': 'success',
                'sticky': False,
            },
        }
