import datetime
from datetime import timezone
from typing import cast

from cryptography import x509
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate
from cryptography.x509.oid import NameOID

from pt_repost.config import load_config


def create_ca() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=backend)
    public_key = private_key.public_key()
    builder = x509.CertificateBuilder()
    builder = (
        builder.subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "self signed CA")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "self signed CA")]))
        .not_valid_before(datetime.datetime.now(tz=timezone.utc))
        .not_valid_after(datetime.datetime(2099, 1, 1, tzinfo=timezone.utc))
        .serial_number(x509.random_serial_number())
        .public_key(public_key)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    )

    certificate = builder.sign(private_key=private_key, algorithm=hashes.SHA512(), backend=backend)

    return certificate, private_key


def sign_certificate_request(
    ca_cert: x509.Certificate, private_ca_key: RSAPrivateKey
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=backend)
    public_key = private_key.public_key()

    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pt-repost")]))
        .issuer_name(ca_cert.subject)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(tz=timezone.utc))
        .not_valid_after(datetime.datetime(2099, 1, 1, tzinfo=timezone.utc))
        .sign(private_ca_key, hashes.SHA512())
    )

    return cert, private_key


def main() -> None:
    cfg = load_config()

    ca_cert_file = cfg.data_dir.joinpath("pt-repost-ca.crt")
    ca_key_file = cfg.data_dir.joinpath("pt-repost-ca.key")

    if not (ca_key_file.exists() and ca_cert_file.exists()):
        ca_cert, ca_key = create_ca()

        with ca_key_file.open("wb") as f:
            f.write(
                ca_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        with ca_cert_file.open("wb") as f:
            f.write(ca_cert.public_bytes(encoding=serialization.Encoding.PEM))
    else:
        ca_key = cast(RSAPrivateKey, load_pem_private_key(ca_key_file.read_bytes(), None))
        ca_cert = load_pem_x509_certificate(ca_cert_file.read_bytes())

    server_cert, server_key = sign_certificate_request(ca_cert, ca_key)

    cfg.data_dir.joinpath("server.crt").write_bytes(
        server_cert.public_bytes(serialization.Encoding.PEM)
    )
    cfg.data_dir.joinpath("server.key").write_bytes(
        server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    client_cert_file = cfg.data_dir.joinpath("client.crt")
    client_key_file = cfg.data_dir.joinpath("client.key")

    client_cert, client_key = sign_certificate_request(ca_cert, ca_key)

    client_cert_file.write_bytes(client_cert.public_bytes(serialization.Encoding.PEM))

    client_key_file.write_bytes(
        client_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


if __name__ == "__main__":
    main()
