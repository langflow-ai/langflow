"""Unit tests for mTLS functionality in APIRequestComponent."""

import os
import ssl
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from lfx.components.data.api_request import APIRequestComponent


class TestAPIRequestComponentMTLS:
    """Test cases for mTLS functionality in APIRequestComponent."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = APIRequestComponent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Initialize required attributes
        self.component.set_attributes(
            {
                "url_input": "https://api.example.com/endpoint",
                "method": "GET",
                "headers": [],
                "body": [],
                "timeout": 30,
                "follow_redirects": True,
                "save_to_file": False,
                "include_httpx_metadata": False,
                "mode": "URL",
                "query_params": None,
                "curl_input": "",
                # mTLS attributes
                "use_mtls": False,
                "cert_source": "File Path",
                "client_cert_file": None,
                "client_key_file": None,
                "key_password": None,
                "cert_env_var": None,
                "key_env_var": None,
                "verify_server_cert": True,
                "ca_bundle_file": None,
            }
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    # Test 1: mTLS disabled by default
    def test_mtls_disabled_by_default(self):
        """Test that mTLS is disabled by default and returns None."""
        ssl_context = self.component.build_ssl_context()
        assert ssl_context is None

    # Test 2: Validation passes when mTLS is disabled
    def test_validate_mtls_config_disabled(self):
        """Test that validation passes when mTLS is disabled."""
        self.component.use_mtls = False
        # Should not raise any exception
        self.component.validate_mtls_config()

    # Test 3: Validation fails when mTLS enabled but no cert file
    def test_validate_mtls_config_no_cert_file(self):
        """Test that validation fails when mTLS is enabled but no certificate provided."""
        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = None

        with pytest.raises(ValueError, match="mTLS enabled but no client certificate file provided"):
            self.component.validate_mtls_config()

    # Test 4: Validation fails when using env vars but no env var name
    def test_validate_mtls_config_no_env_var_name(self):
        """Test that validation fails when using env vars but no variable name provided."""
        self.component.use_mtls = True
        self.component.cert_source = "Environment Variable"
        self.component.cert_env_var = None

        with pytest.raises(
            ValueError, match="mTLS enabled with env vars but no certificate environment variable name provided"
        ):
            self.component.validate_mtls_config()

    # Test 5: Build SSL context with local certificate file (cert + key combined)
    def test_build_ssl_context_local_combined_cert(self):
        """Test building SSL context with combined certificate and key in one file."""
        # Create a dummy combined cert file
        cert_file = self.temp_path / "client.pem"
        cert_file.write_text(  # pragma: allowlist secret
            "-----BEGIN CERTIFICATE-----\nDUMMY_CERT\n-----END CERTIFICATE-----\n"
            "-----BEGIN PRIVATE KEY-----\nDUMMY_KEY\n-----END PRIVATE KEY-----\n"  # pragma: allowlist secret
        )

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.client_key_file = None

        # Mock ssl.create_default_context to avoid actual SSL operations
        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_ssl.return_value = mock_context

            ssl_context = self.component.build_ssl_context()

            # Verify SSL context was created
            assert ssl_context is not None
            mock_ssl.assert_called_once()
            mock_context.load_cert_chain.assert_called_once_with(certfile=str(cert_file), keyfile=None, password=None)

    # Test 6: Build SSL context with separate cert and key files
    def test_build_ssl_context_local_separate_files(self):
        """Test building SSL context with separate certificate and key files."""
        # Create dummy cert and key files
        cert_file = self.temp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\nDUMMY_CERT\n-----END CERTIFICATE-----\n")

        key_file = self.temp_path / "client.key"
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\nDUMMY_KEY\n-----END PRIVATE KEY-----\n"  # pragma: allowlist secret
        )

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.client_key_file = str(key_file)

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_ssl.return_value = mock_context

            ssl_context = self.component.build_ssl_context()

            assert ssl_context is not None
            mock_context.load_cert_chain.assert_called_once_with(
                certfile=str(cert_file), keyfile=str(key_file), password=None
            )

    # Test 7: Build SSL context with encrypted key (password)
    def test_build_ssl_context_with_password(self):
        """Test building SSL context with encrypted private key."""
        cert_file = self.temp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\nDUMMY_CERT\n-----END CERTIFICATE-----\n")

        key_file = self.temp_path / "client.key"
        key_file.write_text("-----BEGIN ENCRYPTED PRIVATE KEY-----\nDUMMY_KEY\n-----END ENCRYPTED PRIVATE KEY-----\n")

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.client_key_file = str(key_file)
        self.component.key_password = "test_password"  # pragma: allowlist secret

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_ssl.return_value = mock_context

            ssl_context = self.component.build_ssl_context()

            assert ssl_context is not None
            mock_context.load_cert_chain.assert_called_once_with(
                certfile=str(cert_file), keyfile=str(key_file), password=b"test_password"
            )

    # Test 8: Certificate file not found
    def test_build_ssl_context_cert_not_found(self):
        """Test that FileNotFoundError is raised when certificate file doesn't exist."""
        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = "/nonexistent/path/cert.pem"

        with pytest.raises(FileNotFoundError, match="Certificate file not found"):
            self.component.build_ssl_context()

    # Test 9: Key file not found
    def test_build_ssl_context_key_not_found(self):
        """Test that FileNotFoundError is raised when key file doesn't exist."""
        cert_file = self.temp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\nDUMMY_CERT\n-----END CERTIFICATE-----\n")

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.client_key_file = "/nonexistent/path/key.pem"

        with pytest.raises(FileNotFoundError, match="Private key file not found"):
            self.component.build_ssl_context()

    # Test 10: Environment variable with valid paths
    def test_build_ssl_context_env_var_success(self):
        """Test building SSL context using environment variables."""
        cert_file = self.temp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\nDUMMY_CERT\n-----END CERTIFICATE-----\n")

        key_file = self.temp_path / "client.key"
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\nDUMMY_KEY\n-----END PRIVATE KEY-----\n"  # pragma: allowlist secret
        )

        # Set environment variables
        os.environ["TEST_CLIENT_CERT"] = str(cert_file)
        os.environ["TEST_CLIENT_KEY"] = str(key_file)

        try:
            self.component.use_mtls = True
            self.component.cert_source = "Environment Variable"
            self.component.cert_env_var = "TEST_CLIENT_CERT"
            self.component.key_env_var = "TEST_CLIENT_KEY"

            with patch("ssl.create_default_context") as mock_ssl:
                mock_context = Mock(spec=ssl.SSLContext)
                mock_ssl.return_value = mock_context

                ssl_context = self.component.build_ssl_context()

                assert ssl_context is not None
                mock_context.load_cert_chain.assert_called_once_with(
                    certfile=str(cert_file), keyfile=str(key_file), password=None
                )
        finally:
            # Clean up environment variables
            os.environ.pop("TEST_CLIENT_CERT", None)
            os.environ.pop("TEST_CLIENT_KEY", None)

    # Test 11: Environment variable not found
    def test_build_ssl_context_env_var_not_found(self):
        """Test that error is raised when environment variable doesn't exist."""
        self.component.use_mtls = True
        self.component.cert_source = "Environment Variable"
        self.component.cert_env_var = "NONEXISTENT_ENV_VAR"

        with pytest.raises(ValueError, match="Environment variable 'NONEXISTENT_ENV_VAR' not found or empty"):
            self.component.build_ssl_context()

    # Test 12: Verify server cert disabled
    def test_build_ssl_context_verify_server_disabled(self):
        """Test that server verification is disabled when verify_server_cert=False."""
        cert_file = self.temp_path / "client.pem"
        cert_file.write_text(  # pragma: allowlist secret
            "-----BEGIN CERTIFICATE-----\nDUMMY_CERT\n-----END CERTIFICATE-----\n"
            "-----BEGIN PRIVATE KEY-----\nDUMMY_KEY\n-----END PRIVATE KEY-----\n"  # pragma: allowlist secret
        )

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.verify_server_cert = False

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_ssl.return_value = mock_context

            ssl_context = self.component.build_ssl_context()

            assert ssl_context is not None
            # Verify that hostname checking and cert verification were disabled
            assert mock_context.check_hostname is False
            assert mock_context.verify_mode == ssl.CERT_NONE

    # Test 13: Custom CA bundle
    def test_build_ssl_context_custom_ca_bundle(self):
        """Test loading custom CA bundle for server verification."""
        cert_file = self.temp_path / "client.pem"
        cert_file.write_text(  # pragma: allowlist secret
            "-----BEGIN CERTIFICATE-----\nDUMMY_CERT\n-----END CERTIFICATE-----\n"
            "-----BEGIN PRIVATE KEY-----\nDUMMY_KEY\n-----END PRIVATE KEY-----\n"  # pragma: allowlist secret
        )

        ca_bundle = self.temp_path / "ca-bundle.pem"
        ca_bundle.write_text("-----BEGIN CERTIFICATE-----\nDUMMY_CA\n-----END CERTIFICATE-----\n")

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.verify_server_cert = True
        self.component.ca_bundle_file = str(ca_bundle)

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_ssl.return_value = mock_context

            ssl_context = self.component.build_ssl_context()

            assert ssl_context is not None
            mock_context.load_verify_locations.assert_called_once_with(cafile=str(ca_bundle))

    # Test 14: SSL error handling
    def test_build_ssl_context_ssl_error(self):
        """Test that SSL errors are properly handled and wrapped."""
        cert_file = self.temp_path / "client.pem"
        cert_file.write_text("INVALID CERTIFICATE DATA")

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_context.load_cert_chain.side_effect = ssl.SSLError("Invalid certificate format")
            mock_ssl.return_value = mock_context

            with pytest.raises(ValueError, match="SSL error while configuring mTLS"):
                self.component.build_ssl_context()

    # Test 15: Validation warning for disabled server verification
    def test_validate_mtls_config_warns_insecure(self):
        """Test that a warning is logged when server verification is disabled."""
        cert_file = self.temp_path / "client.pem"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\nDUMMY\n-----END CERTIFICATE-----\n")

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.verify_server_cert = False

        # Mock the log method to capture warnings
        with patch.object(self.component, "log") as mock_log:
            self.component.validate_mtls_config()
            mock_log.assert_called_once_with("WARNING: Server certificate verification is disabled. This is insecure!")


