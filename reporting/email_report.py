"""
Email Report Module

Handles sending email reports with PDF attachments.
"""

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class EmailSender:
    """Sender for ESI-Lite email reports."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize email sender.
        
        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.email_config = config.get("email", {})
        self.smtp_config = self.email_config.get("smtp", {})
        self.address_config = self.email_config.get("addresses", {})
        
        # SMTP settings
        self.smtp_host = self._get_env_or_config("SMTP_HOST", self.smtp_config.get("host", ""))
        self.smtp_port = self._get_int_env_or_config("SMTP_PORT", self.smtp_config.get("port", 587), 587)
        self.smtp_user = self._get_env_or_config("SMTP_USER", self.smtp_config.get("user", ""))
        self.smtp_password = self._get_env_or_config("SMTP_PASSWORD", self.smtp_config.get("password", ""))
        self.use_tls = self.smtp_config.get("use_tls", True)
        self.timeout = self.smtp_config.get("timeout", 30)
        
        # Email addresses
        self.mail_from = self._get_env_or_config("MAIL_FROM", self.address_config.get("from", ""))
        self.mail_to = self._get_env_or_config("MAIL_TO", self.address_config.get("to", ""))
        
        # Subject template
        self.subject_template = self.email_config.get(
            "subject_template", 
            "[ESI-Lite] {date} | Score: {score:.1f} | Regime: {regime}"
        )
        
        logger.info("Email Sender initialized")
    
    def _get_env_or_config(self, env_var: str, config_value: str) -> str:
        """
        Get value from environment variable or config.
        
        Args:
            env_var: Environment variable name
            config_value: Config value as fallback
            
        Returns:
            Value from environment or config
        """
        # Check if config value is an environment variable reference
        if isinstance(config_value, str) and config_value.startswith("${") and config_value.endswith("}"):
            env_name = config_value[2:-1]
            return os.getenv(env_name, "")
        
        # Otherwise, check environment variable directly
        env_value = os.getenv(env_var, "")
        if env_value:
            return env_value
        
        return config_value

    def _get_int_env_or_config(self, env_var: str, config_value: Any, default: int) -> int:
        """
        Get an integer setting from env or config with a safe fallback.

        Empty strings and invalid values fall back to `default` instead of
        crashing the pipeline during initialization.
        """
        raw_value = self._get_env_or_config(env_var, str(config_value) if config_value is not None else "")
        if raw_value in [None, ""]:
            return default

        try:
            return int(raw_value)
        except (TypeError, ValueError):
            logger.warning("Invalid %s value '%s', falling back to %s", env_var, raw_value, default)
            return default
    
    def is_configured(self) -> bool:
        """
        Check if email is properly configured.
        
        Returns:
            True if all required settings are present
        """
        required = [
            self.smtp_host,
            self.smtp_user,
            self.smtp_password,
            self.mail_from,
            self.mail_to,
        ]
        return all(required)
    
    def send_report(
        self,
        html_content: str,
        pdf_attachment: Optional[str] = None,
        latest_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send email report.
        
        Args:
            html_content: HTML content for email body
            pdf_attachment: Path to PDF attachment
            latest_snapshot: Latest snapshot data for subject line
            
        Returns:
            Dictionary with send status
        """
        if not self.is_configured():
            logger.warning("Email not configured, skipping send")
            return {
                "success": False,
                "error": "Email not configured",
                "configured": False,
            }
        
        try:
            # Build subject
            subject = self._build_subject(latest_snapshot)
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.mail_from
            msg["To"] = self.mail_to
            
            # Attach HTML content
            msg.attach(MIMEText(html_content, "html"))
            
            # Attach PDF if provided
            if pdf_attachment and os.path.exists(pdf_attachment):
                with open(pdf_attachment, "rb") as f:
                    pdf_data = f.read()
                
                pdf_part = MIMEBase("application", "octet-stream")
                pdf_part.set_payload(pdf_data)
                encoders.encode_base64(pdf_part)
                
                filename = os.path.basename(pdf_attachment)
                pdf_part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {filename}"
                )
                msg.attach(pdf_part)
            
            # Send email
            context = ssl.create_default_context()
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout) as server:
                if self.use_tls:
                    server.starttls(context=context)
                
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.mail_from, self.mail_to, msg.as_string())
            
            logger.info(f"Email sent successfully to {self.mail_to}")
            return {
                "success": True,
                "error": None,
                "configured": True,
                "recipient": self.mail_to,
                "timestamp": datetime.now().isoformat(),
            }
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return {
                "success": False,
                "error": f"Authentication failed: {str(e)}",
                "configured": True,
            }
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return {
                "success": False,
                "error": f"SMTP error: {str(e)}",
                "configured": True,
            }
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return {
                "success": False,
                "error": str(e),
                "configured": True,
            }
    
    def _build_subject(self, snapshot: Optional[Dict[str, Any]]) -> str:
        """
        Build email subject line.
        
        Args:
            snapshot: Latest snapshot data
            
        Returns:
            Formatted subject line
        """
        if snapshot is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            return f"[ESI-Lite] {date_str} | Daily Update"
        
        date_str = snapshot.get("latest_date", datetime.now().strftime("%Y-%m-%d"))
        score = snapshot.get("current_score", 0)
        regime = snapshot.get("current_regime", {}).get("label", "Unknown")
        
        return self.subject_template.format(
            date=date_str,
            score=score,
            regime=regime
        )
