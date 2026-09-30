#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Descarga telegram_messages.json desde S3 (boto3 / URL pública). Sin aws-cli."""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

BUCKET = os.environ.get("S3_BUCKET", "monitoria-data")
DEFAULT_KEY = os.environ.get("DATASTORE_S3_JSON_KEY", "telegram_messages.json")
PUBLIC_URL = os.environ.get(
    "S3_PUBLIC_JSON_URL",
    f"https://{BUCKET}.s3.{os.environ.get('AWS_REGION', 'eu-north-1')}.amazonaws.com/{DEFAULT_KEY}",
)


def download_via_boto3(dest: str, key: str) -> bool:
    try:
        import boto3

        region = os.environ.get("AWS_REGION", "eu-north-1")
        client = boto3.client("s3", region_name=region)
        print(f"Descargando s3://{BUCKET}/{key} → {dest}")
        client.download_file(BUCKET, key, dest)
        return True
    except Exception as exc:
        print(f"boto3: {exc}")
        return False


def download_via_http(dest: str, url: str) -> bool:
    try:
        import requests

        print(f"Descargando {url} → {dest}")
        response = requests.get(url, timeout=300)
        if response.status_code != 200:
            print(f"HTTP {response.status_code}")
            return False
        with open(dest, "wb") as fh:
            fh.write(response.content)
        return True
    except Exception as exc:
        print(f"HTTP: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Descargar dataset Telegram desde S3")
    parser.add_argument(
        "-o",
        "--output",
        default="/tmp/telegram_messages.json",
        help="Ruta local de salida",
    )
    parser.add_argument("--key", default=DEFAULT_KEY, help="Clave S3 del JSON")
    args = parser.parse_args()

    if download_via_boto3(args.output, args.key):
        size_mb = os.path.getsize(args.output) / (1024 * 1024)
        print(f"OK ({size_mb:.1f} MB)")
        return

    if download_via_http(args.output, PUBLIC_URL):
        size_mb = os.path.getsize(args.output) / (1024 * 1024)
        print(f"OK vía URL pública ({size_mb:.1f} MB)")
        return

    print("ERROR: no se pudo descargar. Instala awscli o configura credenciales/IAM en la EC2.")
    sys.exit(1)


if __name__ == "__main__":
    main()
