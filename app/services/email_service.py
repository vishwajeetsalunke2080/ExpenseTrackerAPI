"""Email service for sending authentication-related emails.

This service handles sending verification emails, password reset emails,
and security notification emails using SMTP. Configuration is loaded from
environment variables.

Requirements: 1.5, 5.2, 7.2, 10.2
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending authentication-related emails.
    
    Handles email delivery via SMTP with HTML templates for verification,
    password reset, and security notifications.
    """
    
    def __init__(self):
        """Initialize email service with SMTP configuration from settings."""
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.from_email = settings.smtp_from_email
        self.from_name = settings.smtp_from_name
    
    async def send_verification_email(
        self,
        email: str,
        token: str,
        base_url: str = settings.api_baseurl
    ) -> None:
        """Send email verification link to user.
        
        Creates an email with a verification link containing the token.
        The link directs users to the email verification endpoint.
        
        Requirements: 1.5, 7.2
        
        Args:
            email: Recipient email address
            token: Email verification token
            base_url: Base URL for constructing verification link
            
        Raises:
            Exception: If email sending fails
        """
        verification_link = f"{base_url}/auth/verify-email?token={token}"
        
        subject = "Verify Your Email Address"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #4CAF50;">Welcome to {self.from_name}!</h2>
                    <p>Thank you for signing up. Please verify your email address to activate your account.</p>
                    <p>Click the button below to verify your email:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{verification_link}" 
                           style="background-color: #4CAF50; color: white; padding: 12px 30px; 
                                  text-decoration: none; border-radius: 5px; display: inline-block;">
                            Verify Email Address
                        </a>
                    </div>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #666;">{verification_link}</p>
                    <p style="margin-top: 30px; font-size: 12px; color: #999;">
                        This verification link will expire in 24 hours.
                    </p>
                    <p style="font-size: 12px; color: #999;">
                        If you didn't create an account, please ignore this email.
                    </p>
                </div>
            </body>
        </html>
        """
        
        text_body = f"""
        Welcome to {self.from_name}!
        
        Thank you for signing up. Please verify your email address to activate your account.
        
        Click the link below to verify your email:
        {verification_link}
        
        This verification link will expire in 24 hours.
        
        If you didn't create an account, please ignore this email.
        """
        
        await self._send_email(email, subject, html_body, text_body)
    
    async def send_password_reset_email(
        self,
        email: str,
        token: str,
        base_url: str = "http://localhost:8000"
    ) -> None:
        """Send password reset link to user.
        
        Creates an email with a password reset link containing the token.
        The link directs users to the password reset page.
        
        Requirements: 5.2
        
        Args:
            email: Recipient email address
            token: Password reset token
            base_url: Base URL for constructing reset link
            
        Raises:
            Exception: If email sending fails
        """
        reset_link = f"{base_url}/auth/reset-password?token={token}"
        
        subject = "Reset Your Password"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #FF9800;">Password Reset Request</h2>
                    <p>We received a request to reset your password for your {self.from_name} account.</p>
                    <p>Click the button below to reset your password:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" 
                           style="background-color: #FF9800; color: white; padding: 12px 30px; 
                                  text-decoration: none; border-radius: 5px; display: inline-block;">
                            Reset Password
                        </a>
                    </div>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #666;">{reset_link}</p>
                    <p style="margin-top: 30px; font-size: 12px; color: #999;">
                        This password reset link will expire in 1 hour.
                    </p>
                    <p style="font-size: 12px; color: #999;">
                        If you didn't request a password reset, please ignore this email. 
                        Your password will remain unchanged.
                    </p>
                </div>
            </body>
        </html>
        """
        
        text_body = f"""
        Password Reset Request
        
        We received a request to reset your password for your {self.from_name} account.
        
        Click the link below to reset your password:
        {reset_link}
        
        This password reset link will expire in 1 hour.
        
        If you didn't request a password reset, please ignore this email. 
        Your password will remain unchanged.
        """
        
        await self._send_email(email, subject, html_body, text_body)
    
    async def send_account_locked_email(
        self,
        email: str,
        locked_until: Optional[str] = None
    ) -> None:
        """Send security notification when account is locked.
        
        Notifies users when their account has been temporarily locked due to
        multiple failed sign-in attempts.
        
        Requirements: 10.2
        
        Args:
            email: Recipient email address
            locked_until: Optional timestamp when lock expires
            
        Raises:
            Exception: If email sending fails
        """
        subject = "Security Alert: Account Temporarily Locked"
        
        lock_duration = "15 minutes" if not locked_until else f"until {locked_until}"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #F44336;">Security Alert</h2>
                    <p>Your {self.from_name} account has been temporarily locked due to multiple failed sign-in attempts.</p>
                    <div style="background-color: #FFF3CD; border-left: 4px solid #FFC107; padding: 15px; margin: 20px 0;">
                        <strong>Account Status:</strong> Temporarily Locked<br>
                        <strong>Lock Duration:</strong> {lock_duration}
                    </div>
                    <p>This is a security measure to protect your account from unauthorized access.</p>
                    <h3>What should you do?</h3>
                    <ul>
                        <li>Wait for the lock period to expire, then try signing in again</li>
                        <li>If you forgot your password, use the "Forgot Password" option</li>
                        <li>If you didn't attempt to sign in, your account may be at risk</li>
                    </ul>
                    <p style="margin-top: 30px; font-size: 12px; color: #999;">
                        If you believe this is an error or have security concerns, please contact our support team.
                    </p>
                </div>
            </body>
        </html>
        """
        
        text_body = f"""
        Security Alert
        
        Your {self.from_name} account has been temporarily locked due to multiple failed sign-in attempts.
        
        Account Status: Temporarily Locked
        Lock Duration: {lock_duration}
        
        This is a security measure to protect your account from unauthorized access.
        
        What should you do?
        - Wait for the lock period to expire, then try signing in again
        - If you forgot your password, use the "Forgot Password" option
        - If you didn't attempt to sign in, your account may be at risk
        
        If you believe this is an error or have security concerns, please contact our support team.
        """
        
        await self._send_email(email, subject, html_body, text_body)
    
    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> None:
        """Send an email via SMTP.
        
        Internal method that handles the actual SMTP connection and email sending.
        Supports both HTML and plain text versions of the email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_body: HTML version of email body
            text_body: Plain text version of email body
            
        Raises:
            Exception: If SMTP connection or sending fails
        """
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Attach both plain text and HTML versions
            text_part = MIMEText(text_body, "plain")
            html_part = MIMEText(html_body, "html")
            
            message.attach(text_part)
            message.attach(html_part)
            
            # Send email via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()  # Upgrade to secure connection
                
                # Only authenticate if credentials are provided
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(message)
            
            logger.info(f"Email sent successfully to {to_email}: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            raise Exception(f"Failed to send email: {str(e)}")
