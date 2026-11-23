"""Rapprocher les fournisseurs par SIRET avec les en-têtes des PDF texte du corpus."""
import json
import re
from pathlib import Path
import pyarrow.parquet as pq
from extract_features import atomic_json, write_gold
ROOT = Path(__file__).resolve().parent


def normalize(rows, sources):
    manifest = json.loads((ROOT / 'data/markdown/manifest.json').read_text())
    direct = {r['id'] for r in manifest if r.get('pages') and all(p == 'texte' for p in r['pages'])}
    references = {}
    def identity(row):
        body = row['md'].split('## Page 1', 1)[-1].strip()
        header = body.split('Numéro de facture', 1)[0]
        match = re.search(r'\bSIRET\s*:\s*(\d{14})\b', header)
        return (match[1] if match else None), body.splitlines()[0]
    for row in sources:
        if row['id'] in direct:
            siret, name = identity(row)
            if siret:
                references.setdefault(siret, set()).add(name)
    sources_by_id = {r['id']: r for r in sources}
    changes = []
    for row in rows:
        siret, _ = identity(sources_by_id[row['id']])
        names = references.get(siret, set())
        if len(names) != 1:
            raise ValueError(f'Fournisseur ambigu ou sans référence texte : {row["filename"]}')
        name = next(iter(names))
        if row['fournisseur'] != name:
            changes.append({'id': row['id'], 'filename': row['filename'], 'siret': siret,
                            'before': row['fournisseur'], 'after': name})
            row['fournisseur'] = name
    return changes


def main():
    path = ROOT / 'gold/factures.parquet'
    rows = pq.read_table(path).to_pylist()
    sources = pq.read_table(ROOT / 'silver/factures_md.parquet').to_pylist()
    changes = normalize(rows, sources)
    if changes:
        atomic_json(ROOT / 'gold/supplier_corrections.json', changes)
        write_gold(rows, path)
    print(f'{len(changes)} fournisseur(s) corrigé(s) par SIRET ; {len(rows)} factures.')

if __name__ == '__main__':
    main()