class TestAPIRequestComponentMTLSIntegration:
    """Integration tests for mTLS using real SSL contexts and certificates."""

    def setup_method(self):
        """Set up test fixtures with real certificate generation."""
        self.component = APIRequestComponent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Initialize required attributes
        self.component.set_attributes(
            {
                "url_input": "https://api.example.com/endpoint",
                "method": "GET",
                "headers": [],
                "body": [],
                "timeout": 30,
                "follow_redirects": True,
                "save_to_file": False,
                "include_httpx_metadata": False,
                "mode": "URL",
                "query_params": None,
                "curl_input": "",
                # mTLS attributes
                "use_mtls": False,
                "cert_source": "File Path",
                "client_cert_file": None,
                "client_key_file": None,
                "key_password": None,
                "cert_env_var": None,
                "key_env_var": None,
                "verify_server_cert": True,
                "ca_bundle_file": None,
            }
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def _generate_self_signed_cert(self, cert_path: Path, key_path: Path | None = None):
        """Generate a self-signed certificate and key for testing.

        Args:
            cert_path: Path where certificate will be saved
            key_path: Optional path for separate key file. If None, key is included in cert file.
        """
        import datetime

        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        # Generate private key
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

        # Generate certificate
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "TestState"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "TestCity"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TestOrg"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ]
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
            .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                critical=False,
            )
            .sign(private_key, hashes.SHA256(), default_backend())
        )

        # Write certificate
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        if key_path:
            # Write separate files
            cert_path.write_bytes(cert_pem)
            key_path.write_bytes(key_pem)
        else:
            # Write combined file
            cert_path.write_bytes(cert_pem + key_pem)

    def test_build_ssl_context_with_real_combined_cert(self):
        """Integration test: Build SSL context with real self-signed combined certificate."""
        cert_file = self.temp_path / "real_client.pem"
        self._generate_self_signed_cert(cert_file)

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.client_key_file = None

        # Build real SSL context without mocks
        ssl_context = self.component.build_ssl_context()

        # Verify SSL context is real and properly configured
        assert ssl_context is not None
        assert isinstance(ssl_context, ssl.SSLContext)
        assert ssl_context.check_hostname is True
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED

    def test_build_ssl_context_with_real_separate_files(self):
        """Integration test: Build SSL context with real separate cert and key files."""
        cert_file = self.temp_path / "real_client.crt"
        key_file = self.temp_path / "real_client.key"
        self._generate_self_signed_cert(cert_file, key_file)

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.client_key_file = str(key_file)

        # Build real SSL context without mocks
        ssl_context = self.component.build_ssl_context()

        # Verify SSL context is real and properly configured
        assert ssl_context is not None
        assert isinstance(ssl_context, ssl.SSLContext)
        assert ssl_context.check_hostname is True
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED

    def test_build_ssl_context_with_verify_disabled(self):
        """Integration test: Build SSL context with server verification disabled."""
        cert_file = self.temp_path / "real_client.pem"
        self._generate_self_signed_cert(cert_file)

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.verify_server_cert = False

        # Build real SSL context without mocks
        ssl_context = self.component.build_ssl_context()

        # Verify SSL context has verification disabled
        assert ssl_context is not None
        assert isinstance(ssl_context, ssl.SSLContext)
        assert ssl_context.check_hostname is False
        assert ssl_context.verify_mode == ssl.CERT_NONE

    def test_build_ssl_context_with_real_ca_bundle(self):
        """Integration test: Build SSL context with custom CA bundle."""
        cert_file = self.temp_path / "real_client.pem"
        ca_bundle = self.temp_path / "real_ca_bundle.pem"

        # Generate client cert and CA bundle (self-signed)
        self._generate_self_signed_cert(cert_file)
        self._generate_self_signed_cert(ca_bundle)

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.verify_server_cert = True
        self.component.ca_bundle_file = str(ca_bundle)

        # Build real SSL context without mocks
        ssl_context = self.component.build_ssl_context()

        # Verify SSL context is properly configured
        assert ssl_context is not None
        assert isinstance(ssl_context, ssl.SSLContext)
        assert ssl_context.check_hostname is True
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED

    def test_build_ssl_context_with_invalid_cert_format(self):
        """Integration test: Verify that invalid certificate format raises SSL error."""
        cert_file = self.temp_path / "invalid_cert.pem"
        cert_file.write_text("INVALID CERTIFICATE DATA\nNOT A REAL CERT")

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)

        # Should raise ValueError wrapping SSLError for invalid cert
        with pytest.raises(ValueError, match="SSL error while configuring mTLS"):
            self.component.build_ssl_context()


