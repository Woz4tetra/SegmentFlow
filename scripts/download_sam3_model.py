#!/usr/bin/env python3
"""Download and cache SAM3 model from Hugging Face.

This script downloads the SAM3 model from the gated Hugging Face repository
and caches it locally so it can be mounted to Docker containers.

IMPORTANT: SAM3 is a gated model. Before running this script:
1. Go to https://huggingface.co/facebook/sam3
2. Accept the model terms and conditions
3. Create a HuggingFace token at https://huggingface.co/settings/tokens
4. Make sure the token has 'read' access

Usage:
    export HF_TOKEN="your_huggingface_token"
    python scripts/download_sam3_model.py

The model will be cached in ./backend/data/models/ which gets mounted to
the Docker container at /root/.cache/huggingface/hub/
"""

import os
import sys
from pathlib import Path

try:
    from huggingface_hub import snapshot_download, login
except ImportError:
    print("ERROR: huggingface_hub not installed.")
    print("Install it with: pip install huggingface_hub")
    sys.exit(1)


def main() -> None:
    """Download and cache SAM3 model."""
    # Get Hugging Face token from environment
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("ERROR: HF_TOKEN environment variable not set.")
        print("")
        print("To use SAM3, you need a HuggingFace token with access to the gated model.")
        print("")
        print("Steps:")
        print("1. Go to https://huggingface.co/facebook/sam3")
        print("2. Click 'Agree and access repository' to accept the terms")
        print("3. Create a token at https://huggingface.co/settings/tokens")
        print("4. Set it with: export HF_TOKEN='your_token_here'")
        print("5. Run this script again")
        sys.exit(1)

    # Login to Hugging Face
    print("Authenticating with Hugging Face...")
    try:
        login(token=hf_token, add_to_git_credential=False)
        print("✓ Authentication successful")
    except Exception as e:
        print(f"ERROR: Failed to authenticate with Hugging Face: {e}")
        sys.exit(1)

    # Model repository
    repo_id = "facebook/sam3"
    
    # Download to match the Docker mount structure:
    # Local: ./backend/data/models/ -> Container: /root/.cache/huggingface/hub/
    # HuggingFace Hub creates: hub/models--facebook--sam3/snapshots/<commit>/
    base_dir = Path(__file__).parent.parent / "backend" / "data" / "models"
    base_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nDownloading SAM3 model from: {repo_id}")
    print(f"Cache directory: {base_dir}")
    print("This may take several minutes depending on your connection...")
    print("(The model is several GB in size)")

    try:
        # Download directly to the target directory
        # This creates: base_dir/models--facebook--sam3/snapshots/<commit>/
        # which Docker mounts to: /root/.cache/huggingface/hub/models--facebook--sam3/
        local_dir = snapshot_download(
            repo_id=repo_id,
            cache_dir=str(base_dir),
            token=hf_token,
            resume_download=True,
        )
        
        print(f"\n✓ Successfully downloaded SAM3 model")
        print(f"Model cached at: {local_dir}")
        
        # Verify the structure
        expected_structure = base_dir / "models--facebook--sam3"
        if expected_structure.exists():
            print(f"✓ Verified cache structure: {expected_structure}")
        else:
            print(f"⚠ Warning: Expected cache structure not found at {expected_structure}")
        
        print(f"\nThe model is now ready to use.")
        print(f"Make sure to set HF_TOKEN in your .env file for Docker to use:")
        print(f"  echo 'HF_TOKEN=your_token_here' > .env")
        print(f"\nThen start the services: docker-compose up -d")
        
    except Exception as e:
        print(f"\nERROR: Failed to download model: {e}")
        if "401" in str(e) or "unauthorized" in str(e).lower() or "access" in str(e).lower():
            print("\nThis error means you don't have access to the facebook/sam3 model.")
            print("")
            print("To fix this:")
            print("1. Go to https://huggingface.co/facebook/sam3")
            print("2. Click 'Agree and access repository' to accept the model terms")
            print("3. Wait a few minutes for access to be granted")
            print("4. Verify your HF_TOKEN is correct and has 'read' permissions")
            print("5. Try running this script again")
        elif "404" in str(e) or "not found" in str(e).lower():
            print("\nThe repository may not exist or the name is incorrect.")
            print(f"Please verify the repository ID: {repo_id}")
        sys.exit(1)


if __name__ == "__main__":
    main()

