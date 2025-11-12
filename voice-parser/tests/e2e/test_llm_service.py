import pytest
import os
from dotenv import load_dotenv
from voice_parser.services.llm import LLMClient, MessageIntent
from voice_parser.services.llm.models import JobsToBeDoneDocumentModel
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
        Hey, just wanted to remind myself about the three things I need to do tomorrow for the Johnson bathroom renovation.
        First, I need to call the supplier to order the new fixtures.
        Second, I should finish checking the plumbing layout.
        And third, I want to schedule the inspection with the building department.
        """

        result = await llm_client.structure_full_text(
            transcribed_text,
            message_intent=MessageIntent.JOB_TO_BE_DONE
        )

        # Verify the result is a JobsToBeDoneDocumentModel object
        assert isinstance(result, JobsToBeDoneDocumentModel)

        # Verify all required fields are present and non-empty
        assert result.summary
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

        assert result.job
        assert isinstance(result.job, str)
        assert len(result.job) > 0

        assert result.context
        assert isinstance(result.context, str)
        assert len(result.context) > 0

        assert result.action_items
        assert isinstance(result.action_items, list)
        assert len(result.action_items) >= 3  # Should detect the 3 mentioned tasks