class TestAPIRequestComponentMTLSEdgeCases:
    """Edge case tests for mTLS functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = APIRequestComponent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Initialize required attributes
        self.component.set_attributes(
            {
                "url_input": "https://api.example.com/endpoint",
                "method": "GET",
                "headers": [],
                "body": [],
                "timeout": 30,
                "follow_redirects": True,
                "save_to_file": False,
                "include_httpx_metadata": False,
                "mode": "URL",
                "query_params": None,
                "curl_input": "",
                # mTLS attributes
                "use_mtls": False,
                "cert_source": "File Path",
                "client_cert_file": None,
                "client_key_file": None,
                "key_password": None,
                "cert_env_var": None,
                "key_env_var": None,
                "verify_server_cert": True,
                "ca_bundle_file": None,
            }
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_certificate_with_special_characters_in_path(self):
        """Test handling of certificate paths with special characters."""
        # Create a directory with spaces and special chars
        special_dir = self.temp_path / "my certs (test)"
        special_dir.mkdir()

        cert_file = special_dir / "client cert.pem"
        cert_file.write_text(  # pragma: allowlist secret
            "-----BEGIN CERTIFICATE-----\nDUMMY_CERT\n-----END CERTIFICATE-----\n"
            "-----BEGIN PRIVATE KEY-----\nDUMMY_KEY\n-----END PRIVATE KEY-----\n"  # pragma: allowlist secret
        )

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_ssl.return_value = mock_context

            ssl_context = self.component.build_ssl_context()
            assert ssl_context is not None

    def test_empty_certificate_file(self):
        """Test behavior with empty certificate file."""
        cert_file = self.temp_path / "empty.pem"
        cert_file.write_text("")

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_context.load_cert_chain.side_effect = ssl.SSLError("PEM lib")
            mock_ssl.return_value = mock_context

            with pytest.raises(ValueError, match="SSL error while configuring mTLS"):
                self.component.build_ssl_context()

    def test_certificate_path_is_directory_not_file(self):
        """Test error handling when certificate path points to a directory."""
        cert_dir = self.temp_path / "cert_dir"
        cert_dir.mkdir()

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_dir)

        # Directory exists but is not a file - should fail on SSL load
        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_context.load_cert_chain.side_effect = ssl.SSLError("Is a directory")
            mock_ssl.return_value = mock_context

            with pytest.raises(ValueError, match="SSL error while configuring mTLS"):
                self.component.build_ssl_context()

    def test_mismatched_certificate_and_key(self):
        """Test error when certificate and private key don't match."""
        cert_file = self.temp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\nCERT_DATA_1\n-----END CERTIFICATE-----\n")

        key_file = self.temp_path / "client.key"
        key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\nKEY_DATA_2\n-----END PRIVATE KEY-----\n"  # pragma: allowlist secret
        )

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.client_key_file = str(key_file)

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_context.load_cert_chain.side_effect = ssl.SSLError("key values mismatch")
            mock_ssl.return_value = mock_context

            with pytest.raises(ValueError, match="SSL error while configuring mTLS"):
                self.component.build_ssl_context()

    def test_wrong_password_for_encrypted_key(self):
        """Test error when wrong password is provided for encrypted key."""
        cert_file = self.temp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\nDUMMY\n-----END CERTIFICATE-----\n")

        key_file = self.temp_path / "encrypted.key"
        key_file.write_text("-----BEGIN ENCRYPTED PRIVATE KEY-----\nDUMMY\n-----END ENCRYPTED PRIVATE KEY-----\n")

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.client_key_file = str(key_file)
        self.component.key_password = "wrong_password"  # pragma: allowlist secret

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_context.load_cert_chain.side_effect = ssl.SSLError("bad decrypt")
            mock_ssl.return_value = mock_context

            with pytest.raises(ValueError, match="SSL error while configuring mTLS"):
                self.component.build_ssl_context()

    def test_nonexistent_ca_bundle_file(self):
        """Test warning when CA bundle file doesn't exist."""
        cert_file = self.temp_path / "client.pem"
        cert_file.write_text(  # pragma: allowlist secret
            "-----BEGIN CERTIFICATE-----\nDUMMY\n-----END CERTIFICATE-----\n"
            "-----BEGIN PRIVATE KEY-----\nDUMMY\n-----END PRIVATE KEY-----\n"  # pragma: allowlist secret
        )

        self.component.use_mtls = True
        self.component.cert_source = "File Path"
        self.component.client_cert_file = str(cert_file)
        self.component.verify_server_cert = True
        self.component.ca_bundle_file = "/nonexistent/ca-bundle.pem"

        with patch("ssl.create_default_context") as mock_ssl:
            mock_context = Mock(spec=ssl.SSLContext)
            mock_ssl.return_value = mock_context

            with patch.object(self.component, "log") as mock_log:
                ssl_context = self.component.build_ssl_context()
                assert ssl_context is not None
                # Should log warning about missing CA bundle
                mock_log.assert_any_call("WARNING: CA bundle file not found: /nonexistent/ca-bundle.pem")

    def test_environment_variable_with_empty_string_value(self):
        """Test error when environment variable is set but empty."""
        os.environ["EMPTY_CERT_PATH"] = ""

        try:
            self.component.use_mtls = True
            self.component.cert_source = "Environment Variable"
            self.component.cert_env_var = "EMPTY_CERT_PATH"

            with pytest.raises(ValueError, match="Environment variable 'EMPTY_CERT_PATH' not found or empty"):
                self.component.build_ssl_context()
        finally:
            os.environ.pop("EMPTY_CERT_PATH", None)

    def test_environment_variable_with_whitespace_value(self):
        """Test error when environment variable contains only whitespace."""
        os.environ["WHITESPACE_CERT_PATH"] = "   "

        try:
            self.component.use_mtls = True
            self.component.cert_source = "Environment Variable"
            self.component.cert_env_var = "WHITESPACE_CERT_PATH"

            # Path with whitespace doesn't exist
            with pytest.raises(FileNotFoundError, match="Certificate file not found"):
                self.component.build_ssl_context()
        finally:
            os.environ.pop("WHITESPACE_CERT_PATH", None)

    def test_cert_source_secrets_manager_not_implemented(self):
        """Test that Secrets Manager source is handled (future implementation)."""
        self.component.use_mtls = True
        self.component.cert_source = "Secrets Manager"
        self.component.client_cert_file = None

        # Currently, Secrets Manager path does nothing - cert_path will be None
        with pytest.raises(FileNotFoundError, match="Certificate file not found"):
            self.component.build_ssl_context()

    def test_validation_with_none_cert_source(self):
        """Test validation when cert_source attribute is not set."""
        # Remove cert_source to test getattr default
        if hasattr(self.component, "cert_source"):
            delattr(self.component, "cert_source")

        self.component.use_mtls = True
        # Should default to "File Path"
        with pytest.raises(ValueError, match="mTLS enabled but no client certificate file provided"):
            self.component.validate_mtls_config()
