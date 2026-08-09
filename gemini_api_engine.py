"""
Gemini Vision API Engine for Screen Tip AI.

This module integrates official Google Gemini Vision API via `google-genai` SDK
using the API key specified in `/home/jom/projects/screen-tip-ai/.env`.

Key Features:
- Ultra-fast ~1-2 second response times.
- Zero browser popups, zero Chrome profile locks.
- Clean multimodal analysis (PIL Image + prompt).
- Markdown formatting with HTML syntax highlighting support for Answerbox (Box 2).

Design Patterns Used:
- Strategy Pattern: Encapsulates API query execution.
- Singleton / Facade Pattern: Shared client management and configuration loading.
"""

import os
import sys
import logging
from typing import Optional, Union, Callable
from PIL import Image
from dotenv import load_dotenv

from logger_config import get_logger

# Configure structured logger for API Engine
logger = get_logger("GeminiAPIEngine")

DEFAULT_ENV_PATH = "/home/jom/projects/screen-tip-ai/.env"
DEFAULT_MODEL = "gemini-flash-latest"
FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-3.6-flash"]


class GeminiAPIError(Exception):
    """Custom exception raised for errors during Gemini API operations."""
    pass


class GeminiAPIEngine:
    """
    Facade class managing official Google Gemini API calls via google-genai SDK.
    
    Attributes:
        env_path (str): Path to .env file containing gemini_key.
        api_key (str): Extracted Gemini API Key.
        client: Initialized genai.Client instance.
    """
    _instance: Optional["GeminiAPIEngine"] = None

    def __init__(self, env_path: str = DEFAULT_ENV_PATH):
        """
        Initialize GeminiAPIEngine and load API key from environment.
        
        Args:
            env_path (str): File path to .env file.
        """
        self.env_path = env_path
        self.api_key = self._load_api_key()
        self.client = None
        self._initialize_client()

    @classmethod
    def get_instance(cls, env_path: str = DEFAULT_ENV_PATH) -> "GeminiAPIEngine":
        """Singleton accessor method."""
        if cls._instance is None:
            cls._instance = GeminiAPIEngine(env_path=env_path)
        return cls._instance

    def _load_api_key(self) -> str:
        """Load API key from .env file or environment variables."""
        logger.info(f"[Step 1/3] Loading Gemini API Key from: {self.env_path}")
        if os.path.exists(self.env_path):
            load_dotenv(self.env_path, override=True)

        key = (
            os.getenv("gemini_key") or 
            os.getenv("GEMINI_KEY") or 
            os.getenv("GEMINI_API_KEY")
        )
        if not key:
            logger.error(f"[Error] Gemini API key not found in {self.env_path}")
            raise GeminiAPIError(f"API key missing in {self.env_path}. Expected 'gemini_key=...'.")
        
        masked_key = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        logger.info(f"[Step 1/3] Successfully loaded Gemini API Key ({masked_key}).")
        return key

    def _initialize_client(self):
        """Initialize Google GenAI SDK client."""
        try:
            from google import genai
            logger.info("[Step 2/3] Initializing Google GenAI Client...")
            self.client = genai.Client(api_key=self.api_key)
            logger.info("[Step 2/3] Google GenAI Client successfully initialized.")
        except Exception as e:
            logger.error(f"[Error] Failed to initialize Google GenAI SDK client: {e}", exc_info=True)
            raise GeminiAPIError(f"SDK Client initialization failure: {e}") from e

    def query_image(
        self, 
        image_input: Union[str, Image.Image], 
        prompt_text: str, 
        status_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Analyze screenshot image and prompt using official Gemini Vision API.
        
        Args:
            image_input (Union[str, Image.Image]): Absolute path to screenshot image or PIL Image object.
            prompt_text (str): Question prompt text instructions.
            status_callback (Optional[Callable[[str], None]]): Callback for UI status updates.
            
        Returns:
            str: Generated solution text formatted in Markdown/HTML.
        """
        if not self.client:
            raise GeminiAPIError("Client uninitialized. Check API key configuration.")

        # Load PIL Image if path string provided
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise GeminiAPIError(f"Screenshot file not found: {image_input}")
            logger.info(f"[Query] Opening image file from path: {image_input}")
            img = Image.open(image_input)
        else:
            img = image_input

        models_to_try = [DEFAULT_MODEL] + FALLBACK_MODELS
        last_exception = None

        for model_name in models_to_try:
            try:
                msg = f"Querying Gemini API ({model_name})..."
                logger.info(f"[Query] {msg}")
                if status_callback:
                    status_callback(msg)

                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[img, prompt_text]
                )

                solution_text = response.text or ""
                logger.info(f"[SUCCESS] Received Gemini Vision API response from model '{model_name}' ({len(solution_text)} characters).")
                
                return self._format_markdown_to_html(solution_text)

            except Exception as e:
                logger.warning(f"[Query Warning] Model '{model_name}' failed: {e}. Trying fallback model...")
                last_exception = e

        logger.error(f"[Query Error] All Gemini API models failed. Last error: {last_exception}", exc_info=True)
        raise GeminiAPIError(f"Gemini API Query Failed: {last_exception}") from last_exception

    @staticmethod
    def _format_markdown_to_html(markdown_text: str) -> str:
        """
        Convert Markdown text to styled HTML for PyQt QTextEdit.
        """
        import re
        html = markdown_text

        # Code block replacement ```python ... ```
        def replace_code_block(match):
            lang = match.group(1) or ""
            code = match.group(2).replace("<", "&lt;").replace(">", "&gt;")
            return (
                f"<div style='background: #090d16; padding: 10px; border-radius: 8px; margin: 8px 0; border: 1px solid rgba(56, 189, 248, 0.3);'>"
                f"<div style='color: #a855f7; font-size: 11px; font-weight: bold; margin-bottom: 4px;'>{lang.upper() if lang else 'CODE'}</div>"
                f"<pre style='color: #38bdf8; font-family: monospace; margin: 0; white-space: pre-wrap;'>{code}</pre>"
                f"</div>"
            )

        html = re.sub(r'```(\w*)\n(.*?)```', replace_code_block, html, flags=re.DOTALL)
        
        # Inline code `code`
        html = re.sub(r'`([^`]+)`', r'<code style="background: #1e293b; color: #38bdf8; padding: 2px 5px; border-radius: 4px;">\1</code>', html)
        
        # Headers ###
        html = re.sub(r'^### (.*?)$', r'<h4 style="color: #38bdf8; margin-top: 10px; margin-bottom: 4px;">\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*?)$', r'<h3 style="color: #a855f7; margin-top: 12px; margin-bottom: 6px;">\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.*?)$', r'<h2 style="color: #ffffff; margin-top: 14px; margin-bottom: 8px;">\1</h2>', html, flags=re.MULTILINE)

        # Bold **text**
        html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)

        # Convert line breaks to paragraphs/br
        html = html.replace('\n', '<br>')

        return html
