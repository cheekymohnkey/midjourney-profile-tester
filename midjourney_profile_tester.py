#!/usr/bin/env python3
"""Streamlit app to generate MidJourney profile test prompts."""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from io import StringIO, BytesIO
from PIL import Image
from storage_helpers import Path, load_image, save_image
import base64
import os
from st_img_pastebutton import paste
import hashlib
from services.test_data_service import get_test_data_service
tpm = get_test_data_service()
from dotenv import load_dotenv
from storage import get_storage
from services.analysis import score_v1_from_checks
from services.image_utils import embed_image_data
import json
from streamlit_sortables import sort_items
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import datetime
import random
import re

# Module logger
from services.logger_config import init_logging

# Initialize centralized logging (single stdout handler)
init_logging()
logger = logging.getLogger(__name__)

# Ensure uncaught exceptions are logged to console
import sys
def _log_unhandled_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Let default handler run for KeyboardInterrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = _log_unhandled_exception

# Wrap Streamlit's error/exception displayors to also log to console
try:
    _st_error_orig = st.error
    def _st_error_with_log(msg, *args, **kwargs):
        try:
            logger.error("Streamlit error: %s", msg)
        except Exception:
            pass
        return _st_error_orig(msg, *args, **kwargs)
    st.error = _st_error_with_log
except Exception:
    pass

try:
    _st_exception_orig = st.exception
    def _st_exception_with_log(exc, *args, **kwargs):
        try:
            logger.exception("Streamlit exception: %s", exc)
        except Exception:
            pass
        return _st_exception_orig(exc, *args, **kwargs)
    st.exception = _st_exception_with_log
except Exception:
    pass

# Load environment variables from .env file
load_dotenv()

# Analysis prompt version - increment when making significant changes to rating logic
ANALYSIS_PROMPT_VERSION = "2.3-signature"  # v2.3: Enhanced commentary to capture profile's aesthetic signature (tone, color, texture) for better DNA and recommendations

st.set_page_config(page_title="MidJourney Profile Tester", layout="wide")

# Load palette controls from URL query params (allows iframe controls to set them)
try:
    qp = st.experimental_get_query_params()
    for k, v in qp.items():
        if k.startswith('palette_source_'):
            # value may be a list
            val = v[0] if isinstance(v, list) and v else (v if not isinstance(v, list) else '')
            if val:
                st.session_state.setdefault(k, val)
        if k.startswith('palette_norm_'):
            val = v[0] if isinstance(v, list) and v else (v if not isinstance(v, list) else '')
            if val:
                st.session_state.setdefault(k, True if str(val) in ('1', 'true', 'True') else False)
except Exception:
    pass


def get_test_token(test_name: str) -> str:
    """Return GUID token for a test title when available, otherwise a safe title.

    Tries exact match, then case-insensitive match, then id match. Falls back to
    replacing spaces/slashes with underscores.
    """
    try:
        tests = tpm.list_tests()
        # Exact match
        for t in tests:
            # Prefer explicit `id` (migration target) then `guid` for compatibility
            if t.get('title') == test_name and (t.get('id') or t.get('guid')):
                return t.get('id') if t.get('id') else t.get('guid')
        # Case-insensitive trimmed match
        key = test_name.strip().lower()
        for t in tests:
            if t.get('title') and t.get('title').strip().lower() == key and (t.get('id') or t.get('guid')):
                return t.get('id') if t.get('id') else t.get('guid')
        # Match by id (safe id) or guid
        for t in tests:
            if t.get('id') and t.get('id') == test_name:
                return t.get('id')
            if t.get('guid') and t.get('guid') == test_name:
                return t.get('guid')
    except Exception:
        pass
    return test_name.replace(' ', '_').replace('/', '_')


def canonical_test_key(test_obj: dict, test_name: str) -> str:
    """Return canonical key for a test object: prefer `id`, then `guid`, else safe title."""
    if test_obj:
        if test_obj.get('id'):
            return test_obj.get('id')
        if test_obj.get('guid'):
            return test_obj.get('guid')
    return test_name.replace(' ', '_').replace('/', '_')

# Global parameters persistence file
GLOBAL_PARAMS_FILE = Path("global_params.json")


def default_global_params() -> str:
    """Return a sensible default global params string with a randomized seed."""
    return f"--ar 16:9 --quality 4 --seed {random.randint(0, 2**32-1)}"

def load_global_params():
    """Load global parameters from file, return default if not found."""
    try:
        from storage import get_storage
        storage = get_storage()
        data = storage.read_json(str(GLOBAL_PARAMS_FILE)) or {}
        return data.get('global_params', default_global_params())
    except Exception:
        pass
    return default_global_params()

def save_global_params(params):
    """Save global parameters to file."""
    try:
        from storage import get_storage
        storage = get_storage()
        storage.write_json(str(GLOBAL_PARAMS_FILE), {'global_params': params})
    except Exception:
        pass

def filter_seed_from_params(params_string):
    """Remove --seed parameter from a parameter string."""
    if not params_string:
        return params_string
    parts = params_string.split()
    filtered_parts = []
    skip_next = False
    for i, part in enumerate(parts):
        if skip_next:
            skip_next = False
            continue
        if part == '--seed':
            skip_next = True  # Skip the next part (the seed value)
            continue
        filtered_parts.append(part)
    return ' '.join(filtered_parts)

