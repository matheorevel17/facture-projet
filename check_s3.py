"""Vérifier la lecture du bucket Hyperfluid sans modifier son contenu."""

import os
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv


def main():
    load_dotenv(Path(__file__).with_name('.env'))
    required = (
        'S3_ENDPOINT_URL', 'S3_BUCKET', 'AWS_DEFAULT_REGION',
        'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
    )
    missing = [name for name in required if not os.getenv(name, '').strip()]
    if missing:
        print('Renseigne ces variables dans .env : ' + ', '.join(missing))
        return 1

    client = boto3.client(
        's3',
        endpoint_url=os.environ['S3_ENDPOINT_URL'],
        region_name=os.environ['AWS_DEFAULT_REGION'],
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        aws_session_token=os.getenv('AWS_SESSION_TOKEN') or None,
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'},
            connect_timeout=10,
            read_timeout=20,
            retries={'max_attempts': 2},
        ),
    )
    try:
        result = client.list_objects_v2(Bucket=os.environ['S3_BUCKET'], MaxKeys=10)
    except ClientError as exc:
        code = exc.response.get('Error', {}).get('Code', 'Unknown')
        print(f'Accès S3 refusé ou requête invalide (code : {code}).')
        print('Vérifie les clés, la région et les droits sur le bucket.')
        return 1
    except BotoCoreError:
        print('Connexion S3 impossible. Vérifie le réseau et l’endpoint HTTPS.')
        return 1

    print(f"Connexion réussie : s3://{os.environ['S3_BUCKET']}")
    objects = result.get('Contents', [])
    if not objects:
        print('Le bucket est vide.')
    for obj in objects:
        print(f"  {obj['Key']} ({obj['Size']} octets)")
    print('Lecture de la liste vérifiée ; droits d’écriture non testés.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
