"""
Gemini Web Automation Module for Screen Tip AI.

This module provides automated interactions with the Google Gemini Web interface
(https://gemini.google.com/app) without requiring an official API key. It uses
Playwright with your System Google Chrome browser (/usr/bin/google-chrome) and
directly connects to your primary Chrome user profile (~/.config/google-chrome)
so that your active Google login credentials and session cookies are 100% recognized
without any security flags or manual sign-in prompts.

Design Patterns Used:
- Facade Pattern: Simplifies complex Playwright browser interactions into high-level methods.
- Singleton Pattern: Manages a single shared browser automation instance across the app lifecycle.
"""

import os
import sys
import time
import shutil
from typing import Optional, Callable

from logger_config import get_logger, LOG_FILE_PATH

# Proper structured logger for Web Automation Engine
logger = get_logger("GeminiWebAutomator")

# Primary System Google Chrome User Data Directory
PRIMARY_CHROME_PROFILE_DIR = os.path.expanduser("~/.config/google-chrome")
FALLBACK_PROFILE_DIR = os.path.expanduser("~/.screen_tip_gemini_profile")


class GeminiAutomationError(Exception):
    """Custom exception raised for errors encountered during Gemini Web automation."""
    pass


def find_system_chrome_executable() -> Optional[str]:
    """
    Search for system-installed Google Chrome binaries.
    
    Returns:
        Optional[str]: Path to system Chrome binary if found, else None.
    """
    possible_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for path in possible_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            logger.info(f"[Step 1/4] Detected system Chrome executable at: {path}")
            return path
    
    logger.warning("[Step 1/4] System Chrome binary not found in standard paths.")
    return None


def prepare_profile_dir() -> str:
    """
    Determine best profile directory:
    Prefers primary system Chrome directory (~/.config/google-chrome) so existing logins work out of the box.
    If locked or inaccessible, syncs cookies to fallback profile directory.
    
    Returns:
        str: Chosen profile directory path.
    """
    if os.path.exists(PRIMARY_CHROME_PROFILE_DIR):
        logger.info(f"[Step 2/4] Using primary System Chrome profile directory: {PRIMARY_CHROME_PROFILE_DIR}")
        return PRIMARY_CHROME_PROFILE_DIR
    
    logger.info(f"[Step 2/4] Primary System Chrome profile directory not found. Using fallback profile: {FALLBACK_PROFILE_DIR}")
    os.makedirs(FALLBACK_PROFILE_DIR, exist_ok=True)
    return FALLBACK_PROFILE_DIR


