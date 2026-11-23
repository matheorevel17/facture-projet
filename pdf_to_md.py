"""Télécharger les PDF S3 et produire des Markdown locaux, sans écrire sur S3."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
import pymupdf
import pytesseract
from PIL import Image


ROOT = Path(__file__).resolve().parent


def convert_pdf(content, filename, languages):
    sections = [f'# {filename}']
    methods = []
    with pymupdf.open(stream=content, filetype='pdf') as doc:
        if doc.needs_pass:
            raise ValueError('PDF protégé par mot de passe')
        if not len(doc):
            raise ValueError('PDF sans pages')
        for number, page in enumerate(doc, start=1):
            text = page.get_text('text', sort=True).strip()
            # Quelques caractères isolés (numéro de page, filigrane) ne suffisent pas.
            if sum(char.isalnum() for char in text) >= 40:
                method = 'texte'
            else:
                if not shutil.which('tesseract'):
                    raise RuntimeError('Tesseract absent : installer tesseract-ocr et ses langues fra/eng')
                pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csRGB, alpha=False)
                image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
                text = pytesseract.image_to_string(image, lang=languages, timeout=120).strip()
                method = 'ocr'
            if not text:
                raise ValueError(f'Page {number} : aucun texte détecté, vérification manuelle nécessaire')
            sections.append(f'## Page {number}\n\n{text}')
            methods.append(method)
    return '\n\n'.join(sections) + '\n', methods


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', default='', help='Préfixe S3 à parcourir (par défaut : tout le bucket)')
    parser.add_argument('--limit', type=int, help='Nombre maximal de PDF à traiter')
    parser.add_argument('--ocr-lang', default='fra+eng')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit doit être positif')
    load_dotenv(ROOT / '.env')
    required = ['S3_ENDPOINT_URL', 'S3_BUCKET', 'AWS_DEFAULT_REGION', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
    missing = [key for key in required if not os.getenv(key, '').strip()]
    if missing:
        print('Variables manquantes dans .env : ' + ', '.join(missing))
        return 1
    client = boto3.client(
        's3', endpoint_url=os.environ['S3_ENDPOINT_URL'],
        region_name=os.environ['AWS_DEFAULT_REGION'],
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        aws_session_token=os.getenv('AWS_SESSION_TOKEN') or None,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'},
                      connect_timeout=10, read_timeout=30, retries={'max_attempts': 2}),
    )
    output = ROOT / 'data' / 'markdown'
    output.mkdir(parents=True, exist_ok=True)
    report = []
    try:
        pages = client.get_paginator('list_objects_v2').paginate(
            Bucket=os.environ['S3_BUCKET'], Prefix=args.prefix)
        keys = (obj['Key'] for page in pages for obj in page.get('Contents', [])
                if obj['Key'].lower().endswith('.pdf'))
        for key in keys:
            identifier = hashlib.sha256(key.encode()).hexdigest()
            destination = output / f'{identifier}.md'
            row = {'id': identifier, 's3_key': key}
            try:
                response = client.get_object(Bucket=os.environ['S3_BUCKET'], Key=key)
                with response['Body'] as body:
                    content = body.read()
                md, methods = convert_pdf(content, Path(key).name, args.ocr_lang)
                temporary = destination.with_suffix('.md.tmp')
                temporary.write_text(md, encoding='utf-8')
                temporary.replace(destination)
                row.update(status='ok', markdown=str(destination.relative_to(ROOT)), pages=methods)
                print(f'OK {key} : {methods.count("texte")} page(s) texte, {methods.count("ocr")} OCR', flush=True)
            except Exception as exc:
                # Ne pas afficher les détails réseau pouvant contenir des identifiants.
                reason = type(exc).__name__
                if isinstance(exc, (ValueError, RuntimeError)):
                    reason += ': ' + str(exc)
                row.update(status='error', error=reason)
                print(f'ÉCHEC {key} : {reason}', flush=True)
            report.append(row)
            if args.limit and len(report) >= args.limit:
                break
    except (BotoCoreError, ClientError):
        print('Impossible de parcourir S3 : vérifie le réseau et les droits de lecture.')
        return 1
    (output / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    failures = sum(row['status'] == 'error' for row in report)
    print(f'{len(report) - failures}/{len(report)} PDF convertis. Résultats : {output}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
