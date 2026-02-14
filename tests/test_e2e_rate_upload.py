import os
import sys
import time
import subprocess
from pathlib import Path
import requests
import pytest
from PIL import Image

import test_prompts_manager as tpm

pytest.importorskip("playwright")  # skip if playwright not installed


def _wait_for_http(url: str, timeout: float = 30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def make_image(path: Path):
    img = Image.new("RGB", (160, 120), (120, 30, 60))
    img.save(path, format="JPEG")


def test_rate_page_allows_upload_from_rate_ui(tmp_path, monkeypatch):
    """End-to-end: open the app, go to Rate page, upload an image for a single-image test

    - Starts a Streamlit instance in a subprocess
    - Uses Playwright (headless Chromium) to drive the browser
    - Verifies the uploaded file is saved under profile_results/baseline

    This test is skipped automatically if Playwright is not installed in the environment.
    """
    # Environment: force local storage backend for test isolation
    monkeypatch.setenv("USE_S3", "false")
    # Prepare a small image to upload
    local_img = tmp_path / "upload.jpg"
    make_image(local_img)

    # Choose a single-image test that exists in test_prompts.json
    test_title = "Night Urban Traffic"
    test_obj = tpm.get_test_by_title(test_title)
    assert test_obj and test_obj.get("guid"), "expected test to exist in test_prompts.json"
    guid = test_obj.get("guid")

    # Start Streamlit app as a subprocess (uses the current Python interpreter)
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update({"USE_S3": "false"})

    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "midjourney_profile_tester.py", "--server.port", "8501"],
        cwd=str(project_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        assert _wait_for_http("http://127.0.0.1:8501", timeout=30.0), "Streamlit did not start in time"

        # Use Playwright sync API (import guarded by pytest.importorskip above)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://127.0.0.1:8501", timeout=60000)

            # Click the Rate nav button
            page.get_by_role("button", name="⭐ Rate").click()
            page.wait_for_selector("text=Test Ratings", timeout=10000)

            # Expand the specific test expander (missing image state expected)
            # The Rate page shows an expander like: "📷 Night Urban Traffic - ⚠️ Image Not Uploaded"
            expander_locator = page.locator(f"div:has-text(\"{test_title}\")")
            expander_locator.first.click()

            # Inside the expander, find the file input and set the file
            file_input = expander_locator.locator('input[type="file"]')
            # Ensure we found an input
            assert file_input.count() >= 1, "file input not found inside Rate expander"
            file_input.first.set_input_files(str(local_img))

            # Wait for the server to save the uploaded image to disk
            expected_path = project_root / "profile_results" / "baseline" / f"baseline_{guid}.jpg"
            deadline = time.time() + 10
            while time.time() < deadline:
                if expected_path.exists():
                    break
                time.sleep(0.25)

            assert expected_path.exists(), f"Uploaded image was not saved to {expected_path}"

            # Verify the preview image appears in the expander
            img_locator = expander_locator.locator("img")
            img_locator.first.wait_for(state="visible", timeout=5000)

            browser.close()

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

        # Cleanup saved file
        saved = project_root / "profile_results" / "baseline" / f"baseline_{guid}.jpg"
        try:
            if saved.exists():
                saved.unlink()
        except Exception:
            pass