class GeminiWebAutomator:
    """
    Facade class managing Playwright browser automation for Google Gemini Web.
    
    Attributes:
        profile_dir (str): Location of persistent browser data directory.
        headless (bool): Run browser without visible window if True.
        is_ready (bool): Engine initialization status flag.
    """
    _instance: Optional["GeminiWebAutomator"] = None

    def __init__(self, profile_dir: Optional[str] = None, headless: bool = False):
        self.profile_dir = profile_dir or prepare_profile_dir()
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.page = None
        self.is_ready = False
        logger.info(f"[Init] Created GeminiWebAutomator instance using profile: {self.profile_dir}")

    @classmethod
    def get_instance(cls, profile_dir: Optional[str] = None, headless: bool = False) -> "GeminiWebAutomator":
        """Singleton accessor method."""
        if cls._instance is None:
            cls._instance = GeminiWebAutomator(profile_dir=profile_dir, headless=headless)
        return cls._instance

    def initialize(self, status_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Pre-warm browser context using System Chrome and verify logged-in state on startup.
        No invalid flags (--no-sandbox removed) to ensure full security and session validity.
        
        Args:
            status_callback (Optional[Callable[[str], None]]): Callback for UI status logging.
            
        Returns:
            bool: True if initialization and login check succeeded.
        """
        try:
            msg = "Pre-warming System Chrome for Gemini Web..."
            logger.info(f"[Step 3/4] {msg}")
            if status_callback:
                status_callback(msg)

            chrome_executable = find_system_chrome_executable()

            from playwright.sync_api import sync_playwright

            logger.info("[Step 3/4] Starting Playwright browser context...")
            self.playwright = sync_playwright().start()

            # Clean Chromium arguments WITHOUT --no-sandbox to preserve Google Auth & anti-bot stealth
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars"
            ]

            launch_kwargs = {
                "user_data_dir": self.profile_dir,
                "headless": self.headless,
                "args": launch_args
            }
            if chrome_executable:
                launch_kwargs["executable_path"] = chrome_executable
                logger.info(f"[Step 3/4] Configured Playwright with System Chrome executable: {chrome_executable}")

            try:
                self.browser = self.playwright.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as launch_err:
                logger.warning(f"[Step 3/4] Failed to launch with primary profile (possibly locked by open Chrome): {launch_err}")
                logger.info(f"[Step 3/4] Retrying with fallback profile: {FALLBACK_PROFILE_DIR}")
                self.profile_dir = FALLBACK_PROFILE_DIR
                os.makedirs(FALLBACK_PROFILE_DIR, exist_ok=True)
                launch_kwargs["user_data_dir"] = FALLBACK_PROFILE_DIR
                self.browser = self.playwright.chromium.launch_persistent_context(**launch_kwargs)

            if len(self.browser.pages) > 0:
                self.page = self.browser.pages[0]
            else:
                self.page = self.browser.new_page()

            msg = "Navigating to https://gemini.google.com/app..."
            logger.info(f"[Step 4/4] {msg}")
            if status_callback:
                status_callback(msg)

            self.page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=60000)
            time.sleep(1.5)

            # Check DOM for authenticated login status
            logger.info("[Step 4/4] Evaluating DOM for authenticated prompt input...")
            if not self.is_logged_in():
                logger.warning("[Step 4/4] Account not authenticated. Prompting user to log in in browser window...")
                if status_callback:
                    status_callback("Action Required: Please log into Google in the browser window...")
                
                try:
                    self.page.wait_for_selector(
                        'div[contenteditable="true"], rich-textarea, textarea', 
                        timeout=180000
                    )
                except Exception as exc:
                    raise GeminiAutomationError("Login wait timeout expired. Please log into Google Gemini and retry.") from exc

            self.is_ready = True
            logger.info("[SUCCESS] System Chrome pre-warmed and logged into Gemini Web!")
            if status_callback:
                status_callback("Gemini Engine Ready (System Chrome Logged In)")
            return True

        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize Gemini Web automator: {e}", exc_info=True)
            self.is_ready = False
            if status_callback:
                status_callback(f"Initialization error: {str(e)}")
            raise GeminiAutomationError(f"Initialization failure: {e}") from e

    def is_logged_in(self) -> bool:
        """
        Check if the current browser session is logged into Gemini Web.
        
        Returns:
            bool: True if prompt input or active user elements are present in DOM.
        """
        if not self.page:
            return False
        try:
            current_url = self.page.url
            if "accounts.google.com" in current_url:
                logger.info("[Check] Redirected to accounts.google.com -> User is not logged in.")
                return False

            prompt_input = self.page.locator('div[contenteditable="true"], rich-textarea, textarea')
            count = prompt_input.count()
            logger.info(f"[Check] Found {count} prompt input elements in DOM.")
            return count > 0
        except Exception as e:
            logger.warning(f"[Check] Exception checking login state: {e}")
            return False

    def upload_and_ask(
        self, 
        image_path: str, 
        prompt_text: str, 
        status_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Upload screenshot image to Gemini Web, submit prompt text, and scrape response.
        
        Args:
            image_path (str): File path to screenshot image.
            prompt_text (str): Prompt text to accompany image.
            status_callback (Optional[Callable[[str], None]]): Callback for UI status logging.
            
        Returns:
            str: Scraped solution HTML content.
        """
        logger.info(f"[Scan Request] Image: {image_path} | Prompt: {prompt_text[:50]}...")
        
        if not self.is_ready or not self.page:
            logger.error("[Scan Error] Automator engine is not initialized.")
            raise GeminiAutomationError("Automator engine uninitialized.")

        if not os.path.exists(image_path):
            logger.error(f"[Scan Error] Screenshot file does not exist: {image_path}")
            raise GeminiAutomationError(f"File not found: {image_path}")

        try:
            if "gemini.google.com" not in self.page.url:
                logger.info("[Scan Step 1/5] Navigating to https://gemini.google.com/app...")
                if status_callback:
                    status_callback("Navigating to Gemini Web...")
                self.page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
                time.sleep(1.0)

            msg = "Uploading screenshot to Gemini..."
            logger.info(f"[Scan Step 2/5] {msg}")
            if status_callback:
                status_callback(msg)

            file_input = self.page.locator('input[type="file"]')
            if file_input.count() > 0:
                logger.info(f"[Scan Step 2/5] Attaching screenshot file via input[type='file']: {image_path}")
                file_input.set_input_files(image_path)
                time.sleep(1.2)
            else:
                logger.warning("[Scan Step 2/5] input[type='file'] not found; attempting file chooser button fallback...")
                upload_btn = self.page.locator('button[aria-label*="Upload"], button[aria-label*="image"], .uploader-button')
                if upload_btn.count() > 0:
                    with self.page.expect_file_chooser() as fc_info:
                        upload_btn.first.click()
                    file_chooser = fc_info.value
                    file_chooser.set_files(image_path)
                    time.sleep(1.2)

            msg = "Entering prompt text into Gemini..."
            logger.info(f"[Scan Step 3/5] {msg}")
            if status_callback:
                status_callback(msg)

            prompt_box = self.page.locator('div[contenteditable="true"], textarea, rich-textarea')
            if prompt_box.count() > 0:
                prompt_box.first.click()
                prompt_box.first.fill(prompt_text)
                time.sleep(0.5)

            msg = "Submitting question to Gemini AI..."
            logger.info(f"[Scan Step 4/5] {msg}")
            if status_callback:
                status_callback(msg)

            send_btn = self.page.locator('button[aria-label*="Send"], button.send-button, .send-button-container button')
            if send_btn.count() > 0 and send_btn.first.is_enabled():
                logger.info("[Scan Step 4/5] Clicking Send button...")
                send_btn.first.click()
            else:
                logger.info("[Scan Step 4/5] Pressing Enter key to submit...")
                prompt_box.first.press("Enter")

            msg = "Gemini is generating solution..."
            logger.info(f"[Scan Step 5/5] {msg}")
            if status_callback:
                status_callback(msg)

            self.page.wait_for_selector(
                '.model-response-text, message-content, model-response, .markdown', 
                timeout=45000
            )

            time.sleep(3.0)

            responses = self.page.locator('message-content, model-response, .model-response-text, .markdown').all()
            if responses:
                latest_html = responses[-1].inner_html()
                logger.info(f"[SUCCESS] Scraped Gemini response successfully ({len(latest_html)} characters).")
                return latest_html
            
            raise GeminiAutomationError("Model response element found but empty.")

        except Exception as e:
            logger.error(f"[Scan Failure] Exception during upload_and_ask: {e}", exc_info=True)
            raise GeminiAutomationError(f"Scan failed: {e}") from e

    def close(self):
        """Safely close browser context and stop Playwright."""
        try:
            logger.info("[Shutdown] Closing System Chrome browser session...")
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self.is_ready = False
            logger.info("[Shutdown] GeminiWebAutomator shutdown complete.")
        except Exception as e:
            logger.warning(f"[Shutdown] Error while closing automator: {e}")
