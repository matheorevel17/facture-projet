"""Requêtes DuckDB partagées par le serveur MCP. Montants JSON en chaînes décimales."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import duckdb

GOLD = Path(__file__).resolve().parent / 'gold/factures.parquet'


def filters(fournisseur=None, debut=None, fin=None):
    start = date.fromisoformat(debut) if debut else None
    end = date.fromisoformat(fin) if fin else None
    if start and end and start > end:
        raise ValueError('La date de début doit précéder la date de fin.')
    clauses, values = [], []
    for value, clause in [(fournisseur, 'fournisseur = ?'), (start, 'date_facture >= ?'), (end, 'date_facture <= ?')]:
        if value is not None:
            clauses.append(clause)
            values.append(value)
    return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), values


def query(sql, params):
    if not GOLD.exists():
        raise FileNotFoundError('Gold absent : exécuter extract_features.py.')
    with duckdb.connect() as con:
        con.read_parquet(str(GOLD)).create_view('factures')
        result = con.execute(sql, params)
        names = [c[0] for c in result.description]
        return [{k: (str(v) if isinstance(v, (Decimal, date)) else v)
                 for k, v in zip(names, row)} for row in result.fetchall()]


def list_factures(fournisseur=None, debut=None, fin=None, limit=50, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError('limit doit être entre 1 et 100, offset positif ou nul.')
    where, values = filters(fournisseur, debut, fin)
    count = query('SELECT COUNT(*) AS nombre FROM factures' + where, values)[0]['nombre']
    rows = query('SELECT * FROM factures' + where + ' ORDER BY date_facture, id LIMIT ? OFFSET ?', values + [limit, offset])
    return {'nombre_total': count, 'factures': rows, 'offset': offset,
            'next_offset': offset + len(rows) if offset + len(rows) < count else None}


def total_factures(fournisseur=None, debut=None, fin=None):
    where, values = filters(fournisseur, debut, fin)
    rows = query('SELECT devise, COUNT(*) AS nombre, SUM(montant_ht) AS montant_ht, '
                 'SUM(montant_tva) AS montant_tva, SUM(montant_ttc) AS montant_ttc FROM factures'
                 + where + ' GROUP BY devise ORDER BY devise', values)
    return {'nombre': sum(row['nombre'] for row in rows), 'totaux_par_devise': rows,
            'base_periode': 'date_facture (émission), bornes incluses ; montants facturés, pas paiements constatés'}
