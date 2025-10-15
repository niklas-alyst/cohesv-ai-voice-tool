import pytest
import os
from dotenv import load_dotenv
from voice_parser.services.llm import LLMClient, VoiceNoteAnalysis
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
def llm_client(test_openai_settings):
    """Create LLM client with test settings"""
    return LLMClient(settings=test_openai_settings)


class TestLLMClientIntegration:
    """Integration tests for LLM service using real OpenAI API"""

    @pytest.mark.asyncio
    async def test_structure_text_basic_voice_note(self, llm_client):
        """Test structuring a basic voice note transcription"""
        transcribed_text = """
        Hey, just wanted to remind myself about the three things I need to do tomorrow.
        First, I need to call the dentist to schedule my appointment.
        Second, I should finish reviewing the quarterly budget report.
        And third, I want to start planning the team meeting for next week.
        Overall, I'm feeling pretty optimistic about getting these done.
        """

        result = await llm_client.structure_text(transcribed_text)

        # Verify the result is a VoiceNoteAnalysis object
        assert isinstance(result, VoiceNoteAnalysis)

        # Verify all required fields are present and non-empty
        assert result.summary
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

        assert result.topics
        assert isinstance(result.topics, list)
        assert len(result.topics) > 0

        assert result.action_items
        assert isinstance(result.action_items, list)
        assert len(result.action_items) >= 3  # Should detect the 3 mentioned tasks

        assert result.sentiment in ["positive", "neutral", "negative"]
        assert result.sentiment == "positive"  # Text indicates optimism
