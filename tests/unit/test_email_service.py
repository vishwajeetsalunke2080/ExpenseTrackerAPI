"""Unit tests for EmailService.

Tests email sending functionality with mocked SMTP server, email template
rendering, and error handling for failed email delivery.

Requirements: 1.5, 5.2, 7.2, 10.2
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import smtplib

from app.services.email_service import EmailService


@pytest.fixture
def email_service():
    """Create an EmailService instance for testing."""
    with patch('app.services.email_service.settings') as mock_settings:
        mock_settings.smtp_host = "smtp.test.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_username = "test@example.com"
        mock_settings.smtp_password = "test_password"
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.smtp_from_name = "Test App"
        
        service = EmailService()
        return service


class TestEmailServiceInitialization:
    """Test EmailService initialization."""
    
    def test_initialization_loads_smtp_config(self, email_service):
        """Test that EmailService loads SMTP configuration from settings."""
        assert email_service.smtp_host == "smtp.test.com"
        assert email_service.smtp_port == 587
        assert email_service.smtp_username == "test@example.com"
        assert email_service.smtp_password == "test_password"
        assert email_service.from_email == "noreply@example.com"
        assert email_service.from_name == "Test App"


class TestSendVerificationEmail:
    """Test send_verification_email method."""
    
    @pytest.mark.asyncio
    async def test_send_verification_email_success(self, email_service):
        """Test successful verification email sending with mocked SMTP."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_verification_email(
                email="user@example.com",
                token="test_token_123",
                base_url="http://localhost:8000"
            )
            
            # Verify SMTP connection was established
            mock_smtp.assert_called_once_with("smtp.test.com", 587)
            
            # Verify starttls was called
            mock_server.starttls.assert_called_once()
            
            # Verify login was called with credentials
            mock_server.login.assert_called_once_with(
                "test@example.com",
                "test_password"
            )
            
            # Verify send_message was called
            mock_server.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verification_email_contains_correct_link(self, email_service):
        """Test that verification email contains the correct verification link."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            token = "verification_token_xyz"
            base_url = "https://example.com"
            
            await email_service.send_verification_email(
                email="user@example.com",
                token=token,
                base_url=base_url
            )
            
            # Get the message that was sent
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Verify the message structure
            assert message["To"] == "user@example.com"
            assert message["Subject"] == "Verify Your Email Address"
            assert message["From"] == "Test App <noreply@example.com>"
            
            # Verify the verification link is in the message
            expected_link = f"{base_url}/auth/verify-email?token={token}"
            message_body = str(message)
            assert expected_link in message_body
    
    @pytest.mark.asyncio
    async def test_verification_email_template_rendering(self, email_service):
        """Test that verification email renders HTML and text templates correctly."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_verification_email(
                email="user@example.com",
                token="test_token",
                base_url="http://localhost:8000"
            )
            
            # Get the message that was sent
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Verify message is multipart
            assert message.is_multipart()
            
            # Get message parts
            parts = message.get_payload()
            assert len(parts) == 2
            
            # Verify plain text part
            text_part = parts[0]
            assert text_part.get_content_type() == "text/plain"
            text_content = text_part.get_payload()
            assert "Welcome to Test App!" in text_content
            assert "verify your email" in text_content.lower()
            
            # Verify HTML part
            html_part = parts[1]
            assert html_part.get_content_type() == "text/html"
            html_content = html_part.get_payload()
            assert "<html>" in html_content
            assert "Verify Email Address" in html_content
            assert "http://localhost:8000/auth/verify-email?token=test_token" in html_content

    @pytest.mark.asyncio
    async def test_verification_email_without_credentials(self, email_service):
        """Test sending verification email when SMTP credentials are not provided."""
        email_service.smtp_username = None
        email_service.smtp_password = None
        
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_verification_email(
                email="user@example.com",
                token="test_token",
                base_url="http://localhost:8000"
            )
            
            # Verify login was NOT called when credentials are missing
            mock_server.login.assert_not_called()
            
            # But send_message should still be called
            mock_server.send_message.assert_called_once()


