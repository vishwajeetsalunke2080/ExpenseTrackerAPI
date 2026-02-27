"""Generate RSA key pair for JWT signing.

This script generates a 2048-bit RSA key pair for use with RS256 JWT signing.
The keys are saved to the FastAPI directory as private_key.pem and public_key.pem.

Requirements: 2.4, 4.1
"""
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from pathlib import Path


def generate_rsa_keys():
    """Generate RSA key pair and save to PEM files."""
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Serialize private key to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Generate public key from private key
    public_key = private_key.public_key()
    
    # Serialize public key to PEM format
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Get the FastAPI directory
    base_dir = Path(__file__).parent
    
    # Save keys to files
    private_key_path = base_dir / "private_key.pem"
    public_key_path = base_dir / "public_key.pem"
    
    with open(private_key_path, "wb") as f:
        f.write(private_pem)
    
    with open(public_key_path, "wb") as f:
        f.write(public_pem)
    
    print(f"✓ RSA keys generated successfully!")
    print(f"  Private key: {private_key_path}")
    print(f"  Public key: {public_key_path}")
    print()
    print("IMPORTANT: Keep private_key.pem secure and never commit it to version control!")
    print("Add private_key.pem to .gitignore if not already present.")
    
    return private_key_path, public_key_path


if __name__ == "__main__":
    generate_rsa_keys()
