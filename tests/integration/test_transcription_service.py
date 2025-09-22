import pytest
import os
from pathlib import Path
from dotenv import load_dotenv
from voice_parser.services.transcription import TranscriptionClient
from voice_parser.core.settings import OpenAISettings


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load test environment variables from .env.test"""
    load_dotenv(".env.test")


@pytest.fixture
def test_openai_settings():
    """Create OpenAI settings using test environment variables"""
    return OpenAISettings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


@pytest.fixture
def transcription_client(test_openai_settings):
    """Create transcription client with test settings"""
    return TranscriptionClient(settings=test_openai_settings)


@pytest.fixture
def test_audio_file():
    """Provide path to test audio file"""
    test_dir = Path(__file__).parent.parent
    audio_file = test_dir / "fixtures" / "test_audio.wav"

    if not audio_file.exists():
        pytest.skip(f"Test audio file not found: {audio_file}")

    return audio_file


class TestTranscriptionClientIntegration:
    """Integration tests for transcription service using real OpenAI API"""

    @pytest.mark.asyncio
    async def test_transcribe_audio_file(self, transcription_client, test_audio_file):
        """Test transcribing a real audio file"""
        # Read the audio file
        with open(test_audio_file, "rb") as f:
            audio_data = f.read()

        # Transcribe the audio
        result = await transcription_client.transcribe(
            audio_data=audio_data,
            filename=test_audio_file.name
        )

        # Verify the result
        assert isinstance(result, str)
        assert len(result) > 0
        # The exact transcription will depend on your test file,
        # but it should contain recognizable words
        assert result.strip()  # Should not be just whitespace

    @pytest.mark.asyncio
    async def test_transcribe_empty_audio_fails(self, transcription_client):
        """Test that empty audio data raises an appropriate error"""
        with pytest.raises(Exception):  # OpenAI will raise an error for invalid audio
            await transcription_client.transcribe(
                audio_data=b"",
                filename="empty.wav"
            )