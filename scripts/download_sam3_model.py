#!/usr/bin/env python3
"""Download and cache SAM3 model from Hugging Face.

This script downloads the SAM3 model from the gated Hugging Face repository
and caches it locally so it can be mounted to Docker containers.

Usage:
    export HF_TOKEN="your_huggingface_token"
    python scripts/download_sam3_model.py

The model will be cached in ./data/models/sam3/ which can be mounted to containers.
Hugging Face Hub will automatically cache it in the standard location that SAM3 expects.
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
        print("Please set it with: export HF_TOKEN='your_token_here'")
        print("Get your token from: https://huggingface.co/settings/tokens")
        print("\nMake sure your token has access to the facebook/sam3 repository.")
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
    
    # Download to the standard Hugging Face cache structure
    # The structure should be: <cache_dir>/hub/models--facebook--sam3/snapshots/<commit>/
    base_cache = Path(__file__).parent.parent / "backend" / "data" / "models"
    cache_dir = base_cache / "hub"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Set HF_HOME to point to the parent of hub/ (where HF_HOME expects to find the hub/ directory)
    # This makes Hugging Face Hub use our directory instead of ~/.cache/huggingface
    os.environ["HF_HOME"] = str(base_cache)

    print(f"\nDownloading SAM3 model from: {repo_id}")
    print(f"Cache directory: {cache_dir}")
    print("This may take several minutes depending on your connection...")
    print("(The model is several GB in size)")

    try:
        # Use snapshot_download with cache_dir to use standard cache structure
        # This will create: cache_dir/models--facebook--sam3/snapshots/<commit>/
        # Which is what Hugging Face Hub expects
        local_dir = snapshot_download(
            repo_id=repo_id,
            cache_dir=str(cache_dir),  # This creates models--facebook--sam3/ structure inside
            token=hf_token,
            resume_download=True,  # Resume if interrupted
        )
        
        print(f"\n✓ Successfully downloaded SAM3 model")
        print(f"Model cached at: {local_dir}")
        print(f"\nCache structure created in: {cache_dir}")
        
        # Verify the structure
        expected_structure = cache_dir / "models--facebook--sam3"
        if expected_structure.exists():
            print(f"✓ Verified cache structure: {expected_structure}")
        else:
            print(f"⚠ Warning: Expected cache structure not found at {expected_structure}")
        
        print(f"\nThe model is now ready to be used.")
        print(f"\nThe docker-compose.yml mounts: ./backend/data/models:/root/.cache/huggingface/hub")
        print(f"This makes the cache available at: /root/.cache/huggingface/hub/models--facebook--sam3")
        
    except Exception as e:
        print(f"\nERROR: Failed to download model: {e}")
        if "401" in str(e) or "unauthorized" in str(e).lower():
            print("\nThis usually means:")
            print("1. Your HF_TOKEN is invalid or expired")
            print("2. You don't have access to the facebook/sam3 repository")
            print("3. You need to accept the model's terms of use at:")
            print("   https://huggingface.co/facebook/sam3")
        elif "404" in str(e) or "not found" in str(e).lower():
            print("\nThe repository may not exist or the name is incorrect.")
            print(f"Please verify the repository ID: {repo_id}")
        sys.exit(1)


if __name__ == "__main__":
    main()