def optimize_image_for_storage(img, max_size=1024, quality=90):
    """
    Optimize an image for storage: resize to max dimension and convert to JPEG.
    
    Args:
        img: PIL Image object
        max_size: Maximum dimension (width or height)
        quality: JPEG quality (1-100)
    
    Returns:
        Optimized PIL Image in RGB mode
    """
    # Calculate new dimensions maintaining aspect ratio
    width, height = img.size
    if max(width, height) > max_size:
        ratio = max_size / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # Convert to RGB for JPEG (handle transparency)
    if img.mode in ('RGBA', 'P', 'LA'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        if 'A' in img.mode:
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    return img


def _hue_to_hex(hue_name: str) -> str:
    map_tbl = {
        'teal/cyan': '#2aa6a0', 'teal': '#2aa6a0', 'cyan': '#2aa6a0',
        'yellow': '#e6c85b', 'red': '#e04f4f', 'green': '#4fc37a',
        'blue': '#3498db', 'orange': '#d98b3c', 'magenta': '#b84fae',
        'pink': '#e08aa6', 'purple': '#7b61ff', 'brown': '#8b5a2b',
        'black': '#0b0b0b', 'white': '#ffffff', 'gray': '#9aa0a6'
    }
    return map_tbl.get(hue_name.lower(), '#cfcfd0')


def render_palette_swatch(palette, width: int = 260, height: int = 80, source: str = None, normalized: bool = False, test_key: str = None):
    """Render a compact palette swatch via Streamlit components.

    `palette` may be:
    - a dict containing `dominant_hexs` and/or `accent_hexs` (lists of hex strings),
    - a dict with `dominant_hues`/`accent_hues` (names), or
    - a free-form string describing the palette.
    """
    try:
        dom_hexs = []
        acc_hexs = []

        if isinstance(palette, dict):
            dom_hexs = palette.get('dominant_hexs') or []
            acc_hexs = palette.get('accent_hexs') or []
            if not dom_hexs and palette.get('dominant_hues'):
                dom_hexs = [_hue_to_hex(h) for h in palette.get('dominant_hues')[:2]]
            if not acc_hexs and palette.get('accent_hues'):
                acc_hexs = [_hue_to_hex(h) for h in palette.get('accent_hues')[:2]]
        else:
            text = str(palette or '')
            for k in ['teal', 'cyan', 'yellow', 'red', 'green', 'blue', 'orange', 'magenta', 'pink', 'purple']:
                if k in text.lower():
                    if k in ('red', 'green', 'magenta', 'pink', 'orange'):
                        acc_hexs.append(_hue_to_hex(k))
                    else:
                        dom_hexs.append(_hue_to_hex(k))

        if not dom_hexs:
            dom_hexs = [_hue_to_hex('teal'), _hue_to_hex('yellow')]
        if not acc_hexs:
            acc_hexs = [_hue_to_hex('red'), _hue_to_hex('green')]

        while len(dom_hexs) < 2:
            dom_hexs.append(dom_hexs[0])
        while len(acc_hexs) < 2:
            acc_hexs.append(acc_hexs[0])

        norm_text = "Adjusted" if normalized else "Raw"
        src_text = source if source else "Source: analyzer/sample"

        # If a test_key is provided, embed lightweight controls inside the iframe
        controls_html = ""
        if test_key:
            esc_key = str(test_key).replace('"', '\\"')
            sel_val = source or "OpenAI (analyzer)"
            chk_checked = 'checked' if normalized else ''
            controls_html = (
                "<div style=\"margin-bottom:8px;font-size:13px;color:#374151\">Controls: </div>"
                "<div style=\"display:flex;gap:8px;align-items:center;margin-bottom:8px\">"
                "<select id=\"ps\" style=\"font-size:13px;padding:6px;border-radius:6px\">"
                f"<option{' selected' if sel_val.startswith('OpenAI') else ''}>OpenAI (analyzer)</option>"
                f"<option{' selected' if sel_val.startswith('k-means') else ''}>k-means</option>"
                f"<option{' selected' if sel_val.startswith('median-cut') else ''}>median-cut</option>"
                "</select>"
                "<label style=\"font-size:13px;margin-left:6px;display:flex;align-items:center;gap:6px\">"
                f"<input id=\"pn\" type=\"checkbox\" {chk_checked}/> Adjust"
                "</label>"
                "</div>"
                "<script>"
                "const applyToParent = ()=>{"
                "try{"
                "const sel = document.getElementById('ps').value;"
                "const chk = document.getElementById('pn').checked ? '1' : '0';"
                "const params = new URLSearchParams(window.top.location.search);"
                "params.set('palette_source_' + encodeURIComponent('" + esc_key + "'), sel);"
                "params.set('palette_norm_' + encodeURIComponent('" + esc_key + "'), chk);"
                "window.top.location.search = '?' + params.toString();"
                "}catch(e){console.log(e)}"
                "}"
                "document.getElementById('ps').addEventListener('change', applyToParent);"
                "document.getElementById('pn').addEventListener('change', applyToParent);"
                "</script>"
            )

        html = f"""
<div style="font-family:Inter, system-ui, Arial; max-width:{width}px">
    <div style="margin-bottom:6px;font-weight:600;font-size:14px">Palette preview</div>
    <div style="margin-bottom:6px;font-size:12px;color:#6b7280">{src_text} • {norm_text}</div>
                                        {controls_html}
    <div style="display:flex;gap:8px;align-items:center">
        <div style="flex:1;display:flex;border-radius:10px;overflow:hidden;height:{height}px;box-shadow:0 6px 18px rgba(11,18,32,0.06)">
            <div style="flex:1;background:{dom_hexs[0]}"></div>
            <div style="flex:1;background:{dom_hexs[1]}"></div>
        </div>
        <div style="width:84px;display:flex;flex-direction:column;gap:8px">
            <div style="height:{int(height/2)-6}px;border-radius:8px;background:{acc_hexs[0]};box-shadow:0 4px 10px rgba(11,18,32,0.06)"></div>
            <div style="height:{int(height/2)-6}px;border-radius:8px;background:{acc_hexs[1]};box-shadow:0 4px 10px rgba(11,18,32,0.06)"></div>
        </div>
    </div>
</div>
"""

        # Allocate extra iframe height when the inline controls are present so they aren't clipped
        iframe_extra = 80 if controls_html else 24
        iframe_height = height + iframe_extra
        components.html(html, height=iframe_height, scrolling=False)
    except Exception:
        return

def find_image_file(output_dir, profile_id, test_name, image_num=None):
    """
    Find an image file, checking both .jpg and .png extensions.
    Returns Path object if found, None otherwise.
    
    Uses cached file listing to avoid individual S3 HEAD requests.
    
    Args:
        output_dir: Directory containing images
        profile_id: Profile ID (or 'baseline')
        test_name: Test name from DataFrame
        image_num: For multi-image tests, the image number (1-8). None for single-image tests.
    
    Returns:
        Path object if file exists, None otherwise
    """
    # Prefer test GUID when available (new migration), otherwise fall back to safe title
    token = get_test_token(test_name)

    # Also consider legacy safe-title filenames in case profile still uses them
    safe_name = test_name.replace(' ', '_').replace('/', '_')
    candidates = []
    if image_num:
        candidates.append(f"{profile_id}_{token}_{image_num}")
        if safe_name != token:
            candidates.append(f"{profile_id}_{safe_name}_{image_num}")
    else:
        candidates.append(f"{profile_id}_{token}")
        if safe_name != token:
            candidates.append(f"{profile_id}_{safe_name}")

    # Get cached list of filenames for this profile
    existing_files = get_profile_image_files(profile_id)

    # Check candidates in order for .jpg then .png
    for base_name in candidates:
        jpg_filename = f"{base_name}.jpg"
        if jpg_filename in existing_files:
            return output_dir / jpg_filename
        png_filename = f"{base_name}.png"
        if png_filename in existing_files:
            return output_dir / png_filename

    return None

@st.cache_data(ttl=60, hash_funcs={"storage.S3Storage": lambda _: None, "storage.LocalStorage": lambda _: None})
def get_all_profile_analyses():
    """Load all profile analyses once and cache for 60 seconds.

    Delegates to `profile_analyses_manager` which implements per-file
    metadata-aware caching and logging.
    """
    from profile_analyses_manager import load_all_analyses
    return load_all_analyses()

@st.cache_data(ttl=30, hash_funcs={"storage.S3Storage": lambda _: None, "storage.LocalStorage": lambda _: None})
def count_profile_images(profile_id):
    """Count images in a profile directory with caching."""
    storage = get_storage()
    output_path = f"profile_results/{profile_id if profile_id else 'baseline'}"
    jpg_files = storage.list_files(output_path, "*.jpg")
    png_files = storage.list_files(output_path, "*.png")
    return len(jpg_files) + len(png_files)

@st.cache_data(ttl=30, hash_funcs={"storage.S3Storage": lambda _: None, "storage.LocalStorage": lambda _: None})
def get_profile_image_files(profile_id):
    """Get set of all image filenames in a profile directory (cached)."""
    storage = get_storage()
    output_path = f"profile_results/{profile_id if profile_id else 'baseline'}"
    jpg_files = storage.list_files(output_path, "*.jpg")
    png_files = storage.list_files(output_path, "*.png")
    # Extract just the filenames (not full paths) into a set for fast lookup
    filenames = set()
    for file_path in jpg_files + png_files:
        filename = file_path.split('/')[-1]
        filenames.add(filename)
    return filenames

@st.cache_data(ttl=60, hash_funcs={"storage.S3Storage": lambda _: None, "storage.LocalStorage": lambda _: None})
def get_existing_profile_ids():
    """Get list of profile IDs with caching to avoid expensive list operations."""
    storage = get_storage()
    profile_dirs = set()

    # Profiles that have result folders (images)
    all_result_files = storage.list_files("profile_results", "*")
    for file_path in all_result_files:
        parts = file_path.split('/')
        if len(parts) >= 2 and parts[1] and parts[1] != 'baseline':
            profile_dirs.add(parts[1])

    # Also include profiles that only have an analysis JSON
    analysis_files = storage.list_files("profile_analyses", "*_analysis.json")
    for af in analysis_files:
        # af is like 'profile_analyses/<profile>_analysis.json' or 'profile_analyses/baseline_analysis.json'
        parts = af.split('/')
        if not parts:
            continue
        filename = parts[-1]
        if not filename.endswith('_analysis.json'):
            continue
        profile_id = filename[:-len('_analysis.json')]
        if profile_id and profile_id != 'baseline' and not profile_id.startswith('test_'):
            profile_dirs.add(profile_id)

    return sorted(list(profile_dirs))

@st.cache_data(ttl=60, hash_funcs={"storage.S3Storage": lambda _: None, "storage.LocalStorage": lambda _: None})
def get_profile_completion_data(profile_list, test_names_tuple, test_count):
    """Cache profile completion status to avoid repeated JSON reads."""
    profile_analyses_dir = Path("profile_analyses")
    versions = {}
    completion = {}
    from services.results_data_service import get_results_data_service
    rds = get_results_data_service()
    for profile in profile_list:
        try:
            data = rds.read_analysis(profile) or {}
            version = data.get('analysis_version', 'unknown')
            versions[profile] = version
            # Check completion - only count ratings for current tests
            ratings = data.get('ratings', {})
            test_names_set = set(test_names_tuple)
            valid_ratings = [t for t in ratings.keys() if t in test_names_set]
            completion[profile] = (len(valid_ratings) == test_count)
        except Exception:
            versions[profile] = 'unknown'
            completion[profile] = False
    return versions, completion

@st.cache_data(ttl=300, max_entries=100)
def load_image_cached(image_path_str):
    """Load and cache image for 5 minutes. Limits to 100 images in cache."""
    return load_image(image_path_str)


# UI helper: set session-state flags after an AI rating completes
def _set_ai_rated_session_flags(test_name: str, message: str | None = None):
    """Set Streamlit session_state flags used by the UI after an AI rating.

    - `just_ai_rated_{test_name}` is set to True so UI expanders stay open.
    - `ai_rated_message_{test_name}` is set to a short success message.

    Centralized and unit-testable helper.
    """
    import streamlit as st
    st.session_state[f'just_ai_rated_{test_name}'] = True
    st.session_state[f'ai_rated_message_{test_name}'] = message or f"✨ AI rating completed for {test_name}"

# Helper function to load tests as DataFrame
def load_tests_df(status_filter='current'):
    """Load tests from JSON and return as DataFrame."""
    tests = tpm.list_tests(status_filter=status_filter)
    if not tests:
        return pd.DataFrame(columns=['Section', 'Title', 'Prompt', 'Parameter Values'])
    df = pd.DataFrame(tests)
    df = df.rename(columns={
        'title': 'Title',
        'prompt': 'Prompt',
        'section': 'Section',
        'params': 'Parameter Values'
    })
    return df[['Section', 'Title', 'Prompt', 'Parameter Values']]

def render_test_upload(profile_id, test_name, output_dir, idx, image_num=None, show_preview=True):
    """Handle individual test image upload.
    
    Args:
        image_num: For multi-image tests, the image number (1-8). None for single-image tests.
    """
    # Display title (optional - Tests page grid hides per-profile titles)
    if show_preview:
        if image_num:
            st.markdown(f"**{test_name} #{image_num}**")
        else:
            st.markdown(f"**{test_name}**")
    
    # Create token for filename: prefer test GUID if available, else safe title
    try:
        test_obj = tpm.get_by_title(test_name)
        token = canonical_test_key(test_obj, test_name)
    except Exception:
        token = test_name.replace(' ', '_').replace('/', '_')
    if image_num:
        filename = f"{profile_id if profile_id else 'baseline'}_{token}_{image_num}.jpg"
    else:
        filename = f"{profile_id if profile_id else 'baseline'}_{token}.jpg"
    filepath = output_dir / filename
    
    # Check if image exists (handles both .jpg and .png)
    existing_filepath = find_image_file(output_dir, profile_id if profile_id else 'baseline', test_name, image_num)
    if existing_filepath is not None:
        # Optionally show image preview (Tests page may prefer a compact grid instead)
        if show_preview:
            img_display = load_image_cached(str(existing_filepath))
            st.image(img_display, width='stretch')
            display_profile = profile_id if profile_id else 'baseline'
            delete_key = f"delete_{idx}_{image_num}" if image_num else f"delete_{idx}"

            if st.button(f"🗑️ Delete ({display_profile})", key=delete_key):
                # Use storage API to delete so S3 backend works
                try:
                    get_storage().delete(str(existing_filepath))
                except Exception:
                    try:
                        existing_filepath.unlink()
                    except Exception:
                        pass

                # Clear the analysis rating for this test (use ResultsDataService)
                from services.results_data_service import get_results_data_service
                rds = get_results_data_service()
                aid = profile_id if profile_id else 'baseline'
                analysis_data = rds.read_analysis(aid) or {}
                try:
                    from profile_analyses_manager import invalidate
                except Exception:
                    invalidate = None
                if analysis_data and "ratings" in analysis_data:
                    # Remove rating stored under GUID or legacy title key
                    try:
                        test_obj = tpm.get_by_title(test_name)
                    except Exception:
                        test_obj = None
                    rating_key = canonical_test_key(test_obj, test_name)
                    removed = False
                    if rating_key in analysis_data.get('ratings', {}):
                        try:
                            del analysis_data['ratings'][rating_key]
                            removed = True
                        except Exception:
                            pass
                    # Also remove legacy title-key if present
                    if test_name in analysis_data.get('ratings', {}):
                        try:
                            del analysis_data['ratings'][test_name]
                            removed = True
                        except Exception:
                            pass
                    if removed:
                        rds.write_analysis(aid, analysis_data)
                        try:
                            if invalidate:
                                invalidate(str(Path("profile_analyses") / f"{aid}_analysis.json"))
                        except Exception:
                            pass

                # Clear caches so upload controls appear on rerun
                try:
                    get_profile_image_files.clear()
                except Exception:
                    pass
                try:
                    count_profile_images.clear()
                except Exception:
                    pass
                try:
                    load_image_cached.clear()
                except Exception:
                    pass

                st.rerun()
    else:
        # Paste button and file uploader
        paste_col, upload_col = st.columns([1, 1])

        display_profile = profile_id if profile_id else 'baseline'
        paste_key = f"paste_{profile_id if profile_id else 'baseline'}_{idx}_{image_num}" if image_num else f"paste_{profile_id if profile_id else 'baseline'}_{idx}"
        upload_key = f"upload_{profile_id if profile_id else 'baseline'}_{idx}_{image_num}" if image_num else f"upload_{profile_id if profile_id else 'baseline'}_{idx}"

        with paste_col:
            image_data = paste(
                label=f"📋 Paste ({display_profile})",
                key=paste_key
            )
            
            if image_data is not None:
                # Avoid processing the same pasted image repeatedly across reruns
                try:
                    header, encoded = image_data.split(",", 1)
                except Exception:
                    header = None
                    encoded = None

                if encoded:
                    h = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
                    session_hash_key = f"paste_hash_{paste_key}"
                    # If we've seen this paste before, verify the expected file exists.
                    if st.session_state.get(session_hash_key) == h:
                        existing_files = get_profile_image_files(profile_id if profile_id else 'baseline')
                        expected_jpg = f"{profile_id if profile_id else 'baseline'}_{token}_{image_num}.jpg" if image_num else f"{profile_id if profile_id else 'baseline'}_{token}.jpg"
                        expected_png = expected_jpg[:-4] + '.png'
                        if expected_jpg in existing_files or expected_png in existing_files:
                            # File is present but UI may be stale: refresh caches and rerun to show it
                            get_profile_image_files.clear()
                            count_profile_images.clear()
                            load_image_cached.clear()
                            st.success("✅ Pasted!")
                            st.rerun()
                        # Otherwise fall through and re-process the paste (hash likely stale)
                    # Process and record hash
                    binary_data = base64.b64decode(encoded)
                    bytes_data = BytesIO(binary_data)
                    img = Image.open(bytes_data)
                    # Optimize and save as JPEG
                    img = optimize_image_for_storage(img)
                    filepath = filepath.with_suffix('.jpg')
                    save_image(filepath, img, format='JPEG', quality=90)
                    # Clear cache so new image is detected
                    get_profile_image_files.clear()
                    count_profile_images.clear()
                    load_image_cached.clear()
                    try:
                        st.session_state[session_hash_key] = h
                    except Exception:
                        pass
                    # Clear the paste widget state so the same image isn't reprocessed as a new component value
                    try:
                        if paste_key in st.session_state:
                            del st.session_state[paste_key]
                    except Exception:
                        pass
                    st.success("✅ Pasted!")
                    st.rerun()
        
        with upload_col:
            uploaded = st.file_uploader(
                f"📤 Upload ({display_profile})",
                type=['png', 'jpg', 'jpeg', 'webp'],
                key=upload_key,
                help="Drag & drop or click to browse",
                label_visibility="collapsed"
            )
            
            if uploaded:
                # Compute a hash for the uploaded bytes to avoid double-processing
                try:
                    data_bytes = uploaded.getvalue()
                except Exception:
                    data_bytes = None

                uploaded_hash_key = f"upload_hash_{upload_key}"
                if data_bytes:
                    uh = hashlib.sha256(data_bytes).hexdigest()
                    # If we've seen this upload before, verify the expected file exists
                    if st.session_state.get(uploaded_hash_key) == uh:
                        existing_files = get_profile_image_files(profile_id if profile_id else 'baseline')
                        expected_jpg = f"{profile_id if profile_id else 'baseline'}_{token}_{image_num}.jpg" if image_num else f"{profile_id if profile_id else 'baseline'}_{token}.jpg"
                        expected_png = expected_jpg[:-4] + '.png'
                        if expected_jpg in existing_files or expected_png in existing_files:
                            get_profile_image_files.clear()
                            count_profile_images.clear()
                            load_image_cached.clear()
                            st.success("✅ Saved!")
                            st.rerun()
                        # Otherwise fall through and re-process the upload (hash likely stale)
                    img = Image.open(BytesIO(data_bytes))
                    img = optimize_image_for_storage(img)
                    filepath = filepath.with_suffix('.jpg')
                    save_image(filepath, img, format='JPEG', quality=90)
                    # Clear cache so new image is detected
                    get_profile_image_files.clear()
                    count_profile_images.clear()
                    load_image_cached.clear()
                    try:
                        st.session_state[uploaded_hash_key] = uh
                    except Exception:
                        pass
                    # Clear the uploader widget state to avoid reprocessing on rerun
                    try:
                        if upload_key in st.session_state:
                            del st.session_state[upload_key]
                    except Exception:
                        pass
                    st.success("✅ Saved!")
                    st.rerun()

def batch_ai_rate_images(uploaded_tests, profile_id, profile_label="", existing_ratings=None):
    """
    Send all uploaded images to OpenAI for batch analysis.
    
    Args:
        uploaded_tests: List of tuples (test_name, filepath, row)
        profile_id: Profile ID being analyzed
        profile_label: Optional profile label suggestion
        existing_ratings: Dict of already-rated tests to skip
    
    Returns:
        Dict with profile_label, profile_dna, and ratings
    """
    # Delegate to service implementation
    from services.batch_runner import batch_ai_rate_images as _batch_impl
    return _batch_impl(uploaded_tests, profile_id, profile_label=profile_label, existing_ratings=existing_ratings)

def finalize_profile_summary(profile_id, analysis_data):
    """
    Regenerate Profile DNA and Label based on ALL completed ratings.
    Called when all tests are rated.
    """
    from openai import OpenAI
    import config
    
    api_key = config.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env file")
    
    client = OpenAI(api_key=api_key)
    
    # Prepare summary of all ratings
    ratings_summary = []
    for test_name, rating in analysis_data.get("ratings", {}).items():
        ratings_summary.append(f"- {test_name}: {rating['affinity']} (score: {rating['score']}/10)")
    
    summary_text = "\n".join(ratings_summary)
    
    # Ask AI to generate final profile summary
    try:
        from services.ai_client import chat_completion_parse_json
        from services.gpt_config import DEFAULT_MODEL, DEFAULT_MAX_COMPLETION_TOKENS

        parsed, response_text, response_obj = chat_completion_parse_json(
            client=client,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing artistic profiles and identifying aesthetic patterns."
                },
                {
                    "role": "user",
                    "content": f"""Based on these {len(ratings_summary)} test results for MidJourney profile '{profile_id}', provide:

1. **Profile Label**: A concise 2-4 word aesthetic label (e.g., "Moody Urban Explorer", "Vibrant Nature Maximalist")

2. **Profile DNA**: 5-10 distinctive traits that define this profile's aesthetic strengths, weaknesses, and tendencies. Include color palette preferences if evident (e.g., "Prefers warm/moody tones", "Strong with vibrant/saturated colors", "Excels at muted/desaturated palettes", "Gravitates toward neon/dark contrasts").

Test Results:
{summary_text}

Return as JSON:
```json
{{
  "profile_label": "Your Label Here",
  "profile_dna": ["trait1", "trait2", ...]
}}
```"""
                }
            ],
            model=DEFAULT_MODEL,
            max_completion_tokens=DEFAULT_MAX_COMPLETION_TOKENS,
        )
        if parsed is None:
            raise ValueError("Failed to parse JSON from finalize_profile_summary response")
        result = parsed
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        import json
        result = json.loads(response_text)
        
        # Update analysis data
        analysis_data["profile_label"] = result.get("profile_label", "")
        # User preference: keep manual traits first, drop previously AI-generated traits,
        # then append new AI-generated traits (so manual traits always stick and come first).
        new_dna = result.get("profile_dna", []) or []
        manual_list = analysis_data.get("profile_dna_manual", []) or []
        # Build merged list: manual traits first (in their stored order), then new AI traits not already present
        merged_dna = list(manual_list)
        for trait in new_dna:
            if trait not in merged_dna:
                merged_dna.append(trait)
        analysis_data["profile_dna"] = merged_dna
        
        # Rebuild affinity summary from all ratings
        affinity_summary = {
            "native_fit": [],
            "workable": [],
            "resistant": []
        }
        for test_name, rating_data in analysis_data.get("ratings", {}).items():
            affinity = rating_data.get('affinity', '')
            if affinity in affinity_summary:
                affinity_summary[affinity].append(test_name)
        
        analysis_data["affinity_summary"] = affinity_summary
        
        # Save the updated analysis with profile label, DNA, and affinity summary
        save_analysis(profile_id, analysis_data)
        
        return True
        
    except Exception as e:
        st.error(f"Failed to generate profile summary: {e}")
        return False

def save_analysis(profile_id, analysis_data):
    """Save analysis data to JSON file with version tracking."""
    import json
    # Add version to analysis data before saving
    analysis_data['analysis_version'] = ANALYSIS_PROMPT_VERSION
    # Use ResultsDataService to persist analysis and handle backups
    from services.results_data_service import get_results_data_service
    rds = get_results_data_service()
    return rds.write_analysis(profile_id, analysis_data, make_backup=True)

# Custom CSS to make code block copy button always visible and highlight when copied
st.markdown("""
<style>
    /* Force copy button to always be visible - override all animations/transitions */
    button[data-testid="stCodeCopyButton"] {
        opacity: 1 !important;
        visibility: visible !important;
        display: block !important;
        transform: none !important;
        transition: none !important;
        animation: none !important;
    }
    /* Make it larger and more prominent */
    button[data-testid="stCodeCopyButton"] {
        margin: -6px 0 !important;
        width: 36px !important;
        height: 36px !important;
    }
    button[data-testid="stCodeCopyButton"] svg {
        width: 20px !important;
        height: 20px !important;
    }
    /* Position the parent container in the top right */
    .st-emotion-cache-chk1w8 {
        opacity: 1 !important;
        visibility: visible !important;
        display: flex !important;
        position: absolute !important;
        top: 8px !important;
        right: 8px !important;
        z-index: 10 !important;
    }
    /* Make sure the code container is positioned relatively */
    .stCode {
        position: relative !important;
        transition: all 0.3s ease !important;
    }
    /* Highlight style when copied */
    .stCode.copied {
        background: linear-gradient(90deg, rgba(40, 167, 69, 0.2) 0%, rgba(40, 167, 69, 0.1) 100%) !important;
        border-left: 4px solid #28a745 !important;
        padding-left: 12px !important;
    }
    .stCode.copied code {
        background: transparent !important;
    }
</style>
<script>
    // Add click listener to all copy buttons
    document.addEventListener('DOMContentLoaded', function() {
        setupCopyListeners();
    });
    
    // Re-setup listeners when Streamlit reruns
    const observer = new MutationObserver(function(mutations) {
        setupCopyListeners();
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    function setupCopyListeners() {
        const copyButtons = document.querySelectorAll('button[data-testid="stCodeCopyButton"]');
        copyButtons.forEach(button => {
            if (!button.dataset.listenerAdded) {
                button.dataset.listenerAdded = 'true';
                button.addEventListener('click', function() {
                    // Find the parent code container
                    const codeContainer = button.closest('.stCode');
                    if (codeContainer) {
                        // Add copied class
                        codeContainer.classList.add('copied');
                        
                        // Optional: Remove after a delay (if you want temporary highlight)
                        // setTimeout(() => {
                        //     codeContainer.classList.remove('copied');
                        // }, 3000);
                    }
                });
            }
        });
    }
</script>
""", unsafe_allow_html=True)

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'prompts'
if 'profile_id' not in st.session_state:
    st.session_state.profile_id = ''
