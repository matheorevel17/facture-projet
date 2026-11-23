"""Construire le Parquet Silver local à partir du manifeste de conversion PDF."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'data' / 'markdown' / 'manifest.json'
OUTPUT = ROOT / 'silver' / 'factures_md.parquet'
SCHEMA = pa.schema([
    pa.field('id', pa.string(), nullable=False),
    pa.field('filename', pa.string(), nullable=False),
    pa.field('md', pa.string(), nullable=False),
    pa.field('date_ingestion', pa.timestamp('us', tz='UTC'), nullable=False),
    pa.field('s3_key', pa.string(), nullable=False),
])


def build_table():
    entries = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if not entries:
        raise ValueError('Le manifeste est vide : exécute d’abord pdf_to_md.py.')
    failed = [entry for entry in entries if entry.get('status') != 'ok']
    if failed:
        raise ValueError(f'{len(failed)} PDF en erreur dans le manifeste. Corrige la conversion avant de créer Silver.')
    rows = []
    seen = set()
    ingested_at = datetime.now(timezone.utc)
    for entry in entries:
        identifier = entry['id']
        if identifier in seen:
            raise ValueError(f'Identifiant dupliqué : {identifier}')
        seen.add(identifier)
        path = (ROOT / entry['markdown']).resolve()
        if not path.is_relative_to(ROOT / 'data' / 'markdown'):
            raise ValueError('Chemin Markdown en dehors de data/markdown.')
        md = path.read_text(encoding='utf-8')
        if not md.strip():
            raise ValueError(f'Markdown vide : {path.name}')
        rows.append({
            'id': identifier,
            'filename': Path(entry['s3_key']).name,
            'md': md,
            # Horodatage de cette ingestion dans Silver, en UTC.
            'date_ingestion': ingested_at,
            's3_key': entry['s3_key'],
        })
    return pa.Table.from_pylist(rows, schema=SCHEMA)


def main():
    temporary = OUTPUT.with_suffix('.parquet.tmp')
    try:
        table = build_table()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, temporary, compression='snappy')
        # Vérifie aussi que chaque Markdown et son horodatage sont préservés.
        restored = pq.read_table(temporary)
        if not restored.equals(table):
            raise ValueError('Le contenu relu ne correspond pas aux données sources.')
        temporary.replace(OUTPUT)
    except (OSError, ValueError, KeyError, TypeError, pa.ArrowException) as exc:
        temporary.unlink(missing_ok=True)
        print(f'Échec de la création Silver : {exc}')
        return 1
    print(f'{table.num_rows} factures écrites dans {OUTPUT.relative_to(ROOT)}')
    print('Colonnes : ' + ', '.join(table.column_names))
    print('Vérification de relecture réussie : tous les Markdown sont conservés à l’identique.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
