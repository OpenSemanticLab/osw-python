from io import BytesIO, StringIO
from typing import IO, Any, Dict, Optional

import boto3

from osw.auth import CredentialManager
from osw.controller.file.remote import RemoteFileController
from osw.core import model


class S3FileController(model.S3File, RemoteFileController):
    protocol: Optional[str]
    domain: Optional[str]
    bucket: Optional[str]
    key: Optional[str]

    cm: CredentialManager
    s3_client: Optional[Any]
    s3_resource: Optional[Any]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._parse_url()
        creds: CredentialManager.UserPwdCredential = self.cm.get_credential(
            CredentialManager.CredentialConfig(iri=self.domain)
        )

        self.s3_resource = boto3.resource(
            "s3",
            aws_access_key_id=creds.username,
            aws_secret_access_key=creds.password,
            aws_session_token=None,  # replace this with token if necessary
            endpoint_url=self.protocol + "//" + self.domain,
            config=boto3.session.Config(signature_version="s3v4"),
            # verify=False
        )
        self.s3_client = self.s3_resource.meta.client

    def get(self) -> IO:
        response = self.s3_resource.Object(bucket_name=self.bucket, key=self.key).get()
        return response["Body"]

    # def get_to(self, other: "FileController"):
    #    response = self.s3_resource.Object(bucket_name=self.bucket, key=self.key).get()
    #    with response['Body'] as file:
    #        other.put(file)

    def put(self, file: IO, **kwargs: Dict[str, Any]):
        if isinstance(file, StringIO):
            file = BytesIO(file.getvalue().encode())
            # file.seek(0)
        self.s3_client.upload_fileobj(file, self.bucket, self.key)

    # def put_from(self, other: FileController):
    #    pass

    def delete(self):
        self.s3_client.delete_object(Bucket=self.bucket, Key=self.key)

    def _parse_url(self):
        self.protocol = self.url.split("//")[0]
        self.domain = self.url.split("//")[1].split("/")[0]
        self.bucket = self.url.split("//")[1].split("/")[1]
        self.key = self.url.replace(
            self.protocol + "//" + self.domain + "/" + self.bucket + "/", ""
        )