if 'fullscreen' not in st.session_state:
    st.session_state.fullscreen = False

# Debug Tools (sidebar) - helps force-clear caches and inspect storage listings
with st.sidebar.expander("Debug Tools", expanded=False):
    if st.button("Clear image caches and reload", key="debug_clear_caches"):
        try:
            get_profile_image_files.clear()
            count_profile_images.clear()
            get_existing_profile_ids.clear()
            get_profile_completion_data.clear()
            get_all_profile_analyses.clear()
            load_image_cached.clear()
        except Exception:
            pass
        # Use experimental rerun when available, otherwise set a flag and stop to force a refresh
        rerun_fn = getattr(st, "experimental_rerun", None)
        if callable(rerun_fn):
            rerun_fn()
        else:
            st.session_state['_debug_refresh_needed'] = True
            st.stop()

    if st.button("Show storage listing (profile_results)", key="debug_list_storage"):
        try:
            storage = get_storage()
            files = storage.list_files("profile_results", "*")
            st.write("Total files:", len(files))
            # Show up to 200 entries to avoid UI overload
            st.write(files[:200])
        except Exception as e:
            st.write("Error listing storage:", e)

    # Toggle for S3 console logs (default off)
    try:
        from dotenv import set_key, find_dotenv
        env_path = find_dotenv(raise_error_if_not_found=False)
    except Exception:
        set_key = None
        env_path = None

    s3_default = os.environ.get('S3_CONSOLE_LOGS', 'false').lower() in ('1', 'true', 'yes')
    s3_toggle = st.checkbox("Enable S3 console logs", value=s3_default, key="ui_s3_console_logs")
    # Apply immediately for current process
    os.environ['S3_CONSOLE_LOGS'] = 'true' if s3_toggle else 'false'
    if s3_toggle:
        st.caption("S3 console logs enabled (for this process).")
    else:
        st.caption("S3 console logs disabled (for this process).")

    # Optionally persist to .env
    if set_key and st.button("Persist S3 logging to .env", key="persist_s3_env"):
        try:
            # Ensure .env file exists
            if not env_path:
                # create .env in project root
                env_path = str(Path('.').resolve() / '.env')
            set_key(env_path, 'S3_CONSOLE_LOGS', 'true' if s3_toggle else 'false')
            st.success(f"Wrote S3_CONSOLE_LOGS={'true' if s3_toggle else 'false'} to {env_path}")
        except Exception as e:
            st.error(f"Failed to persist .env: {e}")

# Only show UI chrome when NOT in fullscreen
if not st.session_state.fullscreen:
    st.title("🎨 MidJourney Profile Tester")
    
    # Navigation
    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 1])
    with col1:
        if st.button("📝 Prompts"):
            st.session_state.page = 'prompts'
            st.session_state.fullscreen = False
    with col2:
        if st.button("🖼️ Images"):
            st.session_state.page = 'images'
    with col3:
        if st.button("⭐ Rate"):
            st.session_state.page = 'rate'
    with col4:
        if st.button("🛠️ Tests"):
            st.session_state.page = 'manage_tests'
    with col5:
        if st.button("� Assess"):
            st.session_state.page = 'assess'
    with col6:
        if st.button("🎯 Recommend"):
            st.session_state.page = 'recommend'
    
    # Input for profile ID (optional - empty = baseline)
    # Check for existing profiles
    profile_results_dir = Path("profile_results")
    existing_profiles = get_existing_profile_ids()
    
    # Check analysis versions for existing profiles
    # Get total test count and test names
    current_tests = tpm.list_tests(status_filter='current')
    total_tests = len(current_tests)
    current_test_names = set(t.get('title', '') for t in current_tests)
    
    profile_versions, profile_completion = get_profile_completion_data(
        tuple(existing_profiles), 
        tuple(current_test_names),
        total_tests
    )
    
    # Add option to select from existing profiles or enter new
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if existing_profiles:
            # Create display names with version indicators
            analyses = get_all_profile_analyses()

            def format_profile_option(profile):
                if not profile:
                    return ""
                version = profile_versions.get(profile, 'unknown')
                is_complete = profile_completion.get(profile, False)

                # Profile label from analysis (if available)
                label = analyses.get(profile, {}).get('profile_label', '')

                # Build status indicators
                status = ""
                if is_complete:
                    status += "✅ "
                if version == ANALYSIS_PROMPT_VERSION:
                    status += "✓ "
                elif version != 'unknown':
                    status += "⚠️ "

                # Short display: "id — Label [status]"
                if label:
                    display = f"{profile} — {label} {status}".strip()
                else:
                    display = f"{profile} {status}".strip()

                return display
            
            profile_options = [""] + existing_profiles

            # Debugging aid: show total profile count and allow expanding full list
            try:
                st.caption(f"Profiles found: {len(existing_profiles)}")
                with st.expander("Debug: list all profiles (expand to view)", expanded=False):
                    st.write(existing_profiles)
            except Exception:
                pass
            
            # Restore previous selection if it exists in the list
            default_index = 0
            if st.session_state.profile_id in profile_options:
                default_index = profile_options.index(st.session_state.profile_id)
            
            selected_profile = st.selectbox(
                "Select existing profile",
                options=profile_options,
                format_func=lambda p: format_profile_option(p),
                index=default_index,
                key="profile_selector_dropdown",
                help="Choose a profile you've already tested (✅ = all tests complete, ✓ = current version, ⚠️ = outdated)"
            )
        else:
            selected_profile = ""
            st.info("No existing profiles found. Enter a new profile ID below.")
    
    with col_b:
        typed_profile = st.text_input(
            "Or enter new profile ID",
            value=st.session_state.profile_id if st.session_state.profile_id not in existing_profiles else "",
            placeholder="Leave empty for baseline",
            key="profile_typed_input",
            help="Enter a new MidJourney profile ID to test"
        )
    
    # Use selected profile if chosen, otherwise use typed input
    profile_id = selected_profile if selected_profile else typed_profile
    st.session_state.profile_id = profile_id
else:
    # In fullscreen mode, get profile_id from session state
    profile_id = st.session_state.profile_id

# Allow proceeding with or without profile ID
proceed = True

