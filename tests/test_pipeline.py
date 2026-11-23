import unittest
from decimal import Decimal
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
import pyarrow as pa
import pyarrow.parquet as pq
import invoice_store as store
from extract_features import Facture
from pydantic import ValidationError

class Queries(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        path = Path(self.directory.name) / 'gold.parquet'
        rows = [dict(id=str(i), fournisseur=name, date_facture=__import__('datetime').date(2026, 11, 1),
                     devise=currency, montant_ht=Decimal('10.00'), montant_tva=Decimal('2.00'),
                     montant_ttc=Decimal('12.00')) for i, name, currency in
                [(1, "O'Brien", 'EUR'), (2, 'Autre', 'EUR'), (3, 'Autre', 'USD')]]
        pq.write_table(pa.Table.from_pylist(rows), path)
        self.patcher = patch.object(store, 'GOLD', path)
        self.patcher.start()
    def tearDown(self):
        self.patcher.stop()
        self.directory.cleanup()
    def test_currencies_and_pagination(self):
        result = store.total_factures()
        self.assertEqual(result['nombre'], 3)
        self.assertEqual([Decimal(r['montant_ttc']) for r in result['totaux_par_devise']], [Decimal(24), Decimal(12)])
        self.assertEqual(store.list_factures(limit=2)['next_offset'], 2)
        self.assertEqual(len(store.list_factures(limit=2, offset=2)['factures']), 1)
    def test_filters_and_injection(self):
        self.assertEqual(store.total_factures("O'Brien", '2026-11-01', '2026-11-01')['nombre'], 1)
        self.assertEqual(store.total_factures("' OR 1=1 --")['nombre'], 0)
        self.assertEqual(store.total_factures(debut='2027-01-01')['totaux_par_devise'], [])
        with self.assertRaises(ValueError):
            store.total_factures(debut='2026-12-01', fin='2026-01-01')
    def test_decimal_validation(self):
        values = dict(numero_facture='X', date_facture='2026-11-01', fournisseur='A', client=None,
                      date_echeance=None, montant_ht='1 000,00', montant_tva='200,00',
                      montant_ttc='1\u202f200,00', devise='EUR', categorie=None, statut=None)
        self.assertEqual(Facture(**values).montant_ttc, Decimal('1200'))
        with self.assertRaises(ValidationError):
            Facture(**(values | {'montant_ttc': '999,00'}))

if __name__ == '__main__':
    unittest.main()
