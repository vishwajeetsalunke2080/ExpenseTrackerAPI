"""Simple unit tests for AuthService without database dependencies."""
import pytest
from app.services.auth_service import AuthService


class TestAuthServicePasswordFunctions:
    """Test password-related functions that don't require database."""
    
    def test_hash_password(self):
        """Test password hashing produces valid bcrypt hash."""
        service = AuthService()
        password = "TestPassword123"
        
        hashed = service.hash_password(password)
        
        # Hash should not equal original password
        assert hashed != password
        # Hash should be a valid bcrypt hash (starts with $2b$)
        assert hashed.startswith("$2b$")
        # Hash should contain cost factor 12
        assert "$2b$12$" in hashed
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        service = AuthService()
        password = "TestPassword123"
        hashed = service.hash_password(password)
        
        result = service.verify_password(password, hashed)
        
        assert result is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        service = AuthService()
        password = "TestPassword123"
        wrong_password = "WrongPassword456"
        hashed = service.hash_password(password)
        
        result = service.verify_password(wrong_password, hashed)
        
        assert result is False
    
    def test_verify_password_invalid_hash(self):
        """Test password verification with invalid hash format."""
        service = AuthService()
        password = "TestPassword123"
        invalid_hash = "not_a_valid_hash"
        
        result = service.verify_password(password, invalid_hash)
        
        assert result is False
    
    def test_validate_password_strength_valid(self):
        """Test password strength validation with valid passwords."""
        service = AuthService()
        
        # Valid password: 8+ chars, uppercase, lowercase, number
        assert service.validate_password_strength("ValidPass123") is True
        assert service.validate_password_strength("Abcdefg1") is True
        assert service.validate_password_strength("MyP@ssw0rd") is True
        assert service.validate_password_strength("Test1234") is True
    
    def test_validate_password_strength_too_short(self):
        """Test password strength validation with too short password."""
        service = AuthService()
        
        # Less than 8 characters
        assert service.validate_password_strength("Pass1") is False
        assert service.validate_password_strength("Abc123") is False
        assert service.validate_password_strength("Test1") is False
    
    def test_validate_password_strength_no_uppercase(self):
        """Test password strength validation without uppercase."""
        service = AuthService()
        
        # No uppercase letter
        assert service.validate_password_strength("password123") is False
        assert service.validate_password_strength("test12345") is False
    
    def test_validate_password_strength_no_lowercase(self):
        """Test password strength validation without lowercase."""
        service = AuthService()
        
        # No lowercase letter
        assert service.validate_password_strength("PASSWORD123") is False
        assert service.validate_password_strength("TEST12345") is False
    
    def test_validate_password_strength_no_number(self):
        """Test password strength validation without number."""
        service = AuthService()
        
        # No number
        assert service.validate_password_strength("PasswordOnly") is False
        assert service.validate_password_strength("TestPassword") is False
    
    def test_validate_password_strength_edge_cases(self):
        """Test password strength validation edge cases."""
        service = AuthService()
        
        # Exactly 8 characters with all requirements
        assert service.validate_password_strength("Pass123A") is True
        
        # Empty string
        assert service.validate_password_strength("") is False
        
        # Only special characters
        assert service.validate_password_strength("!@#$%^&*") is False
        
        # Mix of special characters with requirements
        assert service.validate_password_strength("P@ssw0rd!") is True
    
    def test_bcrypt_cost_factor(self):
        """Test that bcrypt uses cost factor 12."""
        service = AuthService()
        
        assert service.BCRYPT_COST_FACTOR == 12
    
    def test_hash_password_different_hashes(self):
        """Test that hashing same password twice produces different hashes (due to salt)."""
        service = AuthService()
        password = "TestPassword123"
        
        hash1 = service.hash_password(password)
        hash2 = service.hash_password(password)
        
        # Hashes should be different due to different salts
        assert hash1 != hash2
        
        # But both should verify correctly
        assert service.verify_password(password, hash1) is True
        assert service.verify_password(password, hash2) is True