if st.session_state.page == 'prompts':
    if profile_id:
        st.markdown(f"### Testing Profile: **{profile_id}**")
    else:
        st.markdown(f"### Testing Profile: **Baseline (no profile)**")
    
    # Global parameters input
    st.markdown("---")
    st.markdown("### ⚙️ Global Parameters")
    st.caption("Add common parameters that will be applied to all prompts (e.g., --ar 16:9 --quality 4 --seed 20161027)")
    
    if 'global_params' not in st.session_state:
        st.session_state.global_params = load_global_params()
    
    col1, col2 = st.columns([4, 1])
    with col1:
        global_params = st.text_input(
            "Parameters to add to all prompts",
            value=st.session_state.global_params,
            placeholder="e.g., --ar 16:9 --quality 4 --seed 20161027",
            help="These parameters will be added to every prompt below"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing to align button
        if st.button("Apply"):
            # Randomize any explicit seed values so each application yields
            # a fresh 32-bit unsigned seed where the user provided one.
            def _randomize_seed(s: str) -> str:
                if not s:
                    return s
                def _repl(m):
                    prefix = m.group(1)
                    return f"{prefix}{random.randint(0, 2**32-1)}"
                # Match --seed 123 or --seed=123 (case-insensitive)
                return re.sub(r"(--seed(?:=|\s+))(\d+)", _repl, s, flags=re.IGNORECASE)

            randomized = _randomize_seed(global_params)
            st.session_state.global_params = randomized
            save_global_params(randomized)
            # Bump a sync token so other pages can detect the change and
            # refresh dependent widgets.
            st.session_state.global_params_token = st.session_state.get('global_params_token', 0) + 1
            st.rerun()
    
    st.markdown("---")
    
    try:
        # Load tests from JSON
        with st.spinner("Loading test prompts..."):
            df = load_tests_df(status_filter='current')
            
            if df.empty:
                st.warning("⚠️ No test prompts found. Add some in the Tests tab!")
                st.stop()
        
        st.success(f"✅ Loaded {len(df)} test prompts")
        
        # Display prompts by section
        sections = df['Section'].unique()
        
        for section in sections:
            # Skip empty/NaN sections
            if pd.isna(section) or not str(section).strip():
                continue
                
            section_tests = df[df['Section'] == section]
            
            st.markdown(f"### {section}")
            st.markdown("---")
            
            for idx, row in section_tests.iterrows():
                test_name = row['Title']
                base_prompt = row['Prompt']
                params = row['Parameter Values']
                section = row['Section']
                
                # Build full prompt with global params
                prompt_parts = [base_prompt, params]
                if st.session_state.global_params.strip():
                    global_params_to_add = st.session_state.global_params.strip()
                    # For VOID tests, remove --seed parameter
                    if str(section).startswith('VOID'):
                        global_params_to_add = filter_seed_from_params(global_params_to_add)
                    if global_params_to_add:
                        prompt_parts.append(global_params_to_add)
                if profile_id:
                    prompt_parts.append(f"--p {profile_id}")
                
                full_prompt = " ".join(part for part in prompt_parts if part)
                
                # Display test name as header
                st.markdown(f"**{test_name}**")
                
                # Display prompt in code block with built-in copy button
                st.code(full_prompt, language=None)
                
                st.markdown("")  # Add spacing
        
        # Show all prompts at once for bulk copying
        st.markdown("---")
        st.markdown("### 📄 All Prompts (for bulk copying)")
        
        all_prompts = []
        prompt_count = 0
        for idx, row in df.iterrows():
            section = row['Section']
            test_name = row['Title']
            base_prompt = row['Prompt']
            params = row['Parameter Values']
            
            # Skip empty/NaN rows
            if pd.isna(section) or pd.isna(test_name) or pd.isna(base_prompt):
                continue
            
            # Build full prompt with global params
            prompt_parts = [base_prompt, params]
            if st.session_state.global_params.strip():
                global_params_to_add = st.session_state.global_params.strip()
                # For VOID tests, remove --seed parameter
                if str(section).startswith('VOID'):
                    global_params_to_add = filter_seed_from_params(global_params_to_add)
                if global_params_to_add:
                    prompt_parts.append(global_params_to_add)
            if profile_id:
                prompt_parts.append(f"--p {profile_id}")
            
            full_prompt = " ".join(part for part in prompt_parts if part)
            all_prompts.append(full_prompt)
            prompt_count += 1
            
            # Add blank line after every 10 prompts
            if prompt_count % 10 == 0:
                all_prompts.append("")
        
        all_prompts_text = "\n".join(all_prompts)
        st.text_area(
            "All prompts",
            value=all_prompts_text,
            height=400,
            help="Copy all prompts at once"
        )
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to fetch CSV: {e}")
    except Exception as e:
        st.error(f"❌ Error processing data: {e}")
        st.exception(e)

elif st.session_state.page == 'images' and proceed:
    profile_display = profile_id if profile_id else "Baseline (no profile)"
    
    # Only show page header and toggle when not in fullscreen
    if not st.session_state.fullscreen:
        st.markdown(f"### 🖼️ Image Grid for: **{profile_display}**")
        
        # Add fullscreen toggle and cache refresh button
        col1, col2, col3 = st.columns([5, 1, 1])
        with col2:
            if st.button("🔄 Refresh", help="Clear cache and reload images"):
                # Clear all performance caches
                get_profile_image_files.clear()
                count_profile_images.clear()
                get_existing_profile_ids.clear()
                get_profile_completion_data.clear()
                load_image_cached.clear()
                st.rerun()
        with col3:
            fullscreen = st.toggle("🖥️ Fullscreen", value=st.session_state.fullscreen)
            if fullscreen != st.session_state.fullscreen:
                st.session_state.fullscreen = fullscreen
                st.rerun()
    else:
        fullscreen = st.session_state.fullscreen
    
    if not fullscreen:
        st.info("💡 **How to upload:** Option A: Right-click image in MidJourney → 'Copy Image' → Click 📋 Paste button below  |  Option B: Save to computer → Drag into 📤 Upload (or click to browse)")
        st.caption("⚠️ Note: MidJourney's CDN blocks direct URL downloads, so please download images first")
    
    # Create output directory for this profile
    output_dir = Path(f"profile_results/{profile_id if profile_id else 'baseline'}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Load test data from JSON
        df = load_tests_df(status_filter='current')
        
        if df.empty:
            st.warning("⚠️ No test prompts found")
            st.stop()
        
        # Debug panel at the very top
        import time
        st.markdown("### 🐛 Debug Info")
        debug_container = st.empty()
        start_time = time.time()
        debug_log = []
        debug_log.append(f"[{time.time() - start_time:.2f}s] Page load started")
        debug_container.code("\n".join(debug_log))
        
        # Group by section
        sections = df['Section'].unique()
        debug_log.append(f"[{time.time() - start_time:.2f}s] Found {len(sections)} sections with {len(df)} tests")
        debug_container.code("\n".join(debug_log))
        
        if fullscreen:
            # Marker FIRST - everything before this will be hidden
            st.markdown('<div style="display:none;">FULLSCREEN_START_MARKER</div>', unsafe_allow_html=True)
            
            # Fullscreen/Lightbox mode - hide all Streamlit UI and show only images
            st.markdown("""
            <style>
                /* Hide ALL Streamlit chrome */
                header[data-testid="stHeader"] { display: none !important; }
                .stApp > header { display: none !important; }
                [data-testid="stDecoration"] { display: none !important; }
                [data-testid="stStatusWidget"] { display: none !important; }
                #MainMenu { display: none !important; }
                footer { display: none !important; }
                
                /* Dark fullscreen background */
                .stApp {
                    margin: 0 !important;
                    padding: 0 !important;
                    max-width: 100vw !important;
                    background: #0a0a0a !important;
                }
                section[data-testid="stAppViewContainer"] {
                    background: #0a0a0a !important;
                    min-height: 100vh !important;
                }
                .block-container {
                    padding: 20px !important;
                    max-width: 100vw !important;
                }
                
                /* Ensure images are visible */
                img {
                    border-radius: 8px !important;
                    box-shadow: 0 4px 12px rgba(255, 255, 255, 0.1) !important;
                    display: block !important;
                    visibility: visible !important;
                    opacity: 1 !important;
                }
                
                /* Make captions white */
                figure figcaption, .stImage > div, [data-testid="stCaptionContainer"] {
                    color: white !important;
                    opacity: 0.8 !important;
                    font-size: 14px !important;
                }
                
                /* All text white */
                .stApp *, h1, div, p, span {
                    color: white !important;
                }
                
                [data-testid="stImage"] {
                    display: block !important;
                }
                
                /* Mark fullscreen content with data attribute */
                .fullscreen-content {
                    display: block !important;
                    visibility: visible !important;
                }
            </style>
            
            <script>
            // Hide everything before the fullscreen marker - multiple passes for reliability
            function hideBeforeMarker() {
                const allDivs = document.querySelectorAll('.block-container > div');
                let foundMarker = false;
                let markerIndex = -1;
                
                // First pass: find the marker
                allDivs.forEach((div, index) => {
                    if (div.innerHTML && div.innerHTML.includes('FULLSCREEN_START_MARKER')) {
                        markerIndex = index;
                        foundMarker = true;
                    }
                });
                
                // Second pass: hide everything before the marker
                if (foundMarker) {
                    allDivs.forEach((div, index) => {
                        if (index <= markerIndex) {
                            div.style.display = 'none';
                            div.style.visibility = 'hidden';
                            div.style.height = '0';
                            div.style.overflow = 'hidden';
                        }
                    });
                }
            }
            
            // Run multiple times to catch dynamic content
            setTimeout(hideBeforeMarker, 50);
            setTimeout(hideBeforeMarker, 200);
            setTimeout(hideBeforeMarker, 500);
            </script>
            """, unsafe_allow_html=True)
            
            # Title and escape hint
            st.markdown(f"<h1 style='color: white !important; margin-top: 0; font-size: 36px;'>🎨 {profile_display}</h1>", unsafe_allow_html=True)
            st.markdown("<hr style='border-color: #333; margin-bottom: 30px;'>", unsafe_allow_html=True)
            
            # Collect all images
            all_images = []
            for section in sections:
                section_tests = df[df['Section'] == section]
                for idx, row in section_tests.iterrows():
                    test_name = row['Title']
                    filepath = find_image_file(output_dir, profile_id if profile_id else 'baseline', test_name)
                    if filepath:
                        all_images.append((test_name, filepath))
            
            # Display in grid (5 columns for fullscreen)
            for row_idx in range(0, len(all_images), 5):
                cols = st.columns(5)
                for col_idx, col in enumerate(cols):
                    img_idx = row_idx + col_idx
                    if img_idx < len(all_images):
                        test_name, filepath = all_images[img_idx]
                        with col:
                            img_display = load_image_cached(str(filepath))
                            st.image(img_display, caption=test_name, width='stretch')
            
            if len(all_images) < len(df):
                st.warning(f"⚠️ Showing {len(all_images)}/{len(df)} images. Upload missing images to see complete set.")
        
        else:
            # Normal mode - show upload UI with fragments to prevent full page reloads
            
            debug_log.append(f"[{time.time() - start_time:.2f}s] Normal mode - starting image preload")
            debug_container.code("\n".join(debug_log))
            
            # Pre-warm file list cache to prevent each fragment from triggering S3 calls
            profile_key = profile_id if profile_id else 'baseline'
            debug_log.append(f"[{time.time() - start_time:.2f}s] Getting file list for profile: {profile_key}")
            debug_container.code("\n".join(debug_log))
            
            _ = get_profile_image_files(profile_key)
            debug_log.append(f"[{time.time() - start_time:.2f}s] File list loaded")
            # Also collect a cached list of ALL image files across profiles for compact grid views
            storage = get_storage()
            try:
                all_image_files_for_tests = storage.list_files("profile_results", "*.jpg") + storage.list_files("profile_results", "*.png")
            except Exception:
                all_image_files_for_tests = []
            debug_log.append(f"[{time.time() - start_time:.2f}s] Total image files across profiles: {len(all_image_files_for_tests)}")
            debug_container.code("\n".join(debug_log))
            
            # Pre-load ALL images in parallel for instant rendering
            debug_log.append(f"[{time.time() - start_time:.2f}s] Collecting image paths...")
            debug_container.code("\n".join(debug_log))
            
            images_to_load = []
            
            # Collect all image paths that exist
            for section in sections:
                section_tests = df[df['Section'] == section]
                for idx, row in section_tests.iterrows():
                    test_name = row['Title']
                    # Check for VOID tests that need multiple images
                    if test_name in ["Null Prompt (Photo)", "Null Prompt (Art)"]:
                        for img_num in range(1, 9):
                            filepath = find_image_file(output_dir, profile_key, test_name, img_num)
                            if filepath:
                                images_to_load.append(str(filepath))
                    else:
                        filepath = find_image_file(output_dir, profile_key, test_name)
                        if filepath:
                            images_to_load.append(str(filepath))
            
            debug_log.append(f"[{time.time() - start_time:.2f}s] Found {len(images_to_load)} images to load")
            debug_container.code("\n".join(debug_log))
            
            # Load all images in parallel (max 10 concurrent requests)
            debug_log.append(f"[{time.time() - start_time:.2f}s] Starting parallel image load...")
            debug_container.code("\n".join(debug_log))
            
            def load_single_image(path):
                img_start = time.time()
                result = load_image_cached(path)
                return path, time.time() - img_start
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(load_single_image, path) for path in images_to_load]
                for i, future in enumerate(as_completed(futures)):
                    path, duration = future.result()
                    debug_log.append(f"[{time.time() - start_time:.2f}s] Loaded image {i+1}/{len(images_to_load)} in {duration:.3f}s")
                    if i % 5 == 0:  # Update every 5 images to avoid too many updates
                        debug_container.code("\n".join(debug_log[-10:]))  # Show last 10 lines
            
            debug_log.append(f"[{time.time() - start_time:.2f}s] All images loaded! Rendering page...")
            debug_container.code("\n".join(debug_log[-15:]))
            
            for section in sections:
                section_tests = df[df['Section'] == section]
                st.markdown(f"### {section}")
            
                # Check if this section has multi-image tests (VOID tests)
                has_void_tests = any(name in ["Null Prompt (Photo)", "Null Prompt (Art)"] for name in section_tests['Title'].values)
                
                if has_void_tests:
                    # VOID tests get full width display
                    for idx, row in section_tests.iterrows():
                        test_name = row['Title']
                        if test_name in ["Null Prompt (Photo)", "Null Prompt (Art)"]:
                            st.markdown(f"**{test_name}** - Upload 8 unseeded images")
                            
                            # Create 4 columns for the 8 images (2 rows of 4)
                            for row_num in range(2):
                                cols = st.columns(4)
                                for col_idx, col in enumerate(cols):
                                    img_num = row_num * 4 + col_idx + 1
                                    with col:
                                        render_test_upload(profile_id, test_name, output_dir, f"{idx}_{img_num}", image_num=img_num)
                            # Collect existing images for this VOID test across all profiles
                            images_found = []
                            token = get_test_token(test_name)
                            safe_title = test_name.replace(' ', '_').replace('/', '_')
                            for file_path in all_image_files_for_tests:
                                parts = file_path.split('/')
                                if len(parts) >= 3:
                                    prof = parts[1]
                                    filename = parts[2]
                                    filename_no_ext = filename.rsplit('.', 1)[0]
                                    if filename_no_ext.startswith(f"{prof}_{token}") or filename_no_ext.startswith(f"{prof}_{safe_title}"):
                                        images_found.append((prof, file_path))

                            st.markdown("---")
                else:
                    # Regular tests - Create grid - 5 columns per row
                    tests_list = list(section_tests.iterrows())
                    
                    for row_idx in range(0, len(tests_list), 5):
                        cols = st.columns(5)
                        
                        for col_idx, col in enumerate(cols):
                            test_idx = row_idx + col_idx
                            if test_idx < len(tests_list):
                                idx, row = tests_list[test_idx]
                                test_name = row['Title']
                                
                                with col:
                                    # Single image per test (normal)
                                    render_test_upload(profile_id, test_name, output_dir, idx)
                
                st.markdown("---")
        
        # Show completion status (only in normal mode)
        if not fullscreen:
            total_tests = len(df)
            # Use cached count to avoid expensive S3 operations
            saved_images = count_profile_images(profile_id if profile_id else 'baseline')
            st.info(f"📊 Progress: {saved_images}/{total_tests} images uploaded")
        
    except Exception as e:
        st.error(f"❌ Error loading tests: {e}")

elif st.session_state.page == 'rate':
    st.title("⭐ Rate Profile Performance")
    
    # Allow baseline (empty profile_id)
    display_profile_id = profile_id if profile_id else "baseline"
    st.markdown(f"### Rating Profile: **{display_profile_id}**")
    
    # Load existing rating data if available
    profile_analyses_dir = Path("profile_analyses")
    profile_analyses_dir.mkdir(exist_ok=True)
    
    analysis_file = profile_analyses_dir / f"{display_profile_id}_analysis.json"
    
    import json
    
    # Initialize or load existing data via ResultsDataService
    from services.results_data_service import get_results_data_service
    rds = get_results_data_service()
    analysis_data = rds.read_analysis(display_profile_id) or {}
    if not analysis_data:
        analysis_data = {
            "profile_id": display_profile_id,
            "profile_label": "",
            "profile_dna": [],
            "ratings": {},
            "affinity_summary": {
                "native_fit": [],
                "workable": [],
                "resistant": []
            }
        }
    
    # Load test data for ratings section
    try:
        df = load_tests_df(status_filter='current')
        
        if df.empty:
            st.warning("⚠️ No test prompts found")
            st.stop()
        
        # Add export all profiles button at the top
        st.markdown("---")
        col_export, col_spacer = st.columns([1, 3])
        with col_export:
            if st.button("📦 Export All Profiles", help="Download all profile analyses as a single JSON file"):
                # Get list of all profiles from storage
                all_files = get_storage().list_files("profile_results", "*")
                profile_dirs = set()
                for file_path in all_files:
                    parts = file_path.split('/')
                    if len(parts) >= 2:
                        profile_dirs.add(parts[1])
                
                # Collect all profile analyses
                all_profiles = {}
                profile_analyses_dir = Path("profile_analyses")
                
                from services.results_data_service import get_results_data_service
                rds = get_results_data_service()
                for prof in sorted(profile_dirs):
                    try:
                        data = rds.read_analysis(prof) or {}
                        if data:
                            all_profiles[prof] = data
                    except Exception:
                        # Skip profiles without analysis files
                        pass
                
                # Create JSON string
                import json
                from datetime import datetime
                export_data = {
                    "export_date": datetime.now().strftime("%Y-%m-%d"),
                    "total_profiles": len(all_profiles),
                    "profiles": all_profiles
                }
                json_str = json.dumps(export_data, indent=2)
                
                # Offer download
                st.download_button(
                    label="💾 Download profiles.json",
                    data=json_str,
                    file_name="midjourney_profiles_export.json",
                    mime="application/json"
                )
        st.markdown("---")
        
        # Check which images are uploaded
        output_dir = Path("profile_results") / display_profile_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        st.subheader("📊 Test Ratings")
        
        # Show success message if present (from clear ratings operation)
        if 'clear_ratings_message' in st.session_state and st.session_state.clear_ratings_message:
            st.success(st.session_state.clear_ratings_message)
            # Don't clear immediately - let it show on this render
            # Will be cleared on next button interaction
        
        # Progress summary
        ratings = analysis_data.get("ratings", {})
        total_tests = len(df)
        # Only count ratings for tests that actually exist. Support ratings stored under GUIDs or legacy titles.
        current_test_names = list(df['Title'].tolist())
        rated_tests = 0
        rated_keys = set(ratings.keys())
        for test_name in current_test_names:
            try:
                test_obj = tpm.get_by_title(test_name)
            except Exception:
                test_obj = None
            canonical = canonical_test_key(test_obj, test_name)
            if test_name in rated_keys or (canonical and canonical in rated_keys):
                rated_tests += 1
        
        # Check analysis version
        current_version = ANALYSIS_PROMPT_VERSION
        analysis_version = analysis_data.get("analysis_version", "unknown")
        is_outdated = analysis_version != current_version
        
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1.5, 1.5])
        with col1:
            st.metric("Total Tests", total_tests)
        with col2:
            st.metric("Rated", rated_tests)
        with col3:
            st.metric("Remaining", total_tests - rated_tests)
        with col4:
            st.markdown("")  # Spacing
            if st.button("🤖 Auto-Rate All", type="primary", help="Use AI to rate all uploaded images at once"):
                # Check which images exist
                uploaded_tests = []
                for idx, row in df.iterrows():
                    test_name = row['Title']
                    
                    # Check if this is a multi-image test (Null Prompt tests)
                    if test_name in ["Null Prompt (Photo)", "Null Prompt (Art)"]:
                        # Collect all void images
                        void_images = []
                        for img_num in range(1, 9):
                            filepath = find_image_file(output_dir, display_profile_id, test_name, image_num=img_num)
                            if filepath:
                                void_images.append(filepath)
                        
                        if void_images:
                            # Pass list of filepaths for void test
                            uploaded_tests.append((test_name, void_images, row))
                    else:
                        # Single image test
                        filepath = find_image_file(output_dir, display_profile_id, test_name)
                        if filepath:
                            uploaded_tests.append((test_name, filepath, row))
                
                # Check which are already rated (support GUID keys and legacy title keys)
                rated_keys = set(analysis_data.get("ratings", {}).keys())
                already_rated_names = []
                for name, _, _ in uploaded_tests:
                    try:
                        test_obj = tpm.get_by_title(name)
                    except Exception:
                        test_obj = None
                    canonical = canonical_test_key(test_obj, name)
                    if name in rated_keys or (canonical and canonical in rated_keys):
                        already_rated_names.append(name)
                unrated_count = len(uploaded_tests) - len(already_rated_names)
                
                # If there are unrated images, start automatically; otherwise just show dialog
                if unrated_count > 0:
                    st.session_state.show_auto_rate = True
                    st.session_state.auto_continue_rating = True  # Enable auto-start
                else:
                    st.session_state.show_auto_rate = True
        with col5:
            st.markdown("")  # Spacing
            # Clear any previous messages when clicking clear button
            if 'clear_ratings_message' in st.session_state:
                st.session_state.clear_ratings_message = None
            
            if st.button("🗑️ Clear All Ratings", type="secondary", help="Delete all ratings for this profile"):
                # Just set confirmation flag - actual clear happens in confirmation dialog
                st.session_state.confirm_clear_ratings = True
                st.rerun()
        
        # Show version warning if analysis is outdated
        if rated_tests > 0 and is_outdated:
            st.markdown("---")
            st.warning(f"⚠️ **Outdated Analysis**: This profile was analyzed with version `{analysis_version}`. Current version is `{current_version}`. Consider re-rating for the latest evaluation criteria.")
        
        # Show confirmation dialog if needed
        if st.session_state.get('confirm_clear_ratings', False):
            st.warning("⚠️ Are you sure? This will delete ALL ratings, Profile DNA, and Profile Label for this profile.")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ Yes, Clear Everything", type="primary"):
                    # Create timestamped backup before clearing
                    from datetime import datetime
                    import shutil
                    
                    backup_dir = Path("profile_analyses/backups")
                    storage = get_storage()
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_filename = f"{display_profile_id}_analysis_backup_{timestamp}.json"
                    backup_path = backup_dir / backup_filename
                    
                    # Copy the current analysis file to backup
                    backup_created = False
                    backup_error = None
                    try:
                        from services.results_data_service import get_results_data_service
                        rds = get_results_data_service()
                        data = rds.read_analysis(display_profile_id) or {}
                        if data:
                            try:
                                storage.write_json(str(backup_path), data)
                                backup_created = True
                            except Exception as e:
                                backup_error = f"Backup write failed: {str(e)}"
                        else:
                            backup_error = f"Analysis file not found or empty for: {display_profile_id}"
                    except Exception as e:
                        backup_error = f"Backup failed: {str(e)}"
                    
                    # Actually clear the data
                    analysis_data['ratings'] = {}
                    analysis_data['profile_label'] = ""
                    analysis_data['profile_dna'] = []
                    analysis_data['affinity_summary'] = {
                        "native_fit": [],
                        "workable": [],
                        "resistant": []
                    }
                    save_analysis(display_profile_id, analysis_data)
                    
                    # Clear all widget session state for this profile
                    keys_to_clear = [k for k in st.session_state.keys() 
                                    if k.startswith(('affinity_', 'score_', 'confidence_', 'commentary_'))]
                    for key in keys_to_clear:
                        del st.session_state[key]
                    
                    # Store success message
                    if backup_created:
                        st.session_state.clear_ratings_message = f"✅ All ratings cleared! Backup saved to: backups/{backup_filename}"
                    elif backup_error:
                        st.session_state.clear_ratings_message = f"⚠️ Ratings cleared but backup failed: {backup_error}"
                    else:
                        st.session_state.clear_ratings_message = "✅ All ratings cleared! (No existing analysis to backup)"
                    
                    st.session_state.confirm_clear_ratings = False
                    st.success("✅ All ratings cleared!")
                    st.rerun()
            with col_cancel:
                if st.button("❌ Cancel"):
                    st.session_state.confirm_clear_ratings = False
                    st.rerun()
        
        # Auto-Rate All Dialog
        if st.session_state.get('show_auto_rate', False):
            with st.container():
                st.markdown("---")
                st.subheader("🤖 Batch AI Rating")
                st.markdown("This will send all uploaded images to AI for complete profile analysis.")
                
                # Check which images exist
                uploaded_tests = []
                for idx, row in df.iterrows():
                    test_name = row['Title']
                    
                    # Check if this is a multi-image test (Null Prompt tests)
                    if test_name in ["Null Prompt (Photo)", "Null Prompt (Art)"]:
                        # Collect all void images
                        void_images = []
                        for img_num in range(1, 9):
                            filepath = find_image_file(output_dir, display_profile_id, test_name, image_num=img_num)
                            if filepath:
                                void_images.append(filepath)
                        
                        if void_images:
                            # Pass list of filepaths for void test
                            uploaded_tests.append((test_name, void_images, row))
                    else:
                        # Single image test
                        filepath = find_image_file(output_dir, display_profile_id, test_name)
                        if filepath:
                            uploaded_tests.append((test_name, filepath, row))
                
                # Check which are already rated (support GUID keys and legacy title keys)
                rated_keys = set(analysis_data.get("ratings", {}).keys())
                already_rated_names = []
                for name, _, _ in uploaded_tests:
                    try:
                        test_obj = tpm.get_by_title(name)
                    except Exception:
                        test_obj = None
                    canonical = canonical_test_key(test_obj, name)
                    if name in rated_keys or (canonical and canonical in rated_keys):
                        already_rated_names.append(name)
                unrated_count = len(uploaded_tests) - len(already_rated_names)
                
                st.info(f"Found {len(uploaded_tests)} uploaded images: {len(already_rated_names)} already rated, {unrated_count} remaining")
                
                if len(uploaded_tests) == 0:
                    st.warning("⚠️ No images uploaded. You can upload images here on the Rate page or use the Images tab.")
                    if st.button("Close"):
                        st.session_state.show_auto_rate = False
                        st.rerun()
                elif unrated_count == 0:
                    st.success("✅ All tests already rated!")
                    
                    # Show finalize success message if present
                    if "finalize_message" in st.session_state and st.session_state.finalize_message:
                        st.success(st.session_state.finalize_message)
                        # Clear it so it doesn't show again
                        st.session_state.finalize_message = None
                    
                    # Add button to finalize/regenerate profile summary
                    col_finalize, col_close = st.columns([1, 1])
                    with col_finalize:
                        if st.button("🎨 Finalize Profile Summary", type="primary", help="Regenerate Profile DNA and Label based on all ratings"):
                            with st.spinner("🎨 Analyzing all test results to finalize Profile DNA and Aesthetic Label..."):
                                try:
                                    # Debug: show before state
                                    logger.debug("🔍 DEBUG Before finalize: label='%s'", analysis_data.get('profile_label', 'MISSING'))

                                    if finalize_profile_summary(display_profile_id, analysis_data):
                                        # Debug: show after finalize
                                        label_text = analysis_data.get('profile_label', '(none)')
                                        dna_count = len(analysis_data.get('profile_dna', []))
                                        affinity_summary = analysis_data.get('affinity_summary', {})
                                        logger.debug("🔍 DEBUG After finalize: label='%s', dna_count=%d, affinity_summary=%s", label_text, dna_count, list(affinity_summary.keys()))

                                        save_analysis(display_profile_id, analysis_data)
                                        logger.debug("🔍 DEBUG After save: Saved to %s_analysis.json", display_profile_id)

                                        # Verify what was saved
                                        from services.results_data_service import get_results_data_service
                                        rds = get_results_data_service()
                                        saved_data = rds.read_analysis(display_profile_id) or {}
                                        logger.debug("🔍 DEBUG Verification: Read back label='%s'", saved_data.get('profile_label', 'MISSING'))
                                        
                                        # Store success message in session state before rerun
                                        st.session_state.finalize_message = f"✨ Profile summary finalized!\n\n**Label:** {label_text}\n\n**DNA Traits:** {dna_count}"
                                        st.session_state.show_auto_rate = False
                                        st.rerun()
                                    else:
                                        st.error("Failed to finalize profile summary.")
                                except Exception as e:
                                    st.error(f"Error finalizing: {e}")
                                    st.exception(e)
                    
                    with col_close:
                        if st.button("Close"):
                            st.session_state.show_auto_rate = False
                            st.rerun()
                else:
                    # Generate profile label suggestion
                    profile_label_suggestion = st.text_input(
                        "Profile Label (optional)",
                        value=analysis_data.get("profile_label", ""),
                        placeholder="e.g., 'Moody Urban Explorer' or 'Vibrant Nature Maximalist'",
                        help="AI will suggest a profile label if left blank"
                    )
                    
                    # Check if we should auto-start (either button click or auto-continue from previous batch)
                    should_start_batch = False
                    
                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        batch_size = min(unrated_count, 15)
                        btn_label = f"🚀 Rate Next {batch_size} Test{'s' if batch_size != 1 else ''}"
                        if st.button(btn_label, type="primary", key="start_ai_analysis_btn"):
                            should_start_batch = True
                            st.session_state.auto_continue_rating = True  # Enable auto-continue
                    
                    # Auto-continue if flag is set
                    if st.session_state.get('auto_continue_rating', False) and not should_start_batch:
                        should_start_batch = True
                    
                    if should_start_batch:
                            with st.spinner(f"🤖 AI is analyzing {batch_size} images... This may take a minute..."):
                                try:
                                    # Prepare batch request to OpenAI
                                    try:
                                        batch_result = batch_ai_rate_images(
                                            uploaded_tests=uploaded_tests,
                                            profile_id=display_profile_id,
                                            profile_label=profile_label_suggestion,
                                            existing_ratings=analysis_data.get("ratings", {})
                                        )
                                    except Exception as e:
                                        import traceback
                                        tb = traceback.format_exc()
                                        st.error(f"❌ Error during AI analysis: {e}")
                                        st.exception(e)
                                        batch_result = False
                                
                                    if batch_result:
                                        # Note: batch_ai_rate_images now only returns ratings, not profile_label/profile_dna
                                        # Profile Label/DNA will be generated by finalize_profile_summary when all tests complete
                                        
                                        # Update ratings (already cleaned in batch function)
                                        for test_name, rating_data in batch_result.get("ratings", {}).items():
                                            try:
                                                test_obj = tpm.get_by_title(test_name)
                                            except Exception:
                                                test_obj = None
                                            # Always compute canonical write key (prefer id/guid, fallback to sanitized title)
                                            write_key = canonical_test_key(test_obj, test_name)
                                            analysis_data.setdefault('ratings', {})
                                            analysis_data['ratings'][write_key] = rating_data
                                            # remove legacy title key if GUID/id used
                                            if write_key != test_name and test_name in analysis_data['ratings']:
                                                try:
                                                    del analysis_data['ratings'][test_name]
                                                except Exception:
                                                    pass
                                        
                                        new_rating_count = len(batch_result.get('ratings', {}))
                                        remaining = unrated_count - new_rating_count
                                        
                                        # Save to file after each batch
                                        save_analysis(display_profile_id, analysis_data)
                                        
                                        # If all tests are now complete, finalize the profile summary
                                        if remaining == 0:
                                            with st.spinner("🎨 Finalizing Profile DNA and Aesthetic Label..."):
                                                if finalize_profile_summary(display_profile_id, analysis_data):
                                                    st.success("✨ Profile summary finalized!")
                                            
                                            msg = f"✅ Rated {new_rating_count} test{'s' if new_rating_count != 1 else ''}! 🎉 All tests complete!"
                                            st.success(msg)
                                            st.session_state.auto_continue_rating = False  # Stop auto-continue
                                            st.session_state.show_auto_rate = False
                                            import time
                                            time.sleep(0.5)
                                            st.rerun()
                                        else:
                                            # More tests remaining - automatically continue to next batch
                                            msg = f"✅ Rated {new_rating_count} test{'s' if new_rating_count != 1 else ''}! ({remaining} remaining - continuing automatically...)"
                                            st.success(msg)
                                            # Keep auto_continue_rating = True and rerun to trigger next batch
                                            import time
                                            time.sleep(0.5)
                                            st.rerun()
                                    elif batch_result is None:
                                        st.info("No unrated tests found.")
                                    else:
                                        st.error("❌ AI analysis failed. Please try again.")
                                
                                except Exception as e:
                                        st.error(f"❌ Error during AI analysis: {e}")
                                        st.exception(e)
                    
                    with col_btn2:
                        if st.button("Cancel"):
                            st.session_state.auto_continue_rating = False  # Stop auto-continue
                            st.session_state.show_auto_rate = False
                            st.rerun()
                
                st.markdown("---")
        
        st.markdown("---")
        
    except Exception as e:
        st.error(f"❌ Error loading tests: {e}")
    
    # Affinity Summary (if ratings exist)
    if rated_tests > 0:
        st.markdown("---")
        st.subheader("📊 Affinity Breakdown")
        
        # Count affinities
        native_count = sum(1 for r in ratings.values() if r.get('affinity') == 'native_fit')
        workable_count = sum(1 for r in ratings.values() if r.get('affinity') == 'workable')
        resistant_count = sum(1 for r in ratings.values() if r.get('affinity') == 'resistant')
        
        # Display as columns with colored metrics
        aff_col1, aff_col2, aff_col3 = st.columns(3)
        with aff_col1:
            st.metric("✅ Native Fit", native_count, help="Profile executes these styles excellently (scores 8-10)")
        with aff_col2:
            st.metric("⚠️ Workable", workable_count, help="Style achieved with compromises (scores 5-7)")
        with aff_col3:
            st.metric("❌ Resistant", resistant_count, help="Profile struggles with these styles (scores 1-4)")

    # Profile Label section
    st.subheader("🏷️ Profile Label")
    st.markdown("*One concise phrase describing the profile's dominant aesthetic*")
    
    # Debug: Show what we loaded
    loaded_label = analysis_data.get("profile_label", "")
    if loaded_label:
        st.caption(f"📝 Loaded label from file: '{loaded_label}'")
    
    profile_label = st.text_input(
        "Profile aesthetic label",
        value=analysis_data.get("profile_label", ""),
        placeholder='e.g., "Moody Cinematic Realism Specialist" or "High-Key Clean Studio Photo Specialist"',
        key=f"profile_label_input_{display_profile_id}",
        help="Short phrase capturing the profile's natural visual style"
    )
    
    # Only save if user actually changed it (not just rerender)
    if profile_label != analysis_data.get("profile_label", "") and profile_label != "":
        analysis_data["profile_label"] = profile_label
        save_analysis(display_profile_id, analysis_data)
    
    st.markdown("---")
    
    # Profile DNA section
    st.subheader("🧬 Profile DNA")
    st.markdown("*Recurring traits: vibe, palette, lighting, atmosphere, texture, composition*")
    with st.expander("💡 What to look for in Profile DNA"):
        st.markdown("""
        **Style elements that recur across images:**
        - **Lighting behavior**: cinematic low-key, studio product, high-key illustration
        - **Palette bias**: desaturated, teal/orange, neon, warm cozy
        - **Atmosphere defaults**: fog, rain, haze, bloom, film grain
        - **Texture/rendering**: photo vs painterly vs digital-watercolor
        - **Composition habits**: hero isolation, centered framing, leading lines
        """)
    
    # Show existing DNA traits
    dna_list = analysis_data.get("profile_dna", [])
    # Keep a separate list of manual traits the user explicitly added
    manual_list = analysis_data.get("profile_dna_manual", []) or []
    
    cols = st.columns([4, 1])
    with cols[0]:
        new_dna = st.text_input(
            "Add DNA trait",
            placeholder="e.g., Moody teal-blue color grading",
            key="new_dna_input"
        )
    with cols[1]:
        if st.button("➕ Add", key="add_dna"):
            if new_dna.strip():
                # Record as a manual trait and rebuild the visible DNA list
                manual_list.append(new_dna.strip())
                analysis_data["profile_dna_manual"] = manual_list
                # Preserve any existing non-manual traits after manual ones
                existing = analysis_data.get("profile_dna", []) or []
                rest = [t for t in existing if t not in manual_list]
                analysis_data["profile_dna"] = manual_list + rest
                save_analysis(display_profile_id, analysis_data)
                st.rerun()
    
    if dna_list:
        st.markdown("**Current DNA traits (drag to reorder):**")
        
        # Use streamlit-sortables for drag and drop reordering
        sorted_items = sort_items(
            items=dna_list,
            key="dna_sort"
        )
        
        # Check if order has changed
        if sorted_items and sorted_items != dna_list:
            # Save the new order for profile_dna
            analysis_data["profile_dna"] = sorted_items
            # Also update manual list order to keep manual traits first in their new order
            manual_list = [t for t in sorted_items if t in (analysis_data.get("profile_dna_manual", []) or [])]
            analysis_data["profile_dna_manual"] = manual_list
            save_analysis(display_profile_id, analysis_data)
            st.rerun()
        
        # Show delete buttons for each trait
        st.markdown("---")
        st.markdown("**Delete traits:**")
        current_list = sorted_items if sorted_items else dna_list
        for idx, trait in enumerate(current_list):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"{idx + 1}. {trait}")
            with col2:
                if st.button("🗑️", key=f"del_dna_{idx}"):
                    current_list = list(current_list)
                    removed = current_list.pop(idx)
                    # Remove from manual list if present
                    manual_list = analysis_data.get("profile_dna_manual", []) or []
                    if removed in manual_list:
                        manual_list = [t for t in manual_list if t != removed]
                        analysis_data["profile_dna_manual"] = manual_list
                    analysis_data["profile_dna"] = current_list
                    save_analysis(display_profile_id, analysis_data)
                    st.rerun()
    
    st.markdown("---")
    
    # Display tests for rating - only if df was loaded successfully
    if 'df' in locals() and 'ratings' in locals() and 'output_dir' in locals():
        # Only show filter if we have test data loaded
        show_filter = st.radio(
            "Show:",
            ["All Tests", "Unrated Only", "Rated Only"],
            horizontal=True,
            key="rating_filter"
        )
        
        st.markdown("---")
        
        # Display tests for rating
        for idx, row in df.iterrows():
            test_name = row['Title']
            # Prefer GUID as canonical key when available
            try:
                test_obj = tpm.get_by_title(test_name)
            except Exception:
                test_obj = None
            test_key = canonical_test_key(test_obj, test_name)
            
            # Check filter
            is_rated = (test_key in ratings) or (test_name in ratings)
            if show_filter == "Unrated Only" and is_rated:
                continue
            if show_filter == "Rated Only" and not is_rated:
                continue
            
            # Check if this is a multi-image test (Null Prompt tests)
            is_multi_image = (test_name in ["Null Prompt (Photo)", "Null Prompt (Art)"])
            
            if is_multi_image:
                # For void test, check if at least one image exists
                image_files = []
                for img_num in range(1, 9):
                    filepath = find_image_file(output_dir, display_profile_id, test_name, image_num=img_num)
                    if filepath:
                        image_files.append((img_num, filepath))
                
                if not image_files:
                    with st.expander(f"📷 {test_name} - ⚠️ No Images Uploaded"):
                        st.info("Upload images in the Images tab first (8 unseeded images expected)")
                    continue
                
                # Load existing rating if available (support GUID or legacy title key)
                existing_rating = ratings.get(test_key) or ratings.get(test_name, {})
                
                with st.expander(
                    f"{'✅' if is_rated else '⭐'} {test_name} ({len(image_files)}/8 images)" +
                    (f" - {existing_rating.get('affinity', '').replace('_', ' ').title()} ({existing_rating.get('score', 0)}/10)" if is_rated else ""),
                    expanded=not is_rated
                ):
                    # Show all uploaded void images in a grid
                    st.markdown(f"**{test_name} - {len(image_files)} unseeded images**")
                    st.caption("**Purpose:** Reveal pure profile bias with minimal prompt influence")
                    
                    # Show image upload / previews in 2 rows of 4 using unified helper
                    # This lets users upload/delete each void image directly from the Rate page.
                    for row_start in range(1, 9, 4):
                        cols = st.columns(4)
                        for offset, col in enumerate(cols):
                            img_num = row_start + offset
                            if img_num > 8:
                                continue
                            with col:
                                render_test_upload(display_profile_id, test_name, output_dir, f"{idx}_{img_num}", image_num=img_num, show_preview=True)
                    
                    st.markdown("---")
                    st.info("💡 Rate based on **commonalities across all images**: What visual patterns, color palettes, lighting, or textures consistently emerge?")
                    
                    # Rating form
                    col_rate1, col_rate2 = st.columns([1, 1])
                    
                    with col_rate1:
                        # Affinity selection
                        affinity_options = {
                            "native_fit": "✅ Strong Profile Signature - Clear recurring patterns",
                            "workable": "⚠️ Moderate Signature - Some patterns visible",
                            "resistant": "❌ Weak Signature - Highly variable/random"
                        }
                        
                        current_affinity = existing_rating.get('affinity', 'workable')
                        affinity_index = list(affinity_options.keys()).index(current_affinity) if current_affinity in affinity_options else 1
                        
                        affinity = st.radio(
                            "Profile Signature Strength",
                            options=list(affinity_options.keys()),
                            format_func=lambda x: affinity_options[x],
                            index=affinity_index,
                            key=f"affinity_{test_name}"
                        )
                    
                    with col_rate2:
                        # Score slider
                        score = st.slider(
                            "Consistency Score",
                            min_value=1,
                            max_value=10,
                            value=int(existing_rating.get('score', 5)),
                            key=f"score_{test_name}",
                            help="How consistent are the visual patterns across all images? 1 = Random/chaotic, 10 = Strong consistent signature"
                        )
                        
                        # Rendering style slider - different for PHOTO vs ART void tests
                        is_photo_void = "Photo" in test_name
                        if is_photo_void:
                            rendering_style = st.slider(
                                "Photographic Strength",
                                min_value=1,
                                max_value=10,
                                value=int(existing_rating.get('rendering_style', 5)),
                                key=f"rendering_{test_name}",
                                help="How photographic are the results? 1 = Painterly/abstract | 10 = Sharp photographic realism"
                            )
                            style_label = "📷 Photographic" if rendering_style >= 7 else "🎨 Hybrid" if rendering_style >= 4 else "🖌️ Painterly"
                        else:
                            rendering_style = st.slider(
                                "Artistic Strength",
                                min_value=1,
                                max_value=10,
                                value=int(existing_rating.get('rendering_style', 5)),
                                key=f"rendering_{test_name}",
                                help="How painterly/artistic are the results? 1 = Photographic/realistic | 10 = Strong painterly/abstract"
                            )
                            style_label = "🖌️ Painterly" if rendering_style >= 7 else "🎨 Hybrid" if rendering_style >= 4 else "📷 Photographic"
                        st.caption(f"**{style_label}**")
                        
                        # Confidence level
                        confidence_options = ["High", "Medium", "Low"]
                        raw_confidence = existing_rating.get('confidence', 'High')
                        
                        # Convert float confidence (from AI) to string format (for UI)
                        if isinstance(raw_confidence, (int, float)):
                            if raw_confidence >= 0.8:
                                current_confidence = "High"
                            elif raw_confidence >= 0.5:
                                current_confidence = "Medium"
                            else:
                                current_confidence = "Low"
                        else:
                            current_confidence = raw_confidence if raw_confidence in confidence_options else "High"
                        
                        confidence = st.select_slider(
                            "Confidence",
                            options=confidence_options,
                            value=current_confidence,
                            key=f"confidence_{test_name}",
                            help="How clear are the recurring patterns?"
                        )
                    
                    # Color palette field
                    color_palette = st.text_input(
                        "Dominant Color Patterns",
                        value=existing_rating.get('color-palette') or existing_rating.get('color_palette', ''),
                        placeholder="e.g., consistent warm sepia, recurring blue-purple tones...",
                        key=f"color_palette_{test_name}",
                        help="What color schemes appear repeatedly?"
                    )
                    # Arrange palette controls and swatch into two columns so controls remain visible
                    try:
                        existing_pal = existing_rating.get('color_palette') or existing_rating.get('color-palette')
                    except Exception:
                        existing_pal = None

                    left_col, right_col = st.columns([1, 1])

                    # Controls go in the left column
                    with left_col:
                        st.markdown("#### 🎛️ Palette controls")
                        has_analyzer_hexs = False
                        try:
                            if isinstance(existing_pal, dict):
                                dom_hexs = existing_pal.get('dominant_hex') or existing_pal.get('dominant_hexs')
                                acc_hexs = existing_pal.get('accent_hex') or existing_pal.get('accent_hexs')
                                has_analyzer_hexs = bool(dom_hexs or acc_hexs)
                        except Exception:
                            has_analyzer_hexs = False

                        # Always default to OpenAI as requested
                        palette_source_default = 0
                        palette_source = st.selectbox(
                            "Palette source",
                            options=["OpenAI (analyzer)", "k-means", "median-cut"],
                            index=palette_source_default,
                            key=f"palette_source_{test_name}",
                            help="Choose how to derive color swatches when analyzer hexs are not available."
                        )

                        # Normalization toggle: apply analyzer-provided temperature/saturation
                        norm_default = False
                        try:
                            if isinstance(existing_pal, dict):
                                if existing_pal.get('temperature_bias') is not None or existing_pal.get('saturation_level') is not None:
                                    norm_default = True
                        except Exception:
                            norm_default = False

                        apply_norm = st.checkbox(
                            "Apply analyzer temperature/saturation adjustments",
                            value=norm_default,
                            key=f"palette_norm_{test_name}",
                            help="When enabled, adjusts sampled or analyzer hexes by the analysis' temperature_bias and saturation_level."
                        )

                    # Swatch renders in the right column
                    with right_col:
                        st.markdown("#### 🎨 Palette preview")
                        # Show a small swatch preview for existing analysis palettes; prefer sampled colors from images
                        try:
                            if existing_pal:
                                # If analysis stored a dict of hues, prefer analyzer hexs; otherwise try sampling across all images
                                if isinstance(existing_pal, dict):
                                    # Prefer analyzer-provided hex lists if present
                                    dom_hexs = existing_pal.get('dominant_hex') or existing_pal.get('dominant_hexs')
                                    acc_hexs = existing_pal.get('accent_hex') or existing_pal.get('accent_hexs')
                                    if dom_hexs or acc_hexs:
                                        pal = {
                                            'dominant_hexs': dom_hexs or [],
                                            'accent_hexs': acc_hexs or []
                                        }
                                        if apply_norm:
                                            try:
                                                from services.image_utils import adjust_palette_temperature_and_saturation
                                                t_bias = existing_pal.get('temperature_bias', 0.0)
                                                s_level = existing_pal.get('saturation_level', 1.0)
                                                pal['dominant_hexs'] = adjust_palette_temperature_and_saturation(pal['dominant_hexs'], t_bias, s_level)
                                                pal['accent_hexs'] = adjust_palette_temperature_and_saturation(pal['accent_hexs'], t_bias, s_level)
                                            except Exception:
                                                pass
                                        render_palette_swatch(pal, width=240, height=64, source=palette_source, normalized=apply_norm, test_key=test_name)
                                    else:
                                        # Sample across all uploaded void images to build hexs
                                        img_paths = [str(fp) for _, fp in image_files]
                                        from services.image_utils import sample_palette_from_images
                                        method = 'kmeans' if palette_source.startswith('k-means') else 'median_cut'
                                        # If user selected OpenAI but no analyzer hexs exist, fall back to k-means
                                        if palette_source.startswith('OpenAI') and not (dom_hexs or acc_hexs):
                                            method = 'kmeans'
                                        hexs = sample_palette_from_images(img_paths, n_colors=5, method=method)
                                        if hexs:
                                            dominants = hexs[:3]
                                            accents = hexs[3:5]
                                            # Apply normalization if requested (use analyzer metadata if present)
                                            if apply_norm:
                                                try:
                                                    from services.image_utils import adjust_palette_temperature_and_saturation
                                                    t_bias = existing_pal.get('temperature_bias', 0.0) if isinstance(existing_pal, dict) else 0.0
                                                    s_level = existing_pal.get('saturation_level', 1.0) if isinstance(existing_pal, dict) else 1.0
                                                    dominants = adjust_palette_temperature_and_saturation(dominants, t_bias, s_level)
                                                    accents = adjust_palette_temperature_and_saturation(accents, t_bias, s_level)
                                                except Exception:
                                                    pass
                                            pal = {'dominant_hexs': dominants, 'accent_hexs': accents}
                                            # Persist sampled hexs into analysis_data for future renders
                                            try:
                                                existing_rating_cp = existing_rating.get('color_palette') if isinstance(existing_rating.get('color_palette'), dict) else {}
                                                existing_rating_cp['dominant_hex'] = dominants
                                                existing_rating_cp['accent_hex'] = accents
                                                existing_rating_cp['dominant_hexs'] = dominants
                                                existing_rating_cp['accent_hexs'] = accents
                                                existing_rating['color_palette'] = existing_rating_cp
                                                ratings[test_key] = existing_rating
                                                analysis_data['ratings'] = ratings
                                                save_analysis(display_profile_id, analysis_data)
                                            except Exception:
                                                pass
                                            render_palette_swatch(pal, width=240, height=64, source=palette_source, normalized=apply_norm, test_key=test_name)
                                        else:
                                            render_palette_swatch(existing_pal, width=240, height=64, source=palette_source, normalized=apply_norm, test_key=test_name)
                                else:
                                    render_palette_swatch(existing_pal, width=240, height=64, source=palette_source, normalized=apply_norm, test_key=test_name)
                        except Exception:
                            render_palette_swatch(existing_pal, width=240, height=64, source=palette_source, normalized=apply_norm, test_key=test_name)
                    
                    # Commentary with AI button
                    col_comment, col_ai = st.columns([3, 1])
                    
                    with col_comment:
                        commentary = st.text_area(
                            "Observations (optional)",
                            value=existing_rating.get('notes') or existing_rating.get('commentary', ''),
                            placeholder="What visual elements recur? Lighting patterns? Textures? Compositional habits?",
                            height=100,
                            key=f"commentary_{test_name}"
                        )
                    
                    with col_ai:
                        st.markdown("&nbsp;")  # Spacing
                        try:
                            _test_obj = tpm.get_by_title(test_name)
                        except Exception:
                            _test_obj = None
                        rating_key = canonical_test_key(_test_obj, test_name)
                        has_rating = rating_key in analysis_data.get('ratings', {}) or test_name in analysis_data.get('ratings', {})
                        ai_btn_label = "🔄 Re-rate" if has_rating else "🤖 AI Rate"
                        ai_btn_help = "Generate full AI rating (affinity, score, commentary) - will overwrite existing" if has_rating else "Generate full AI rating using OpenAI Vision"
                        
                        if st.button(ai_btn_label, key=f"ai_comment_{test_name}", help=ai_btn_help, type="secondary" if has_rating else "primary"):
                            with st.spinner("🤖 Analyzing with AI..."):
                                try:
                                    try:
                                        test_obj = tpm.get_by_title(test_name)
                                    except Exception:
                                        test_obj = {'title': test_name}

                                    from services.test_runner import run_test_for_profile

                                    res = run_test_for_profile(test_obj, display_profile_id, find_image_file, save_analysis)
                                    if res.get('status') == 'ok' and res.get('saved'):
                                        st.success("✨ Rating generated!")
                                        import time
                                        time.sleep(0.5)
                                        st.rerun()
                                    elif res.get('status') == 'no_images':
                                        st.warning("⚠️ No images uploaded for this test/profile")
                                    else:
                                        st.error(f"❌ Analysis failed: {res.get('error')}")
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
                    
                    # Save button
                    if st.button(f"💾 Save Rating for {test_name}", key=f"save_{test_name}"):
                        write_key = test_key
                        ratings[write_key] = {
                            "affinity": affinity,
                            "score": score,
                            "confidence": confidence,
                            "rendering_style": rendering_style,
                            "commentary": commentary,
                            "color-palette": color_palette
                        }
                        # Remove legacy title-key if different
                        if write_key != test_name and test_name in ratings:
                            try:
                                del ratings[test_name]
                            except Exception:
                                pass
                        analysis_data["ratings"] = ratings
                        save_analysis(display_profile_id, analysis_data)
                        st.success(f"✅ Saved rating for {test_name}")
                        import time
                        time.sleep(0.5)  # Brief pause to show success message
                        st.rerun()
                
            else:
                # Single image test (normal behavior)
                # Check if image exists
                filepath = find_image_file(output_dir, display_profile_id, test_name)
                
                if not filepath:
                    with st.expander(f"📷 {test_name} - ⚠️ Image Not Uploaded"):
                        # Allow upload/delete directly from the Rate page now
                        render_test_upload(display_profile_id, test_name, output_dir, idx, show_preview=True)
                    continue
                
                # Load existing rating if available (support GUID keys and legacy title keys)
                try:
                    test_obj = tpm.get_by_title(test_name)
                except Exception:
                    test_obj = None
                test_key = canonical_test_key(test_obj, test_name)
                existing_rating = ratings.get(test_key) or ratings.get(test_name, {})
                
                # Check if just AI rated (to keep expander open and show message)
                just_ai_rated = st.session_state.get(f'just_ai_rated_{test_name}', False)
                ai_message = st.session_state.get(f'ai_rated_message_{test_name}', None)
                if just_ai_rated:
                    # Clear the flags
                    st.session_state[f'just_ai_rated_{test_name}'] = False
                    if ai_message:
                        st.session_state[f'ai_rated_message_{test_name}'] = None
                    force_expanded = True
                else:
                    force_expanded = False
                
                # Show success message if present
                if ai_message:
                    st.success(ai_message)
                
                with st.expander(
                    f"{'✅' if is_rated else '⭐'} {test_name}" +
                    (f" - {existing_rating.get('affinity', '').replace('_', ' ').title()} ({existing_rating.get('score', 0)}/10)" if is_rated else ""),
                    expanded=(not is_rated) or force_expanded
                ):
                    col_img, col_rate = st.columns([1, 1])
                    
                    with col_img:
                        img_display = load_image_cached(str(filepath))
                        st.image(img_display, width='stretch')
                        st.caption(f"**Prompt:** {row['Prompt']}")
                        st.info("💡 Judge **style resemblance** (not content accuracy): Does it match the requested visual style, lighting, palette, and atmosphere?")
                    
                    with col_rate:
                        # Affinity selection
                        affinity_options = {
                            "native_fit": "✅ Native Fit - Profile looks at home in this style",
                            "workable": "⚠️ Workable - Close, but profile bias leaks through",
                            "resistant": "❌ Resistant - Fights the style, snaps to default look"
                        }
                        
                        current_affinity = existing_rating.get('affinity', 'workable')
                        affinity_index = list(affinity_options.keys()).index(current_affinity) if current_affinity in affinity_options else 1
                        
                        affinity = st.radio(
                            "Affinity Category",
                            options=list(affinity_options.keys()),
                            format_func=lambda x: affinity_options[x],
                            index=affinity_index,
                            key=f"affinity_{test_name}"
                        )
                        
                        # Score slider
                        score = st.slider(
                            "Style Resemblance Score",
                            min_value=1,
                            max_value=10,
                            value=int(existing_rating.get('score', 5)),
                            key=f"score_{test_name}",
                            help="Style match only (not content accuracy): 1 = Poor style match, 10 = Perfect style match"
                        )
                        
                        # Confidence level
                        confidence_options = ["High", "Medium", "Low"]
                        raw_confidence = existing_rating.get('confidence', 'High')
                        
                        # Convert float confidence (from AI) to string format (for UI)
                        if isinstance(raw_confidence, (int, float)):
                            if raw_confidence >= 0.8:
                                current_confidence = "High"
                            elif raw_confidence >= 0.5:
                                current_confidence = "Medium"
                            else:
                                current_confidence = "Low"
                        else:
                            current_confidence = raw_confidence if raw_confidence in confidence_options else "High"
                        
                        confidence = st.select_slider(
                            "Confidence",
                            options=confidence_options,
                            value=current_confidence,
                            key=f"confidence_{test_name}",
                            help="How clear is the style match? Use Low if image is ambiguous"
                        )
                        
                        # Color palette field
                        color_palette = st.text_input(
                            "Color Palette",
                            value=existing_rating.get('color-palette') or existing_rating.get('color_palette', ''),
                            placeholder="e.g., warm earth tones, vibrant neons, muted pastels...",
                            key=f"color_palette_{test_name}",
                            help="Describe the dominant color scheme"
                        )
                        # Show a small swatch preview for existing analysis palettes; prefer sampled colors from the image
                        try:
                            existing_pal = existing_rating.get('color_palette') or existing_rating.get('color-palette')
                            if existing_pal:
                                try:
                                    if isinstance(existing_pal, dict):
                                        dom_hexs = existing_pal.get('dominant_hex') or existing_pal.get('dominant_hexs')
                                        acc_hexs = existing_pal.get('accent_hex') or existing_pal.get('accent_hexs')
                                        if dom_hexs or acc_hexs:
                                            pal = {'dominant_hexs': dom_hexs or [], 'accent_hexs': acc_hexs or []}
                                            render_palette_swatch(pal, width=220, height=64,
                                                                 source=st.session_state.get(f"palette_source_{test_name}"),
                                                                 normalized=st.session_state.get(f"palette_norm_{test_name}", False),
                                                                 test_key=test_name)
                                        else:
                                            from services.image_utils import sample_palette_from_images
                                            img_file = filepath
                                            if img_file:
                                                hexs = sample_palette_from_images([str(img_file)], n_colors=5)
                                                if hexs:
                                                    dominants = hexs[:3]
                                                    accents = hexs[3:5]
                                                    pal = {'dominant_hexs': dominants, 'accent_hexs': accents}
                                                    # persist sampled hexs
                                                    try:
                                                        existing_rating_cp = existing_rating.get('color_palette') if isinstance(existing_rating.get('color_palette'), dict) else {}
                                                        existing_rating_cp['dominant_hex'] = dominants
                                                        existing_rating_cp['accent_hex'] = accents
                                                        existing_rating_cp['dominant_hexs'] = dominants
                                                        existing_rating_cp['accent_hexs'] = accents
                                                        existing_rating['color_palette'] = existing_rating_cp
                                                        ratings[test_key] = existing_rating
                                                        analysis_data['ratings'] = ratings
                                                        save_analysis(display_profile_id, analysis_data)
                                                    except Exception:
                                                        pass
                                                    render_palette_swatch(pal, width=220, height=64,
                                                                         source=st.session_state.get(f"palette_source_{test_name}"),
                                                                         normalized=st.session_state.get(f"palette_norm_{test_name}", False),
                                                                         test_key=test_name)
                                                else:
                                                    render_palette_swatch(existing_pal, width=220, height=64,
                                                                         source=st.session_state.get(f"palette_source_{test_name}"),
                                                                         normalized=st.session_state.get(f"palette_norm_{test_name}", False),
                                                                         test_key=test_name)
                                            else:
                                                render_palette_swatch(existing_pal, width=220, height=64,
                                                                     source=st.session_state.get(f"palette_source_{test_name}"),
                                                                     normalized=st.session_state.get(f"palette_norm_{test_name}", False),
                                                                     test_key=test_name)
                                    else:
                                        render_palette_swatch(existing_pal, width=220, height=64,
                                                             source=st.session_state.get(f"palette_source_{test_name}"),
                                                             normalized=st.session_state.get(f"palette_norm_{test_name}", False),
                                                             test_key=test_name)
                                except Exception:
                                    render_palette_swatch(existing_pal, width=220, height=64,
                                                         source=st.session_state.get(f"palette_source_{test_name}"),
                                                         normalized=st.session_state.get(f"palette_norm_{test_name}", False),
                                                         test_key=test_name)
                        except Exception:
                            pass
                        
                        # Commentary with AI generation option
                        col_comment, col_ai = st.columns([4, 1])
                        
                        with col_comment:
                            commentary = st.text_area(
                                "Commentary (optional)",
                                value=existing_rating.get('notes') or existing_rating.get('commentary', ''),
                                placeholder="What works well? What struggles? Any specific observations...",
                                height=100,
                                key=f"commentary_{test_name}"
                            )
                        
                        with col_ai:
                            st.markdown("&nbsp;")  # Spacing
                            try:
                                _test_obj = tpm.get_by_title(test_name)
                            except Exception:
                                _test_obj = None
                            rating_key = canonical_test_key(_test_obj, test_name)
                            has_rating = rating_key in analysis_data.get('ratings', {}) or test_name in analysis_data.get('ratings', {})
                            ai_btn_label = "🔄 Re-rate" if has_rating else "🤖 AI Rate"
                            ai_btn_help = "Generate full AI rating (affinity, score, commentary) - will overwrite existing" if has_rating else "Generate full AI rating using OpenAI Vision"
                            
                            if st.button(ai_btn_label, key=f"ai_comment_{test_name}", help=ai_btn_help, type="secondary" if has_rating else "primary"):
                                with st.spinner("🤖 Analyzing with AI..."):
                                    try:
                                        try:
                                            test_obj = tpm.get_by_title(test_name)
                                        except Exception:
                                            test_obj = {'title': test_name}

                                        from services.test_runner import run_test_for_profile

                                        res = run_test_for_profile(test_obj, display_profile_id, find_image_file, save_analysis)
                                        if res.get('status') == 'ok' and res.get('saved'):
                                            _set_ai_rated_session_flags(test_name)
                                            st.success("✨ Rating generated!")
                                            import time
                                            time.sleep(0.3)
                                            st.rerun()
                                        elif res.get('status') == 'no_images':
                                            st.warning("⚠️ No images uploaded for this test/profile")
                                        else:
                                            st.error(f"❌ Analysis failed: {res.get('error')}")
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                        
                        # Save button
                        if st.button("💾 Save Rating", key=f"save_{test_name}", type="primary"):
                            # Update rating
                            ratings[test_name] = {
                                "score": score,
                                "affinity": affinity,
                                "confidence": confidence,
                                "color_palette": color_palette.strip(),
                                "commentary": commentary.strip()
                            }
                            
                            analysis_data["ratings"] = ratings
                            
                            # Update affinity summary
                            affinity_summary = {
                                "native_fit": [],
                                "workable": [],
                                "resistant": []
                            }
                            for t_name, t_data in ratings.items():
                                aff = t_data['affinity']
                                if aff in affinity_summary:
                                    affinity_summary[aff].append(t_name)
                            
                            analysis_data["affinity_summary"] = affinity_summary
                            
                            # Save to file via centralized save_analysis
                            save_analysis(display_profile_id, analysis_data)
                            
                            st.success(f"✅ Saved rating for {test_name}")
                            import time
                            time.sleep(0.5)  # Brief pause to show success message
                            st.rerun()
        
        # Download complete analysis
        if ratings:
            st.markdown("---")
            st.subheader("💾 Export Analysis")
            
            json_output = json.dumps(analysis_data, indent=2)
            st.download_button(
                label=f"📥 Download {display_profile_id}_analysis.json",
                data=json_output,
                file_name=f"{display_profile_id}_analysis.json",
                mime="application/json"
            )
            
            st.info(f"✅ Analysis auto-saved to `profile_analyses/{display_profile_id}_analysis.json`")

