import asyncio
from urllib.parse import urlparse

import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config.settings import (
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
    AWS_REGION, S3_BUCKET_NAME
)
from db.mongo import MongoDBManager
from db.mysql import MySQLManager


class DecryptionService:
    def __init__(self, mysql: MySQLManager, mongo: MongoDBManager):
        self.mysql = mysql
        self.mongo = mongo
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

    def _download_and_decrypt(self, key: str, dek: bytes, iv: bytes) -> bytes:
        """S3 다운로드 + AES-GCM 복호화 (동기, 워커 스레드에서 실행)"""
        resp = self.s3.get_object(Bucket=S3_BUCKET_NAME, Key=key)
        ciphertext = resp['Body'].read()
        return AESGCM(dek).decrypt(iv, ciphertext, None)

    async def decrypt(self, contract_id: int) -> bytes:
        info = await self.mysql.get_contract_file_info(contract_id)
        if not info:
            raise ValueError(f"ContractFile not found: {contract_id}")

        file_id = info['id']
        pdf_url = info['file_address']
        share_a = info['encrypted_data_key']
        iv = info['iv']

        share_b = await self.mongo.get_share_b(file_id)
        if not share_b:
            raise ValueError(f"shareB not found for fileId: {file_id}")

        # 복원된 DEK
        dek = bytes(a ^ b for a, b in zip(share_a, share_b))

        # URL에서 S3 Key만 분리
        parsed = urlparse(pdf_url)
        key = parsed.path.lstrip("/")

        # S3 다운로드와 복호화는 블로킹 작업이라 워커 스레드로 넘긴다
        return await asyncio.to_thread(self._download_and_decrypt, key, dek, iv)
