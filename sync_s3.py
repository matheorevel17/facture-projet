"""Envoyer Silver et Gold sur Hyperfluid et vérifier les octets téléchargés."""
import hashlib
import os
from pathlib import Path
import boto3
from botocore.config import Config
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


def main():
    load_dotenv(ROOT / '.env')
    client = boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT_URL'],
                         region_name=os.environ['AWS_DEFAULT_REGION'],
                         aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
                         aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                         aws_session_token=os.getenv('AWS_SESSION_TOKEN') or None,
                         config=Config(signature_version='s3v4', s3={'addressing_style': 'path'},
                                       connect_timeout=10, read_timeout=30))
    bucket = os.environ['S3_BUCKET']
    paths = ['silver/factures_md.parquet', 'gold/factures.parquet']
    contents = {key: (ROOT / key).read_bytes() for key in paths}
    for key, content in contents.items():
        digest = hashlib.sha256(content).hexdigest()
        client.put_object(Bucket=bucket, Key=key, Body=content,
                          ContentType='application/vnd.apache.parquet', Metadata={'sha256': digest})
        response = client.get_object(Bucket=bucket, Key=key)
        with response['Body'] as stream:
            actual = hashlib.sha256(stream.read()).hexdigest()
        if actual != digest:
            raise ValueError(f'Verification SHA-256 échouée : {key}')
        print(f'Envoyé et vérifié : s3://{bucket}/{key}')

if __name__ == '__main__':
    main()