elif st.session_state.page == 'assess':
    st.title("🔍 Image Analysis & Profile Finder")
    st.markdown("Upload any image to analyze its aesthetic and find the best MidJourney profiles to recreate that style.")
    
    st.info("💡 **How to upload:** Option A: Right-click any image → 'Copy Image' → Click 📋 Paste button  |  Option B: Save to computer → Click 📤 Upload")
    
    # Two-column layout for paste and upload
    paste_col, upload_col = st.columns([1, 1])
    
    uploaded_file = None
    pasted_image = None
    
    with paste_col:
        image_data = paste(
            label="📋 Paste from Clipboard",
            key="assess_paste_button"
        )
        
        if image_data is not None:
            # Decode base64 image
            import base64
            from io import BytesIO
            header, encoded = image_data.split(",", 1)
            binary_data = base64.b64decode(encoded)
            pasted_image = BytesIO(binary_data)
            st.success("✅ Image pasted!")
    
    with upload_col:
        uploaded_file = st.file_uploader(
            "📤 Upload Image",
            type=['png', 'jpg', 'jpeg', 'webp'],
            help="Upload any image to analyze",
            label_visibility="collapsed"
        )
    
    # Use whichever source provided an image (pasted takes precedence)
    image_source = pasted_image if pasted_image is not None else uploaded_file
    
    if image_source is not None:
        # Display the image
        st.image(image_source, caption="Image to Analyze", width='stretch')
        
        # Auto-analyze on upload by checking if this image has been processed
        import hashlib
        
        # Get image bytes and create hash
        if isinstance(image_source, BytesIO):
            image_bytes = image_source.getvalue()
        else:
            image_bytes = image_source.getvalue()
        
        image_hash = hashlib.md5(image_bytes).hexdigest()
        
        # Initialize session state for tracking analyzed images
        if 'analyzed_image_hash' not in st.session_state:
            st.session_state.analyzed_image_hash = None
        
        # Check if this is a new image that hasn't been analyzed yet
        should_analyze = (st.session_state.analyzed_image_hash != image_hash)
        
        # Manual re-analyze button
        if st.button("🔄 Re-Analyze Image", type="secondary", disabled=should_analyze):
            should_analyze = True
        
        if should_analyze:
            st.session_state.analyzed_image_hash = image_hash
            
            with st.spinner("🔍 Analyzing image aesthetic..."):
                import openai
                import base64
                import os
                from PIL import Image
                import io
                
                # Convert image to base64 for OpenAI
                img = Image.open(io.BytesIO(image_bytes))
                
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                # Prepare OpenAI request
                api_key = os.environ.get('OPENAI_API_KEY')
                if not api_key:
                    st.error("❌ OPENAI_API_KEY not found in environment")
                    st.stop()
                
                client = openai.OpenAI(api_key=api_key)
                
                # Analysis prompt
                analysis_prompt = """Analyze this image's aesthetic characteristics and create a MidJourney prompt to recreate it.

**Provide a detailed analysis:**

1. **Subject & Composition**: What is depicted? How is it composed?

2. **Visual Style**: Photography, digital art, painting, vector, 3D render, etc.

3. **Mood & Atmosphere**: Dark/bright, moody/cheerful, dramatic/calm, etc.

4. **Color Palette**: Dominant colors, saturation level (muted/vibrant), temperature (warm/cool), contrast level

5. **Texture & Quality**: Smooth/gritty, photorealistic/stylized, painterly/clean, etc.

6. **Lighting**: Natural/artificial, soft/hard, direction, time of day

7. **Technical Characteristics**: Depth of field, perspective, motion blur, grain/noise, etc.

**Then provide:**

- **MidJourney Prompt**: A complete, detailed prompt that would recreate this image's aesthetic in MidJourney. Be specific about style, mood, colors, lighting, and technical aspects. Format as a single paragraph ready to use.

- **Style Keywords**: 5-7 keywords that capture this aesthetic (e.g., "moody", "neon", "urban", "high-contrast", "cinematic")

Be thorough and specific in your analysis."""
                
                try:
                    from services.ai_client import chat_completion_to_text
                    from services.gpt_config import DEFAULT_MODEL, DEFAULT_MAX_COMPLETION_TOKENS
                    analysis_text, response = chat_completion_to_text(
                        client=client,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": analysis_prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{img_base64}",
                                            "detail": "high"
                                        }
                                    }
                                ]
                            }
                        ],
                        model=DEFAULT_MODEL,
                        max_completion_tokens=DEFAULT_MAX_COMPLETION_TOKENS,
                    )
                    
                    # Display analysis
                    st.markdown("---")
                    st.subheader("🎨 Aesthetic Analysis")
                    st.markdown(analysis_text)
                    
                    # Extract the generated prompt - try multiple patterns
                    import re
                    generated_prompt = None
                    
                    # Try pattern 1: **MidJourney Prompt**: text
                    prompt_match = re.search(
                        r'\*\*MidJourney Prompt\*\*:?\s*(.+?)(?=\n\n\*\*|\n\n-\s*\*\*|$)',
                        analysis_text,
                        re.DOTALL | re.IGNORECASE
                    )
                    if prompt_match:
                        generated_prompt = prompt_match.group(1).strip()
                    
                    # Try pattern 2: Look for any prompt-like content after "MidJourney Prompt"
                    if not generated_prompt:
                        prompt_match = re.search(
                            r'MidJourney Prompt[:\s]+(.+?)(?=\n\n|\Z)',
                            analysis_text,
                            re.DOTALL | re.IGNORECASE
                        )
                        if prompt_match:
                            generated_prompt = prompt_match.group(1).strip()
                    
                    # Clean up any remaining markdown formatting and quotes
                    if generated_prompt:
                        generated_prompt = re.sub(r'^\*\*|\*\*$', '', generated_prompt).strip()
                        # Remove surrounding quotes if present
                        generated_prompt = generated_prompt.strip('"\'')
                        
                        st.markdown("---")
                        st.subheader("📝 Generated MidJourney Prompt")
                        st.code(generated_prompt, language="text")
                        st.caption("This prompt should recreate the aesthetic of the uploaded image")
                    
                    # Now find matching profiles (use analysis text for matching, not just prompt)
                    st.markdown("---")
                    st.subheader("🏆 Recommended Profiles")
                    st.markdown("Based on the aesthetic analysis, here are profiles that align with this style:")
                    
                    with st.spinner("🔍 Finding matching profiles..."):
                        # Load all saved analyses
                        profile_analyses_dir = Path("profile_analyses")
                        analyses = {}
                        
                        # List all analysis files and load via ResultsDataService
                        storage = get_storage()
                        analysis_files = storage.list_files("profile_analyses", "*_analysis.json")
                        from services.results_data_service import get_results_data_service
                        rds = get_results_data_service()

                        for file_path in analysis_files:
                            try:
                                file_name = file_path.split('/')[-1]
                                profile_id = file_name.replace("_analysis.json", "")
                                data = rds.read_analysis(profile_id) or {}
                                if data:
                                    analyses[profile_id] = data
                            except Exception:
                                pass
                        
                        if not analyses:
                            st.warning("⚠️ No profile analyses found. Analyze some profiles first!")
                        else:
                            # Find matching tests based on keywords from analysis text
                            tests_df = load_tests_df()
                            
                            # Use analysis text for matching (more robust than just the prompt)
                            analysis_words = set(analysis_text.lower().split())
                            matching_tests = []
                            
                            for idx, row in tests_df.iterrows():
                                test_name = row['Title']
                                test_prompt = row['Prompt'].lower()
                                test_words = set(test_prompt.split())
                                overlap = len(analysis_words & test_words) / max(len(analysis_words), 1)
                                if overlap > 0.1:  # Lower threshold since we're matching full analysis
                                    matching_tests.append((test_name, overlap))
                            
                            matching_tests.sort(key=lambda x: x[1], reverse=True)
                            
                            if not matching_tests:
                                st.info("No strong test matches found - showing profiles by overall performance")
                            
                            # Score each profile
                            profile_scores = {}
                            
                            for profile_id, data in analyses.items():
                                ratings = data.get('ratings', {})
                                
                                if not ratings:
                                    continue
                                
                                total_score = 0
                                total_weight = 0
                                
                                if matching_tests:
                                    # Weight by matching tests
                                    for test_name, overlap in matching_tests[:5]:
                                        try:
                                            test_obj = tpm.get_by_title(test_name)
                                        except Exception:
                                            test_obj = None
                                        key = canonical_test_key(test_obj, test_name)
                                        rating = ratings.get(key) or ratings.get(test_name)
                                        if rating:
                                            score = rating['score']
                                            affinity = rating['affinity']
                                            
                                            weight = overlap
                                            if affinity == 'native_fit':
                                                weight *= 1.5
                                            elif affinity == 'resistant':
                                                weight *= 0.5
                                            
                                            total_score += score * weight
                                            total_weight += weight
                                else:
                                    # Use all ratings
                                    for test_name, rating in ratings.items():
                                        score = rating['score']
                                        affinity = rating['affinity']

                                        weight = 1.0
                                        if affinity == 'native_fit':
                                            weight = 1.5
                                        elif affinity == 'resistant':
                                            weight = 0.5

                                        total_score += score * weight
                                        total_weight += weight
                                
                                if total_weight > 0:
                                    weighted_avg = total_score / total_weight
                                    profile_scores[profile_id] = {
                                        'score': weighted_avg,
                                        'data': data
                                    }
                            
                            # Sort and display recommendations (moved outside the loop)
                            sorted_profiles = sorted(
                                profile_scores.items(),
                                key=lambda x: x[1]['score'],
                                reverse=True
                            )
                            
                            for rank, (profile_id, info) in enumerate(sorted_profiles[:5], 1):
                                score = info['score']
                                data = info['data']
                                
                                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "")
                                
                                with st.expander(f"{medal} **#{rank}: {profile_id}** (Match Score: {score:.1f}/10)", expanded=(rank == 1)):
                                    # Profile DNA
                                    dna_traits = data.get('profile_dna', [])
                                    if dna_traits:
                                        st.markdown("**Profile DNA:**")
                                        for trait in dna_traits[:5]:
                                            st.markdown(f"- {trait}")
                                    
                                    # Show relevant test performance
                                    if matching_tests:
                                        st.markdown("**Relevant Test Performance:**")
                                        ratings = data.get('ratings', {})
                                        for test_name, overlap in matching_tests[:5]:
                                            try:
                                                test_obj = tpm.get_by_title(test_name)
                                            except Exception:
                                                test_obj = None
                                            key = canonical_test_key(test_obj, test_name)
                                            rating = ratings.get(key) or ratings.get(test_name)
                                            if rating:
                                                affinity_emoji = {
                                                    'native_fit': '✅',
                                                    'workable': '⚠️',
                                                    'resistant': '❌'
                                                }.get(rating['affinity'], '❓')
                                                
                                                st.markdown(f"{affinity_emoji} **{test_name}**: {rating['score']}/10")
                                                
                                                # Show commentary for top match
                                                if overlap == matching_tests[0][1] and 'commentary' in rating:
                                                    st.markdown(f"*{rating['commentary']}*")
                                    
                                    # Show prompt with profile if we extracted one
                                    if generated_prompt:
                                        st.markdown("---")
                                        st.markdown("**🎨 Use This Prompt:**")
                                        if profile_id.lower() == "baseline":
                                            full_prompt = f"{generated_prompt} --ar 16:9 --stylize 1000 --quality 4"
                                        else:
                                            full_prompt = f"{generated_prompt} --ar 16:9 --stylize 1000 --p {profile_id} --quality 4"
                                        st.code(full_prompt, language="text")
                                        st.caption("Copy this prompt directly into MidJourney")
                                    else:
                                        st.info("💡 See the generated prompt in the analysis above to use with this profile")
                        
                        if not generated_prompt:
                            st.markdown("---")
                            st.info("💡 **Note:** The MidJourney prompt couldn't be automatically extracted, but you can find it in the aesthetic analysis above and use it with the recommended profiles.")
                
                except Exception as e:
                    st.error(f"❌ Error during analysis: {e}")
                    st.exception(e)
    else:
        st.info("👆 Paste or upload any image to begin analysis")
        
        st.markdown("""### How it works:
1. Upload any image (photo, art, screenshot, etc.)
2. AI analyzes the aesthetic: colors, mood, style, lighting, textures
3. Generates a MidJourney prompt to recreate that aesthetic
4. Recommends profiles whose strengths align with the image's style
5. Get ready-to-use prompts with the best matching profiles""")

