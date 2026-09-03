"""The WhisperX service: transcription, alignment, and diarization on one GPU.

The service is independent of the app that consumes it. Its contract, which is
what this package implements, is docs/whisperx-api.md in the same repository.
"""

from service.version import API_VERSION, SERVICE_VERSION

__all__ = ["API_VERSION", "SERVICE_VERSION"]
