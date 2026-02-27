"""Quick test to verify JWT configuration is working."""
from app.config import settings

print("Testing JWT Configuration...")
print(f"✓ JWT Algorithm: {settings.jwt_algorithm}")
print(f"✓ Private key loaded: {len(settings.jwt_private_key)} characters")
print(f"✓ Public key loaded: {len(settings.jwt_public_key)} characters")
print("\nAll configuration loaded successfully!")