elif st.session_state.page == 'recommend':
    st.title("🎯 Profile Recommendations")
    st.markdown("Get profile suggestions for a new prompt based on saved analyses.")
    
    # Load all saved analyses
    profile_analyses_dir = Path("profile_analyses")
    profile_analyses_dir.mkdir(exist_ok=True)
    
    import json
    import glob
    
    analyses = {}
    storage = get_storage()
    json_files = storage.list_files("profile_analyses", "*_analysis.json")
    from services.results_data_service import get_results_data_service
    rds = get_results_data_service()

    if json_files:
        for json_file_path in json_files:
            try:
                file_name = json_file_path.split('/')[-1]
                profile_id = file_name.replace('_analysis.json', '')
                data = rds.read_analysis(profile_id) or {}
                if data:
                    analyses[profile_id] = data
            except Exception as e:
                st.warning(f"⚠️ Could not load {json_file_path}: {e}")
        
        st.success(f"✅ Loaded {len(analyses)} profile analyses")
        
        # Show available profiles
        with st.expander("📁 Available Profiles"):
            for profile_id, data in analyses.items():
                dna_count = len(data.get('profile_dna', []))
                ratings_count = len(data.get('ratings', {}))
                st.markdown(f"- **{profile_id}**: {dna_count} DNA traits, {ratings_count} test ratings")
        
        st.markdown("---")
        
        # Input new prompt
        new_prompt = st.text_area(
            "Enter your new prompt",
            height=150,
            placeholder="A moody cyberpunk street scene at night with neon reflections...",
            help="Enter the prompt you want to use, and we'll recommend the best profile"
        )
        
        if st.button("🔮 Get Recommendations", type="primary"):
            if not new_prompt.strip():
                st.warning("⚠️ Please enter a prompt first")
            else:
                with st.spinner("Analyzing prompt..."):
                    # Simple keyword-based matching
                    # Extract keywords from prompt
                    import re
                    from collections import Counter
                    
                    # Load test suite to understand categories
                    try:
                        df = load_tests_df(status_filter='current')
                        
                        if df.empty:
                            st.warning("⚠️ No test prompts found")
                            st.stop()
                        
                        # Normalize prompt
                        prompt_lower = new_prompt.lower()
                        
                        # Determine which test categories this prompt matches
                        matching_tests = []
                        
                        for idx, row in df.iterrows():
                            test_name = row['Title']
                            test_prompt = row['Prompt'].lower()
                            
                            # Simple keyword overlap
                            test_keywords = set(re.findall(r'\b\w+\b', test_prompt))
                            prompt_keywords = set(re.findall(r'\b\w+\b', prompt_lower))
                            
                            overlap = len(test_keywords & prompt_keywords)
                            if overlap > 2:  # At least 3 keyword matches
                                matching_tests.append((test_name, overlap))
                        
                        matching_tests.sort(key=lambda x: x[1], reverse=True)
                        
                        st.subheader("🔍 Prompt Analysis")
                        if matching_tests:
                            st.markdown(f"**Similar to:** {', '.join([t[0] for t in matching_tests[:3]])}")
                        else:
                            st.info("No strong matches to test categories - showing all profiles")
                        
                        # Extract color keywords from prompt for palette matching
                        color_keywords = {
                            'warm': ['warm', 'orange', 'red', 'yellow', 'gold', 'amber', 'sunset', 'fire'],
                            'cool': ['cool', 'blue', 'cyan', 'teal', 'ice', 'winter', 'ocean'],
                            'vibrant': ['vibrant', 'bright', 'neon', 'vivid', 'saturated', 'bold', 'electric'],
                            'muted': ['muted', 'soft', 'pastel', 'subtle', 'desaturated', 'pale', 'faded'],
                            'dark': ['dark', 'black', 'shadow', 'moody', 'noir', 'night', 'midnight'],
                            'light': ['light', 'white', 'bright', 'airy', 'ethereal', 'luminous'],
                            'monochrome': ['monochrome', 'black and white', 'grayscale', 'sepia'],
                            'earth': ['earth', 'brown', 'tan', 'beige', 'natural', 'organic'],
                        }
                        
                        detected_palettes = []
                        for palette_type, keywords in color_keywords.items():
                            if any(kw in prompt_lower for kw in keywords):
                                detected_palettes.append(palette_type)
                        
                        if detected_palettes:
                            st.markdown(f"**Detected Color Themes:** {', '.join(detected_palettes)}")
                        
                        # Score each profile
                        profile_scores = {}
                        
                        for profile_id, data in analyses.items():
                            ratings = data.get('ratings', {})
                            
                            if not ratings:
                                continue
                            
                            # Calculate weighted score based on matching tests
                            total_score = 0
                            total_weight = 0
                            palette_bonus = 0
                            
                            if matching_tests:
                                # Use matching tests
                                for test_name, overlap in matching_tests[:5]:  # Top 5 matches
                                    try:
                                        test_obj = tpm.get_by_title(test_name)
                                    except Exception:
                                        test_obj = None
                                    key = canonical_test_key(test_obj, test_name)
                                    rating = ratings.get(key) or ratings.get(test_name)
                                    if rating:
                                        score = rating['score']
                                        affinity = rating['affinity']
                                        
                                        # Weight by overlap and affinity
                                        weight = overlap
                                        if affinity == 'native_fit':
                                            weight *= 1.5
                                        elif affinity == 'resistant':
                                            weight *= 0.5
                                        
                                        # Check color palette match
                                        if detected_palettes and 'color_palette' in rating:
                                            palette_text = rating['color_palette'].lower()
                                            palette_matches = sum(1 for p in detected_palettes if p in palette_text or any(kw in palette_text for kw in color_keywords.get(p, [])))
                                            if palette_matches > 0:
                                                # Boost weight for palette matches
                                                weight *= (1 + 0.2 * palette_matches)
                                                palette_bonus += palette_matches
                                        
                                        total_score += score * weight
                                        total_weight += weight
                            else:
                                # Use all tests (average)
                                for test_name, rating in ratings.items():
                                    score = rating['score']
                                    affinity = rating['affinity']
                                    
                                    weight = 1.0
                                    if affinity == 'native_fit':
                                        weight = 1.5
                                    elif affinity == 'resistant':
                                        weight = 0.5
                                    
                                    # Check color palette match
                                    if detected_palettes and 'color_palette' in rating:
                                        palette_text = rating['color_palette'].lower()
                                        palette_matches = sum(1 for p in detected_palettes if p in palette_text or any(kw in palette_text for kw in color_keywords.get(p, [])))
                                        if palette_matches > 0:
                                            weight *= (1 + 0.15 * palette_matches)
                                            palette_bonus += palette_matches
                                    
                                    total_score += score * weight
                                    total_weight += weight
                            
                            if total_weight > 0:
                                weighted_avg = total_score / total_weight
                                profile_scores[profile_id] = {
                                    'score': weighted_avg,
                                    'palette_bonus': palette_bonus,
                                    'data': data
                                }
                        
                        # Sort by score
                        sorted_profiles = sorted(
                            profile_scores.items(),
                            key=lambda x: x[1]['score'],
                            reverse=True
                        )
                        
                        # Display recommendations
                        st.markdown("---")
                        st.subheader("🏆 Recommended Profiles")
                        
                        for rank, (profile_id, info) in enumerate(sorted_profiles[:5], 1):
                            score = info['score']
                            palette_bonus = info.get('palette_bonus', 0)
                            data = info['data']
                            
                            # Medal emojis
                            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "")
                            palette_badge = "🎨" if palette_bonus > 0 else ""
                            
                            with st.expander(f"{medal} {palette_badge} **#{rank}: {profile_id}** (Score: {score:.1f}/10)", expanded=(rank <= 3)):
                                if palette_bonus > 0:
                                    st.success(f"🎨 Color Palette Match! ({int(palette_bonus)} matching themes)")
                                
                                # Show Profile DNA
                                st.markdown("**Profile DNA:**")
                                dna_traits = data.get('profile_dna', [])
                                if dna_traits:
                                    for trait in dna_traits[:5]:  # Top 5 traits
                                        st.markdown(f"- {trait}")
                                else:
                                    st.info("No DNA traits available")
                                
                                # Show relevant ratings
                                st.markdown("**Relevant Test Performance:**")
                                ratings = data.get('ratings', {})
                                
                                if matching_tests:
                                    # Show scores for matching tests with aesthetic commentary
                                    for test_name, overlap in matching_tests[:5]:
                                        try:
                                            test_obj = tpm.get_by_title(test_name)
                                        except Exception:
                                            test_obj = None
                                        key = canonical_test_key(test_obj, test_name)
                                        rating = ratings.get(key) or ratings.get(test_name)
                                        if rating:
                                            affinity_emoji = {
                                                'native_fit': '✅',
                                                'workable': '⚠️',
                                                'resistant': '❌'
                                            }.get(rating['affinity'], '❓')
                                            
                                            st.markdown(f"{affinity_emoji} **{test_name}**: {rating['score']}/10 ({rating['affinity']})")
                                            
                                            # Show color palette if available (accept either key format)
                                            palette_val = rating.get('color-palette') or rating.get('color_palette')
                                            if palette_val:
                                                try:
                                                    render_palette_swatch(palette_val, width=240, height=64,
                                                                         source=st.session_state.get(f"palette_source_{test_name}"),
                                                                         normalized=st.session_state.get(f"palette_norm_{test_name}", False),
                                                                         test_key=test_name)
                                                except Exception:
                                                    st.caption(f"🎨 Palette: {palette_val}")

                                            # Show aesthetic commentary for the most relevant test (highest overlap)
                                            if overlap == matching_tests[0][1]:
                                                summary = rating.get('notes') or rating.get('commentary', '')
                                                if summary:
                                                    with st.container():
                                                        st.markdown(f"*Aesthetic Analysis:* {summary}")

                                                # Surface metrics and normalized weights when present
                                                metrics = rating.get('metrics_v1') or {}
                                                weights = metrics.get('weights') if metrics else None
                                                if weights:
                                                    try:
                                                        norm = ", ".join([f"{k}={v:.2f}" for k, v in weights.items()])
                                                        st.caption(f"Metrics weights: {norm}")
                                                    except Exception:
                                                        pass
                                else:
                                    # Show average by category
                                    photo_scores = [r['score'] for k, r in ratings.items() if k.startswith('PHOTO_')]
                                    art_scores = [r['score'] for k, r in ratings.items() if k.startswith('ART_')]
                                    
                                    if photo_scores:
                                        st.markdown(f"📸 **Photography**: {sum(photo_scores)/len(photo_scores):.1f}/10 avg")
                                    if art_scores:
                                        st.markdown(f"🎨 **Art**: {sum(art_scores)/len(art_scores):.1f}/10 avg")
                                
                                # Show MidJourney prompt with profile
                                st.markdown("---")
                                st.markdown("**🎨 Use This Prompt:**")
                                # Don't include --p for baseline profile, and never include --seed
                                if profile_id.lower() == "baseline":
                                    full_prompt = f"{new_prompt.strip()} --ar 16:9 --stylize 1000 --quality 4"
                                else:
                                    full_prompt = f"{new_prompt.strip()} --ar 16:9 --stylize 1000 --p {profile_id} --quality 4"
                                st.code(full_prompt, language="text")
                                st.caption("Copy this prompt directly into MidJourney")
                        
                    except Exception as e:
                        st.error(f"❌ Error analyzing prompt: {e}")
    
    else:
        st.info("📁 No profile analyses found. Save JSON files from the Analyze tab to `profile_analyses/` folder.")
        st.markdown("""
        **To get started:**
        1. Go to the **Analyze** tab
        2. Parse your profile analysis
        3. Download the JSON
        4. Save it to `profile_analyses/` folder
        5. Return here to get recommendations
        """)

elif st.session_state.page == 'manage_tests':
    from ui.tests_page import render_tests_page
    render_tests_page(
        batch_ai_rate_images=batch_ai_rate_images,
        render_test_upload=render_test_upload,
        find_image_file=find_image_file,
        save_analysis=save_analysis,
        get_all_profile_analyses=get_all_profile_analyses,
        get_existing_profile_ids=get_existing_profile_ids,
        load_image_cached=load_image_cached,
        get_profile_image_files=get_profile_image_files,
        count_profile_images=count_profile_images,
        filter_seed_from_params=filter_seed_from_params,
    )