class TestSendPasswordResetEmail:
    """Test send_password_reset_email method."""
    
    @pytest.mark.asyncio
    async def test_send_password_reset_email_success(self, email_service):
        """Test successful password reset email sending with mocked SMTP."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_password_reset_email(
                email="user@example.com",
                token="reset_token_456",
                base_url="http://localhost:8000"
            )
            
            # Verify SMTP connection was established
            mock_smtp.assert_called_once_with("smtp.test.com", 587)
            
            # Verify starttls was called
            mock_server.starttls.assert_called_once()
            
            # Verify send_message was called
            mock_server.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_password_reset_email_contains_correct_link(self, email_service):
        """Test that password reset email contains the correct reset link."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            token = "reset_token_abc"
            base_url = "https://example.com"
            
            await email_service.send_password_reset_email(
                email="user@example.com",
                token=token,
                base_url=base_url
            )
            
            # Get the message that was sent
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Verify the message structure
            assert message["To"] == "user@example.com"
            assert message["Subject"] == "Reset Your Password"
            assert message["From"] == "Test App <noreply@example.com>"
            
            # Verify the reset link is in the message
            expected_link = f"{base_url}/auth/reset-password?token={token}"
            message_body = str(message)
            assert expected_link in message_body
    
    @pytest.mark.asyncio
    async def test_password_reset_email_template_rendering(self, email_service):
        """Test that password reset email renders HTML and text templates correctly."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_password_reset_email(
                email="user@example.com",
                token="reset_token",
                base_url="http://localhost:8000"
            )
            
            # Get the message that was sent
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Verify message is multipart
            assert message.is_multipart()
            
            # Get message parts
            parts = message.get_payload()
            assert len(parts) == 2
            
            # Verify plain text part
            text_part = parts[0]
            assert text_part.get_content_type() == "text/plain"
            text_content = text_part.get_payload()
            assert "Password Reset Request" in text_content
            assert "reset your password" in text_content.lower()
            
            # Verify HTML part
            html_part = parts[1]
            assert html_part.get_content_type() == "text/html"
            html_content = html_part.get_payload()
            assert "<html>" in html_content
            assert "Reset Password" in html_content
            assert "http://localhost:8000/auth/reset-password?token=reset_token" in html_content


class TestSendAccountLockedEmail:
    """Test send_account_locked_email method."""
    
    @pytest.mark.asyncio
    async def test_send_account_locked_email_success(self, email_service):
        """Test successful account locked email sending with mocked SMTP."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_account_locked_email(
                email="user@example.com",
                locked_until="2024-01-01 12:00:00"
            )
            
            # Verify SMTP connection was established
            mock_smtp.assert_called_once_with("smtp.test.com", 587)
            
            # Verify send_message was called
            mock_server.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_account_locked_email_with_timestamp(self, email_service):
        """Test account locked email includes the locked_until timestamp."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            locked_until = "2024-01-01 15:30:00"
            
            await email_service.send_account_locked_email(
                email="user@example.com",
                locked_until=locked_until
            )
            
            # Get the message that was sent
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Verify the message structure
            assert message["To"] == "user@example.com"
            assert message["Subject"] == "Security Alert: Account Temporarily Locked"
            
            # Verify the locked_until timestamp is in the message
            message_body = str(message)
            assert locked_until in message_body
    
    @pytest.mark.asyncio
    async def test_account_locked_email_without_timestamp(self, email_service):
        """Test account locked email with default duration when no timestamp provided."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_account_locked_email(
                email="user@example.com"
            )
            
            # Get the message that was sent
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Verify default duration is mentioned
            message_body = str(message)
            assert "15 minutes" in message_body
    
    @pytest.mark.asyncio
    async def test_account_locked_email_template_rendering(self, email_service):
        """Test that account locked email renders HTML and text templates correctly."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_account_locked_email(
                email="user@example.com",
                locked_until="2024-01-01 12:00:00"
            )
            
            # Get the message that was sent
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Verify message is multipart
            assert message.is_multipart()
            
            # Get message parts
            parts = message.get_payload()
            assert len(parts) == 2
            
            # Verify plain text part
            text_part = parts[0]
            assert text_part.get_content_type() == "text/plain"
            text_content = text_part.get_payload()
            assert "Security Alert" in text_content
            assert "temporarily locked" in text_content.lower()
            
            # Verify HTML part
            html_part = parts[1]
            assert html_part.get_content_type() == "text/html"
            html_content = html_part.get_payload()
            assert "<html>" in html_content
            assert "Security Alert" in html_content
            assert "temporarily locked" in html_content.lower()



class TestEmailErrorHandling:
    """Test error handling for failed email delivery."""
    
    @pytest.mark.asyncio
    async def test_smtp_connection_error(self, email_service):
        """Test handling of SMTP connection errors."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = smtplib.SMTPConnectError(421, "Connection refused")
            
            with pytest.raises(Exception) as exc_info:
                await email_service.send_verification_email(
                    email="user@example.com",
                    token="test_token",
                    base_url="http://localhost:8000"
                )
            
            assert "Failed to send email" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_smtp_authentication_error(self, email_service):
        """Test handling of SMTP authentication errors."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, "Authentication failed")
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            with pytest.raises(Exception) as exc_info:
                await email_service.send_verification_email(
                    email="user@example.com",
                    token="test_token",
                    base_url="http://localhost:8000"
                )
            
            assert "Failed to send email" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_smtp_recipient_error(self, email_service):
        """Test handling of SMTP recipient errors."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_server.send_message.side_effect = smtplib.SMTPRecipientsRefused({
                "user@example.com": (550, "User unknown")
            })
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            with pytest.raises(Exception) as exc_info:
                await email_service.send_verification_email(
                    email="user@example.com",
                    token="test_token",
                    base_url="http://localhost:8000"
                )
            
            assert "Failed to send email" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_smtp_server_disconnected_error(self, email_service):
        """Test handling of SMTP server disconnection errors."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_server.send_message.side_effect = smtplib.SMTPServerDisconnected("Connection lost")
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            with pytest.raises(Exception) as exc_info:
                await email_service.send_password_reset_email(
                    email="user@example.com",
                    token="reset_token",
                    base_url="http://localhost:8000"
                )
            
            assert "Failed to send email" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, email_service):
        """Test handling of generic exceptions during email sending."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("Unexpected error")
            
            with pytest.raises(Exception) as exc_info:
                await email_service.send_account_locked_email(
                    email="user@example.com"
                )
            
            assert "Failed to send email" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_error_logging_on_failure(self, email_service):
        """Test that errors are logged when email sending fails."""
        with patch('smtplib.SMTP') as mock_smtp, \
             patch('app.services.email_service.logger') as mock_logger:
            
            mock_smtp.side_effect = smtplib.SMTPConnectError(421, "Connection refused")
            
            with pytest.raises(Exception):
                await email_service.send_verification_email(
                    email="user@example.com",
                    token="test_token",
                    base_url="http://localhost:8000"
                )
            
            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to send email to user@example.com" in error_call


