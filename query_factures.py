"""Interroger le Parquet Gold avec DuckDB, sans charger le fichier dans pandas."""

import argparse
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fournisseur', help='Nom exact du fournisseur')
    parser.add_argument('--debut', type=date.fromisoformat)
    parser.add_argument('--fin', type=date.fromisoformat)
    args = parser.parse_args()
    if args.debut and args.fin and args.debut > args.fin:
        parser.error('--debut doit précéder --fin')
    path = ROOT / 'gold' / 'factures.parquet'
    if not path.exists():
        print('Gold absent. Termine d’abord : python extract_features.py')
        return 1
    clauses, params = [], []
    for value, clause in [(args.fournisseur, 'fournisseur = ?'),
                          (args.debut, 'date_facture >= ?'), (args.fin, 'date_facture <= ?')]:
        if value is not None:
            clauses.append(clause)
            params.append(value)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    with duckdb.connect() as con:
        con.read_parquet(str(path)).create_view('factures')
        queries = [
            ('Nombre de factures', 'SELECT COUNT(*) AS nombre FROM factures' + where),
            ('Totaux par devise', 'SELECT devise, SUM(montant_ht) AS total_ht, SUM(montant_tva) AS total_tva, SUM(montant_ttc) AS total_ttc FROM factures' + where + ' GROUP BY devise ORDER BY devise'),
            ('Par fournisseur', 'SELECT fournisseur, devise, COUNT(*) AS nombre, SUM(montant_ttc) AS total_ttc FROM factures' + where + ' GROUP BY fournisseur, devise ORDER BY fournisseur, devise'),
            ('Par mois d’émission', "SELECT strftime(date_facture, '%Y-%m') AS mois, devise, SUM(montant_ttc) AS total_ttc FROM factures" + where + ' GROUP BY mois, devise ORDER BY mois, devise'),
        ]
        for title, sql in queries:
            print('\n' + title)
            result = con.execute(sql, params)
            print(' | '.join(col[0] for col in result.description))
            for row in result.fetchall():
                print(' | '.join(str(value) for value in row))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
