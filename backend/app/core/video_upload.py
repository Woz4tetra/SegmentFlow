"""Video upload service for handling chunked uploads with integrity checks."""

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import NamedTuple

from app.core.logging import get_logger

logger = get_logger(__name__)


class UploadSession(NamedTuple):
    """Represents an active upload session.

    Attributes:
        project_id: ID of the project being uploaded to
        total_chunks: Total number of chunks expected
        total_size: Total size of the final file in bytes
        file_hash: file hash of the complete file for integrity verification
        temp_dir: Temporary directory storing chunk files
        chunks_received: Number of chunks received so far
    """

    project_id: str
    total_chunks: int
    total_size: int
    file_hash: str
    temp_dir: Path
    chunks_received: int = 0


class VideoUploadService:
    """Service for managing chunked video uploads.

    Supports:
    - Chunked upload of large files (100MB+)
    - Integrity verification via file hash
    - Progress tracking
    - Automatic cleanup of failed uploads
    - Resumable uploads by storing chunks temporarily

    Attributes:
        max_chunk_size: Maximum allowed chunk size in bytes (100MB default)
        temp_base_dir: Base directory for temporary upload storage
    """

    def __init__(self, temp_base_dir: Path | str | None = None):
        """Initialize the video upload service.

        Args:
            temp_base_dir: Base directory for temporary upload storage.
                If None, uses system temp directory. Defaults to None.
        """
        if temp_base_dir is None:
            self.temp_base_dir = Path(tempfile.gettempdir()) / "segmentflow_uploads"
        else:
            self.temp_base_dir = Path(temp_base_dir)

        self.temp_base_dir.mkdir(parents=True, exist_ok=True)
        self.max_chunk_size = 100 * 1024 * 1024  # 100MB
        self._sessions: dict[str, UploadSession] = {}

    def start_upload(
        self,
        project_id: str,
        total_chunks: int,
        total_size: int,
        file_hash: str,
    ) -> None:
        """Initialize a new upload session.

        Args:
            project_id: ID of the project to upload to
            total_chunks: Total number of chunks expected
            total_size: Total size of the complete file in bytes
            file_hash: file hash of the complete file for verification

        Raises:
            ValueError: If an upload session already exists for this project
            ValueError: If total_size exceeds reasonable limits (1GB)
        """
        session_key = str(project_id)

        if session_key in self._sessions:
            raise ValueError(f"Upload already in progress for project {project_id}")

        if total_size > 1024 * 1024 * 1024:  # 1GB limit
            raise ValueError("File size exceeds 1GB limit")

        temp_dir = self.temp_base_dir / session_key
        temp_dir.mkdir(parents=True, exist_ok=True)

        session = UploadSession(
            project_id=session_key,
            total_chunks=total_chunks,
            total_size=total_size,
            file_hash=file_hash,
            temp_dir=temp_dir,
            chunks_received=0,
        )
        self._sessions[session_key] = session
        logger.info(
            f"Started upload session for project {project_id}: "
            f"{total_chunks} chunks, {total_size} bytes"
        )

    def save_chunk(
        self,
        project_id: str,
        chunk_number: int,
        chunk_data: bytes,
    ) -> None:
        """Save an uploaded chunk to temporary storage.

        Args:
            project_id: ID of the project
            chunk_number: Sequential chunk number (0-indexed)
            chunk_data: Binary data of the chunk

        Raises:
            ValueError: If no upload session exists for this project
            ValueError: If chunk_number is out of range
            ValueError: If chunk_data exceeds max_chunk_size
        """
        session_key = str(project_id)

        if session_key not in self._sessions:
            raise ValueError(f"No upload session for project {project_id}")

        session = self._sessions[session_key]

        if chunk_number < 0 or chunk_number >= session.total_chunks:
            raise ValueError(
                f"Invalid chunk number {chunk_number}. Expected 0-{session.total_chunks - 1}"
            )

        if len(chunk_data) > self.max_chunk_size:
            raise ValueError(f"Chunk size {len(chunk_data)} exceeds maximum {self.max_chunk_size}")

        # Save chunk to temporary file
        chunk_path = session.temp_dir / f"chunk_{chunk_number:06d}"
        with open(chunk_path, "wb") as f:
            f.write(chunk_data)

        logger.info(
            f"Saved chunk {chunk_number}/{session.total_chunks - 1} for project {project_id} "
            f"({len(chunk_data)} bytes)"
        )

    def get_progress(self, project_id: str) -> dict:
        """Get upload progress for a project.

        Args:
            project_id: ID of the project

        Returns:
            dict: Progress information including:
                - uploaded_size: bytes uploaded so far
                - progress_percent: percentage complete (0-100)
                - chunks_received: number of chunks received
                - total_chunks: total chunks expected
                - status: current status

        Raises:
            ValueError: If no upload session exists for this project
        """
        session_key = str(project_id)
        logger.info(f"Checking upload progress for project {project_id}")

        if session_key not in self._sessions:
            raise ValueError(f"No upload session for project {project_id}")

        session = self._sessions[session_key]

        # Count received chunks
        chunks_received = len(list(session.temp_dir.glob("chunk_*")))
        uploaded_size = chunks_received * (session.total_size // session.total_chunks)

        # Adjust for potential partial chunks
        chunk_files = sorted(session.temp_dir.glob("chunk_*"))
        if chunk_files:
            total_uploaded = sum(f.stat().st_size for f in chunk_files)
            uploaded_size = total_uploaded

        progress_percent = (
            (uploaded_size / session.total_size * 100) if session.total_size > 0 else 0
        )

        return {
            "uploaded_size": uploaded_size,
            "progress_percent": round(progress_percent, 2),
            "chunks_received": chunks_received,
            "total_chunks": session.total_chunks,
            "status": "uploading",
        }

    def finalize_upload(self, project_id: str, output_path: Path) -> bool:
        """Finalize an upload by combining chunks and verifying integrity.

        Combines all chunks into the final video file, verifies the file hash,
        and cleans up temporary files.

        Args:
            project_id: ID of the project
            output_path: Path where the final video should be saved

        Returns:
            bool: True if upload was finalized successfully

        Raises:
            ValueError: If no upload session exists for this project
            RuntimeError: If file hash verification fails
            RuntimeError: If chunk count doesn't match expected
        """
        session_key = str(project_id)
        logger.info(f"Starting finalization of upload for project {project_id}")

        if session_key not in self._sessions:
            raise ValueError(f"No upload session for project {project_id}")

        session = self._sessions[session_key]

        # Verify all chunks are present
        chunk_files = sorted(session.temp_dir.glob("chunk_*"))
        if len(chunk_files) != session.total_chunks:
            raise RuntimeError(
                f"Missing chunks: received {len(chunk_files)}, expected {session.total_chunks}"
            )

        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Combine chunks into final file
        logger.info(f"Combining {len(chunk_files)} chunks into {output_path}")
        try:
            with open(output_path, "wb") as out_file:
                for i, chunk_file in enumerate(chunk_files):
                    with open(chunk_file, "rb") as f:
                        out_file.write(f.read())
                    if (i + 1) % 10 == 0:  # Log every 10 chunks
                        logger.info(f"Combined {i + 1}/{len(chunk_files)} chunks")

            # Verify file hash
            logger.info(f"Verifying file integrity for project {project_id}")
            file_hash = self._compute_file_hash(output_path)
            if file_hash != session.file_hash:
                output_path.unlink()  # Delete corrupted file
                logger.error(
                    f"Hash mismatch for {project_id}: expected {session.file_hash}, got {file_hash}"
                )
                raise RuntimeError(
                    f"File hash mismatch. Expected {session.file_hash}, got {file_hash}"
                )

            logger.info(f"Successfully finalized upload for project {project_id}: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to finalize upload for project {project_id}: {e}")
            # Clean up partial file if it exists
            if output_path.exists():
                output_path.unlink()
            raise

        finally:
            # Clean up temporary directory
            self.cancel_upload(project_id)

    def cancel_upload(self, project_id: str) -> None:
        """Cancel an upload and clean up temporary files.

        Args:
            project_id: ID of the project
        """
        session_key = str(project_id)

        if session_key not in self._sessions:
            return

        session = self._sessions[session_key]

        try:
            if session.temp_dir.exists():
                shutil.rmtree(session.temp_dir)
                logger.info(f"Cleaned up temporary files for project {project_id}")
        except Exception as e:
            logger.warning(f"Error cleaning up temporary files for {project_id}: {e}")

        del self._sessions[session_key]

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            str: Hexadecimal SHA-256 hash of the file
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