class TestEmailMessageStructure:
    """Test email message structure and formatting."""
    
    @pytest.mark.asyncio
    async def test_message_has_correct_headers(self, email_service):
        """Test that email messages have correct headers."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_verification_email(
                email="test@example.com",
                token="token123",
                base_url="http://localhost:8000"
            )
            
            # Get the message
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Verify headers
            assert message["Subject"] is not None
            assert message["From"] == "Test App <noreply@example.com>"
            assert message["To"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_message_is_multipart_alternative(self, email_service):
        """Test that email messages use multipart/alternative format."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_password_reset_email(
                email="test@example.com",
                token="reset123",
                base_url="http://localhost:8000"
            )
            
            # Get the message
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Verify multipart structure
            assert message.is_multipart()
            assert message.get_content_type() == "multipart/alternative"
    
    @pytest.mark.asyncio
    async def test_message_contains_both_text_and_html(self, email_service):
        """Test that email messages contain both text and HTML parts."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_account_locked_email(
                email="test@example.com"
            )
            
            # Get the message
            call_args = mock_server.send_message.call_args
            message = call_args[0][0]
            
            # Get parts
            parts = message.get_payload()
            
            # Verify we have exactly 2 parts
            assert len(parts) == 2
            
            # Verify content types
            content_types = [part.get_content_type() for part in parts]
            assert "text/plain" in content_types
            assert "text/html" in content_types


class TestEmailLogging:
    """Test email sending logging."""
    
    @pytest.mark.asyncio
    async def test_successful_send_is_logged(self, email_service):
        """Test that successful email sends are logged."""
        with patch('smtplib.SMTP') as mock_smtp, \
             patch('app.services.email_service.logger') as mock_logger:
            
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            await email_service.send_verification_email(
                email="user@example.com",
                token="test_token",
                base_url="http://localhost:8000"
            )
            
            # Verify success was logged
            mock_logger.info.assert_called_once()
            info_call = mock_logger.info.call_args[0][0]
            assert "Email sent successfully to user@example.com" in info_call
            assert "Verify Your Email Address" in info_call
