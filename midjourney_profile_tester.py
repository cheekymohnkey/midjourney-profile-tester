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
import test_prompts_manager as tpm
from dotenv import load_dotenv
from storage import get_storage
import json
from streamlit_sortables import sort_items

# Load environment variables from .env file
load_dotenv()

# Analysis prompt version - increment when making significant changes to rating logic
ANALYSIS_PROMPT_VERSION = "2.3-signature"  # v2.3: Enhanced commentary to capture profile's aesthetic signature (tone, color, texture) for better DNA and recommendations

st.set_page_config(page_title="MidJourney Profile Tester", layout="wide")

# Global parameters persistence file
GLOBAL_PARAMS_FILE = Path("global_params.json")

def load_global_params():
    """Load global parameters from file, return default if not found."""
    try:
        if GLOBAL_PARAMS_FILE.exists():
            with open(GLOBAL_PARAMS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('global_params', '--ar 16:9 --quality 4 --seed 20161027')
    except Exception:
        pass
    return '--ar 16:9 --quality 4 --seed 20161027'

def save_global_params(params):
    """Save global parameters to file."""
    try:
        with open(GLOBAL_PARAMS_FILE, 'w') as f:
            json.dump({'global_params': params}, f)
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

def find_image_file(output_dir, profile_id, test_name, image_num=None):
    """
    Find an image file, checking both .jpg and .png extensions.
    Returns Path object if found, None otherwise.
    
    Args:
        output_dir: Directory containing images
        profile_id: Profile ID (or 'baseline')
        test_name: Test name from DataFrame
        image_num: For multi-image tests, the image number (1-8). None for single-image tests.
    
    Returns:
        Path object if file exists, None otherwise
    """
    safe_name = test_name.replace(' ', '_').replace('/', '_')
    storage = get_storage()
    
    # Build filename with optional image number
    if image_num:
        base_name = f"{profile_id}_{safe_name}_{image_num}"
    else:
        base_name = f"{profile_id}_{safe_name}"
    
    # Check .jpg first (new format)
    jpg_path = output_dir / f"{base_name}.jpg"
    if storage.exists(str(jpg_path)):
        return jpg_path
    
    # Fall back to .png (legacy format)
    png_path = output_dir / f"{base_name}.png"
    if storage.exists(str(png_path)):
        return png_path
    
    return None

# Helper function to load tests as DataFrame
def load_tests_df(status_filter='current'):
    """Load tests from JSON and return as DataFrame."""
    tests = tpm.load_tests(status_filter=status_filter)
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

@st.fragment
def render_test_upload(profile_id, test_name, output_dir, idx, image_num=None):
    """Fragment to handle individual test image upload without full page rerun.
    
    Args:
        image_num: For multi-image tests, the image number (1-8). None for single-image tests.
    """
    # Display title
    if image_num:
        st.markdown(f"**{test_name} #{image_num}**")
    else:
        st.markdown(f"**{test_name}**")
    
    # Create safe filename - new uploads will be .jpg
    safe_name = test_name.replace(' ', '_').replace('/', '_')
    if image_num:
        filename = f"{profile_id if profile_id else 'baseline'}_{safe_name}_{image_num}.jpg"
    else:
        filename = f"{profile_id if profile_id else 'baseline'}_{safe_name}.jpg"
    filepath = output_dir / filename
    
    # Check if image exists (handles both .jpg and .png)
    existing_filepath = find_image_file(output_dir, profile_id if profile_id else 'baseline', test_name, image_num)
    if existing_filepath:
        # Load image from storage for display
        img_display = load_image(existing_filepath)
        st.image(img_display, use_container_width=True)
        delete_key = f"delete_{idx}_{image_num}" if image_num else f"delete_{idx}"
        if st.button("🗑️", key=delete_key):
            existing_filepath.unlink()
            
            # Clear the analysis rating for this test
            analysis_file = Path("profile_analyses") / f"{profile_id if profile_id else 'baseline'}_analysis.json"
            analysis_data = get_storage().read_json(str(analysis_file))
            if analysis_data and "ratings" in analysis_data:
                if test_name in analysis_data["ratings"]:
                    del analysis_data["ratings"][test_name]
                    get_storage().write_json(str(analysis_file), analysis_data)
            
            st.rerun(scope="fragment")
    else:
        # Paste button and file uploader
        paste_col, upload_col = st.columns([1, 1])
        
        paste_key = f"paste_{profile_id if profile_id else 'baseline'}_{idx}_{image_num}" if image_num else f"paste_{profile_id if profile_id else 'baseline'}_{idx}"
        upload_key = f"upload_{profile_id if profile_id else 'baseline'}_{idx}_{image_num}" if image_num else f"upload_{profile_id if profile_id else 'baseline'}_{idx}"
        
        with paste_col:
            image_data = paste(
                label="📋 Paste",
                key=paste_key
            )
            
            if image_data is not None:
                # Decode base64 image
                header, encoded = image_data.split(",", 1)
                binary_data = base64.b64decode(encoded)
                bytes_data = BytesIO(binary_data)
                img = Image.open(bytes_data)
                # Optimize and save as JPEG
                img = optimize_image_for_storage(img)
                filepath = filepath.with_suffix('.jpg')
                save_image(filepath, img, format='JPEG', quality=90)
                st.success("✅ Pasted!")
                st.rerun(scope="fragment")
        
        with upload_col:
            uploaded = st.file_uploader(
                "📤 Upload",
                type=['png', 'jpg', 'jpeg', 'webp'],
                key=upload_key,
                help="Drag & drop or click to browse",
                label_visibility="collapsed"
            )
            
            if uploaded:
                # Optimize and save as JPEG
                img = Image.open(uploaded)
                img = optimize_image_for_storage(img)
                filepath = filepath.with_suffix('.jpg')
                save_image(filepath, img, format='JPEG', quality=90)
                st.success("✅ Saved!")
                st.rerun(scope="fragment")

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
    import openai
    from openai import OpenAI
    import config
    
    # Get API key from config (which loads from .env)
    api_key = config.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env file")
    
    client = OpenAI(api_key=api_key)
    
    # Filter out already-rated tests
    if existing_ratings:
        unrated_tests = [(name, path, row) for name, path, row in uploaded_tests if name not in existing_ratings]
    else:
        unrated_tests = uploaded_tests
    
    # Load prompt template from file (use pathlib.Path for local filesystem)
    import pathlib
    template_path = pathlib.Path(__file__).parent / "analysis_prompt_template.txt"
    with open(template_path, 'r') as f:
        prompt_template = f.read()
    
    # Format the template with profile_id
    prompt_text = prompt_template.format(profile_id=profile_id)
    
    # Prepare batch message content
    message_content = [
        {
            "type": "text",
            "text": prompt_text + "\n\n**Test Images:**"
        }
    ]
    
    # Use unrated tests, limit to first 15 to avoid payload size issues
    batch_tests = unrated_tests[:15]
    
    if len(unrated_tests) == 0:
        return None  # Nothing to rate
    
    # Add each image with its test context
    for idx, (test_name, filepath_or_list, row) in enumerate(batch_tests, 1):
        # Check if this is a multi-image test (filepath is a list)
        is_multi_image = isinstance(filepath_or_list, list)
        
        if is_multi_image:
            # Void test with multiple images
            message_content.append({
                "type": "text",
                "text": f"\n\n**Test {idx}: {test_name}**\nSection: {row['Section']}\nPrompt: {row['Prompt']}\n\n**Purpose**: This test uses {len(filepath_or_list)} unseeded images to reveal pure profile bias. Analyze the COMMONALITIES across all images - recurring visual patterns, color schemes, lighting preferences, textures, and compositional habits that represent the profile's natural defaults."
            })
            
            # Add all images for this void test
            for img_num, filepath in enumerate(filepath_or_list, 1):
                # Read and resize image
                img = load_image(filepath)
                
                # Resize to max 512px on longest side
                max_size = 512
                ratio = max_size / max(img.size)
                if ratio < 1:
                    new_size = tuple(int(dim * ratio) for dim in img.size)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Convert to JPEG
                buffer = BytesIO()
                img.convert('RGB').save(buffer, format='JPEG', quality=85)
                img_data = base64.b64encode(buffer.getvalue()).decode()
                
                # Add image with label
                message_content.append({
                    "type": "text",
                    "text": f"Image {img_num}/{len(filepath_or_list)}:"
                })
                message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_data}",
                        "detail": "low"
                    }
                })
        else:
            # Single image test (normal)
            filepath = filepath_or_list
            
            # Read and resize image to reduce payload size
            img = load_image(filepath)
            
            # Resize to max 512px on longest side (OpenAI low detail uses 512x512)
            max_size = 512
            ratio = max_size / max(img.size)
            if ratio < 1:
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Convert to JPEG to reduce size (PNG can be huge)
            buffer = BytesIO()
            img.convert('RGB').save(buffer, format='JPEG', quality=85)
            img_data = base64.b64encode(buffer.getvalue()).decode()
            
            # Add test context
            message_content.append({
                "type": "text",
                "text": f"\n\n**Test {idx}: {test_name}**\nPrompt: {row['Prompt']}\nSection: {row['Section']}"
            })
            
            # Add image
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_data}",
                    "detail": "low"  # Use low detail for cost efficiency
                }
            })
    
    # Add format instructions - build example with actual test names
    example_test_name = batch_tests[0][0] if batch_tests else "Alpine Stream"
    message_content.append({
        "type": "text",
        "text": f"""

**Output Format (JSON):**
IMPORTANT: Use the actual test names (e.g., "{example_test_name}") as the keys in the "ratings" object, NOT "Test 1", "Test 2", etc.

```json
{{
  "ratings": {{
    "{example_test_name}": {{
      "affinity": "native_fit|workable|resistant",
      "score": 8,
      "confidence": 0.9,
      "commentary": "Commentary here...",
      "color-palette": "Color palette description here..."
    }}
  }}
}}
```

Respond with ONLY the JSON, no other text."""
    })
    
    # Call OpenAI API
    try:
        response = client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {
                    "role": "user",
                    "content": message_content
                }
            ],
            max_completion_tokens=4000,
            temperature=0.7
        )
        
        # Parse response
        response_text = response.choices[0].message.content.strip()
        
        # Extract JSON from response (handle code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        import json
        result = json.loads(response_text)
        
        # Fix test names: remove "Test N: " prefix OR map "Test N" to actual test name
        import re
        if 'ratings' in result:
            # Create a mapping of test index to test name
            test_index_map = {str(idx): name for idx, (name, _, _) in enumerate(batch_tests, 1)}
            
            fixed_ratings = {}
            for key, value in result['ratings'].items():
                # Check if it's "Test N: Name" format - extract Name
                match = re.match(r'^Test (\d+): (.+)$', key)
                if match:
                    clean_key = match.group(2)
                # Check if it's just "Test N" format - map to actual name
                elif re.match(r'^Test (\d+)$', key):
                    test_num = re.match(r'^Test (\d+)$', key).group(1)
                    clean_key = test_index_map.get(test_num, key)
                else:
                    clean_key = key
                fixed_ratings[clean_key] = value
            result['ratings'] = fixed_ratings
        
        return result
    
    except Exception as e:
        st.error(f"OpenAI API Error: {e}")
        raise

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
        response = client.chat.completions.create(
            model="gpt-4o-mini",
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
            temperature=0.7
        )
        
        # Parse response
        response_text = response.choices[0].message.content.strip()
        
        # Extract JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        import json
        result = json.loads(response_text)
        
        # Update analysis data
        analysis_data["profile_label"] = result.get("profile_label", "")
        analysis_data["profile_dna"] = result.get("profile_dna", [])
        
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
    analysis_file = Path("profile_analyses") / f"{profile_id}_analysis.json"
    get_storage().write_json(str(analysis_file), analysis_data)

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
    existing_profiles = []
    storage = get_storage()
    
    # List directories in profile_results
    all_files = storage.list_files("profile_results", "*")
    # Extract unique directory names (profile IDs)
    profile_dirs = set()
    for file_path in all_files:
        # file_path is like "profile_results/profile_id/filename"
        parts = file_path.split('/')
        if len(parts) >= 2 and parts[1] != 'baseline':
            profile_dirs.add(parts[1])
    existing_profiles = sorted(list(profile_dirs))
    
    # Check analysis versions for existing profiles
    profile_versions = {}
    profile_completion = {}
    profile_analyses_dir = Path("profile_analyses")
    
    # Get total test count and test names
    current_tests = tpm.load_tests(status_filter='current')
    total_tests = len(current_tests)
    current_test_names = set(t.get('title', '') for t in current_tests)
    
    for profile in existing_profiles:
        analysis_file = profile_analyses_dir / f"{profile}_analysis.json"
        try:
            # Try to read from storage (works for both local and S3)
            data = get_storage().read_json(str(analysis_file))
            version = data.get('analysis_version', 'unknown')
            profile_versions[profile] = version
            # Check completion - only count ratings for current tests
            ratings = data.get('ratings', {})
            valid_ratings = [t for t in ratings.keys() if t in current_test_names]
            profile_completion[profile] = (len(valid_ratings) == total_tests)
        except:
            # File doesn't exist or can't be read
            profile_versions[profile] = 'unknown'
            profile_completion[profile] = False
    
    # Add option to select from existing profiles or enter new
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if existing_profiles:
            # Create display names with version indicators
            def format_profile_option(profile):
                if not profile:
                    return ""
                version = profile_versions.get(profile, 'unknown')
                is_complete = profile_completion.get(profile, False)
                
                # Build status indicators
                status = ""
                if is_complete:
                    status += "✅ "
                if version == ANALYSIS_PROMPT_VERSION:
                    status += "✓ "
                elif version != 'unknown':
                    status += "⚠️ "
                
                return f"{profile} {status}".strip() if status else profile
            
            profile_options = [""] + existing_profiles
            
            # Restore previous selection if it exists in the list
            default_index = 0
            if st.session_state.profile_id in profile_options:
                default_index = profile_options.index(st.session_state.profile_id)
            
            selected_index = st.selectbox(
                "Select existing profile",
                options=range(len(profile_options)),
                format_func=lambda i: format_profile_option(profile_options[i]),
                index=default_index,
                key="profile_selector_dropdown",
                help="Choose a profile you've already tested (✅ = all tests complete, ✓ = current version, ⚠️ = outdated)"
            )
            selected_profile = profile_options[selected_index]
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
            st.session_state.global_params = global_params
            save_global_params(global_params)
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
        
        # Add fullscreen toggle
        col1, col2 = st.columns([6, 1])
        with col2:
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
        
        # Group by section
        sections = df['Section'].unique()
        
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
                            img_display = load_image(filepath)
                            st.image(img_display, caption=test_name, use_container_width=True)
            
            if len(all_images) < len(df):
                st.warning(f"⚠️ Showing {len(all_images)}/{len(df)} images. Upload missing images to see complete set.")
        
        else:
            # Normal mode - show upload UI with fragments to prevent full page reloads
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
            # Count both .jpg (new) and .png (legacy) images
            saved_images = len(list(output_dir.glob("*.jpg"))) + len(list(output_dir.glob("*.png")))
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
    
    # Initialize or load existing data
    if analysis_file.exists():
        analysis_data = get_storage().read_json(str(analysis_file))
    else:
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
                
                for prof in sorted(profile_dirs):
                    analysis_file = profile_analyses_dir / f"{prof}_analysis.json"
                    try:
                        data = get_storage().read_json(str(analysis_file))
                        all_profiles[prof] = data
                    except Exception as e:
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
        # Only count ratings for tests that actually exist
        current_test_names = set(df['Title'].tolist())
        rated_tests = len([t for t in ratings.keys() if t in current_test_names])
        
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
                
                # Check which are already rated
                already_rated_names = [name for name, _, _ in uploaded_tests if name in analysis_data.get("ratings", {})]
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
                        if analysis_file.exists():
                            # Read and write to create backup
                            data = storage.read_json(str(analysis_file))
                            storage.write_json(str(backup_path), data)
                            backup_created = True
                        else:
                            backup_error = f"Analysis file not found: {analysis_file}"
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
                
                # Check which are already rated
                already_rated_names = [name for name, _, _ in uploaded_tests if name in analysis_data.get("ratings", {})]
                unrated_count = len(uploaded_tests) - len(already_rated_names)
                
                st.info(f"Found {len(uploaded_tests)} uploaded images: {len(already_rated_names)} already rated, {unrated_count} remaining")
                
                if len(uploaded_tests) == 0:
                    st.warning("⚠️ No images uploaded. Please upload images in the Images tab first.")
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
                                    print(f"🔍 DEBUG Before finalize: label='{analysis_data.get('profile_label', 'MISSING')}'")
                                    
                                    if finalize_profile_summary(display_profile_id, analysis_data):
                                        # Debug: show after finalize
                                        label_text = analysis_data.get('profile_label', '(none)')
                                        dna_count = len(analysis_data.get('profile_dna', []))
                                        affinity_summary = analysis_data.get('affinity_summary', {})
                                        print(f"🔍 DEBUG After finalize: label='{label_text}', dna_count={dna_count}, affinity_summary={list(affinity_summary.keys())}")
                                        
                                        save_analysis(display_profile_id, analysis_data)
                                        print(f"🔍 DEBUG After save: Saved to {display_profile_id}_analysis.json")
                                        
                                        # Verify what was saved
                                        import json
                                        saved_data = get_storage().read_json(str(analysis_file))
                                        print(f"🔍 DEBUG Verification: Read back label='{saved_data.get('profile_label', 'MISSING')}'")
                                        
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
                                    batch_result = batch_ai_rate_images(
                                        uploaded_tests=uploaded_tests,
                                        profile_id=display_profile_id,
                                        profile_label=profile_label_suggestion,
                                        existing_ratings=analysis_data.get("ratings", {})
                                    )
                                
                                    if batch_result:
                                        # Note: batch_ai_rate_images now only returns ratings, not profile_label/profile_dna
                                        # Profile Label/DNA will be generated by finalize_profile_summary when all tests complete
                                        
                                        # Update ratings (already cleaned in batch function)
                                        for test_name, rating_data in batch_result.get("ratings", {}).items():
                                            analysis_data["ratings"][test_name] = rating_data
                                        
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
        get_storage().write_json(str(analysis_file), analysis_data)
    
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
                dna_list.append(new_dna.strip())
                analysis_data["profile_dna"] = dna_list
                get_storage().write_json(str(analysis_file), analysis_data)
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
            # Save the new order
            analysis_data["profile_dna"] = sorted_items
            get_storage().write_json(str(analysis_file), analysis_data)
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
                    current_list.pop(idx)
                    analysis_data["profile_dna"] = current_list
                    get_storage().write_json(str(analysis_file), analysis_data)
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
            
            # Check filter
            is_rated = test_name in ratings
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
                
                # Load existing rating if available
                existing_rating = ratings.get(test_name, {})
                
                with st.expander(
                    f"{'✅' if is_rated else '⭐'} {test_name} ({len(image_files)}/8 images)" +
                    (f" - {existing_rating.get('affinity', '').replace('_', ' ').title()} ({existing_rating.get('score', 0)}/10)" if is_rated else ""),
                    expanded=not is_rated
                ):
                    # Show all uploaded void images in a grid
                    st.markdown(f"**{test_name} - {len(image_files)} unseeded images**")
                    st.caption("**Purpose:** Reveal pure profile bias with minimal prompt influence")
                    
                    # Display images in rows of 4
                    for i in range(0, len(image_files), 4):
                        cols = st.columns(4)
                        for j, col in enumerate(cols):
                            if i + j < len(image_files):
                                img_num, filepath = image_files[i + j]
                                with col:
                                    img_display = load_image(filepath)
                                    st.image(img_display, caption=f"#{img_num}", use_container_width=True)
                    
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
                            value=existing_rating.get('score', 5),
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
                                value=existing_rating.get('rendering_style', 5),
                                key=f"rendering_{test_name}",
                                help="How photographic are the results? 1 = Painterly/abstract | 10 = Sharp photographic realism"
                            )
                            style_label = "📷 Photographic" if rendering_style >= 7 else "🎨 Hybrid" if rendering_style >= 4 else "🖌️ Painterly"
                        else:
                            rendering_style = st.slider(
                                "Artistic Strength",
                                min_value=1,
                                max_value=10,
                                value=existing_rating.get('rendering_style', 5),
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
                        value=existing_rating.get('color-palette', ''),
                        placeholder="e.g., consistent warm sepia, recurring blue-purple tones...",
                        key=f"color_palette_{test_name}",
                        help="What color schemes appear repeatedly?"
                    )
                    
                    # Commentary with AI button
                    col_comment, col_ai = st.columns([3, 1])
                    
                    with col_comment:
                        commentary = st.text_area(
                            "Observations (optional)",
                            value=existing_rating.get('commentary', ''),
                            placeholder="What visual elements recur? Lighting patterns? Textures? Compositional habits?",
                            height=100,
                            key=f"commentary_{test_name}"
                        )
                    
                    with col_ai:
                        st.markdown("&nbsp;")  # Spacing
                        has_rating = test_name in analysis_data.get('ratings', {})
                        ai_btn_label = "🔄 Re-rate" if has_rating else "🤖 AI Rate"
                        ai_btn_help = "Generate full AI rating (affinity, score, commentary) - will overwrite existing" if has_rating else "Generate full AI rating using OpenAI Vision"
                        
                        if st.button(ai_btn_label, key=f"ai_comment_{test_name}", help=ai_btn_help, type="secondary" if has_rating else "primary"):
                            with st.spinner("🤖 Analyzing with AI..."):
                                # Get OpenAI API key from config
                                import config
                                api_key = config.OPENAI_API_KEY
                                if not api_key:
                                    st.error("⚠️ OPENAI_API_KEY not set in .env file")
                                else:
                                    try:
                                        # Collect all void image paths
                                        void_image_paths = []
                                        for img_num in range(1, 9):
                                            fp = find_image_file(output_dir, display_profile_id, test_name, image_num=img_num)
                                            if fp:
                                                void_image_paths.append(fp)
                                        
                                        # Create a single-item batch with the list of void images
                                        single_test = [(test_name, void_image_paths, row)]
                                        
                                        # Call the batch function (it will handle the void test)
                                        result = batch_ai_rate_images(single_test, display_profile_id, existing_ratings=None)
                                        
                                        if result and 'ratings' in result and test_name in result['ratings']:
                                            # Update the rating
                                            analysis_data['ratings'][test_name] = result['ratings'][test_name]
                                            save_analysis(display_profile_id, analysis_data)
                                            st.success("✨ Rating generated!")
                                            import time
                                            time.sleep(0.5)
                                            st.rerun()
                                        else:
                                            st.error("❌ No rating returned from AI")
                                    
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                    
                    # Save button
                    if st.button(f"💾 Save Rating for {test_name}", key=f"save_{test_name}"):
                        ratings[test_name] = {
                            "affinity": affinity,
                            "score": score,
                            "confidence": confidence,
                            "rendering_style": rendering_style,
                            "commentary": commentary,
                            "color-palette": color_palette
                        }
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
                        st.info("Upload image in the Images tab first")
                    continue
                
                # Load existing rating if available
                existing_rating = ratings.get(test_name, {})
                
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
                        img_display = load_image(filepath)
                        st.image(img_display, use_container_width=True)
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
                            value=existing_rating.get('score', 5),
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
                            value=existing_rating.get('color-palette', ''),
                            placeholder="e.g., warm earth tones, vibrant neons, muted pastels...",
                            key=f"color_palette_{test_name}",
                            help="Describe the dominant color scheme"
                        )
                        
                        # Commentary with AI generation option
                        col_comment, col_ai = st.columns([4, 1])
                        
                        with col_comment:
                            commentary = st.text_area(
                                "Commentary (optional)",
                                value=existing_rating.get('commentary', ''),
                                placeholder="What works well? What struggles? Any specific observations...",
                                height=100,
                                key=f"commentary_{test_name}"
                            )
                        
                        with col_ai:
                            st.markdown("&nbsp;")  # Spacing
                            has_rating = test_name in analysis_data.get('ratings', {})
                            ai_btn_label = "🔄 Re-rate" if has_rating else "🤖 AI Rate"
                            ai_btn_help = "Generate full AI rating (affinity, score, commentary) - will overwrite existing" if has_rating else "Generate full AI rating using OpenAI Vision"
                            
                            if st.button(ai_btn_label, key=f"ai_comment_{test_name}", help=ai_btn_help, type="secondary" if has_rating else "primary"):
                                with st.spinner("🤖 Analyzing with AI..."):
                                    # Get OpenAI API key from config
                                    import config
                                    api_key = config.OPENAI_API_KEY
                                    if not api_key:
                                        st.error("⚠️ OPENAI_API_KEY not set in .env file")
                                    else:
                                        try:
                                            # Use the batch_ai_rate_images function for consistency
                                            # Create a single-item batch
                                            single_test = [(test_name, filepath, row)]
                                            
                                            # Call the batch function (it will handle just one image)
                                            result = batch_ai_rate_images(single_test, display_profile_id, existing_ratings=None)
                                            
                                            if result and 'ratings' in result and test_name in result['ratings']:
                                                # Update the rating
                                                analysis_data['ratings'][test_name] = result['ratings'][test_name]
                                                save_analysis(display_profile_id, analysis_data)
                                                # Set flag to keep expander open after AI rating
                                                st.session_state[f'just_ai_rated_{test_name}'] = True
                                                st.session_state[f'ai_rated_message_{test_name}'] = f"✨ AI rating completed for {test_name}"
                                                import time
                                                time.sleep(0.3)
                                                st.rerun()
                                            else:
                                                st.error("❌ No rating returned from AI")
                                        
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
                            
                            # Save to file
                            get_storage().write_json(str(analysis_file), analysis_data)
                            
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
        st.image(image_source, caption="Image to Analyze", use_container_width=True)
        
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
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
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
                        max_tokens=1500
                    )
                    
                    analysis_text = response.choices[0].message.content
                    
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
                        
                        # List all analysis files
                        storage = get_storage()
                        analysis_files = storage.list_files("profile_analyses", "*_analysis.json")
                        
                        for file_path in analysis_files:
                            try:
                                import json
                                file_name = file_path.split('/')[-1]
                                profile_id = file_name.replace("_analysis.json", "")
                                data = storage.read_json(file_path)
                                analyses[profile_id] = data
                            except:
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
                                        if test_name in ratings:
                                            rating = ratings[test_name]
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
                                        for test_name, overlap in matching_tests[:3]:
                                            if test_name in ratings:
                                                rating = ratings[test_name]
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
    
    if json_files:
        for json_file_path in json_files:
            try:
                data = storage.read_json(json_file_path)
                file_name = json_file_path.split('/')[-1]
                profile_id = data.get('profile_id', file_name.replace('_analysis.json', ''))
                analyses[profile_id] = data
            except Exception as e:
                st.warning(f"⚠️ Could not load {file_name}: {e}")
        
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
                                    if test_name in ratings:
                                        rating = ratings[test_name]
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
                                        if test_name in ratings:
                                            rating = ratings[test_name]
                                            affinity_emoji = {
                                                'native_fit': '✅',
                                                'workable': '⚠️',
                                                'resistant': '❌'
                                            }.get(rating['affinity'], '❓')
                                            
                                            st.markdown(f"{affinity_emoji} **{test_name}**: {rating['score']}/10 ({rating['affinity']})")
                                            
                                            # Show color palette if available
                                            if 'color_palette' in rating and rating['color_palette']:
                                                st.caption(f"🎨 Palette: {rating['color_palette']}")
                                            
                                            # Show aesthetic commentary for the most relevant test (highest overlap)
                                            if overlap == matching_tests[0][1] and 'commentary' in rating:
                                                with st.container():
                                                    st.markdown(f"*Aesthetic Analysis:* {rating['commentary']}")
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
    st.title("🛠️ Manage Test Prompts")
    st.markdown("Add, edit, archive, and version control your test prompts.")
    
    # Load current tests
    tests = tpm.load_tests()
    
    # Tabs for different operations
    test_tabs = st.tabs(["📋 View Tests", "➕ Add Test", "✏️ Edit Test", "📦 Archive", "📥 Import/Export"])
    
    with test_tabs[0]:  # View Tests
        st.subheader("Current Tests")
        
        # Filter by status and section
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            status_filter = st.selectbox("Status", ["current", "archived", "all"], key="view_status")
        with col2:
            section_filter = st.selectbox("Section", ["ALL", "PHOTO", "ART", "VOID_PHOTO", "VOID_ART"], key="view_section")
        with col3:
            version_filter = st.selectbox("Version", ["ALL", "v1", "v2", "v3"], key="view_version")
        
        # Apply filters
        display_tests = tests
        if status_filter != "all":
            display_tests = [t for t in display_tests if t.get('status') == status_filter]
        if section_filter != "ALL":
            display_tests = [t for t in display_tests if t.get('section') == section_filter]
        if version_filter != "ALL":
            display_tests = [t for t in display_tests if t.get('version') == version_filter]
        
        st.info(f"Showing {len(display_tests)} tests")
        
        # Display tests
        for test in display_tests:
            with st.expander(f"{test.get('section', 'N/A')} | {test.get('title', 'Untitled')} ({test.get('version', 'v1')})"):
                st.markdown(f"**ID:** `{test.get('id', 'N/A')}`")
                st.markdown(f"**Status:** {test.get('status', 'current')}")
                st.markdown(f"**Prompt:** {test.get('prompt', 'N/A')}")
                st.markdown(f"**Parameters:** `{test.get('params', 'N/A')}`")
                st.markdown(f"**Created:** {test.get('created_date', 'N/A')}")
                
                # Show profile analysis for this test
                st.markdown("---")
                st.markdown("#### 📊 Profile Analyses")
                
                # Load all profile analyses
                import json
                profile_analyses_dir = Path("profile_analyses")
                test_title = test.get('title', '')
                
                storage = get_storage()
                analysis_files = storage.list_files("profile_analyses", "*_analysis.json")
                
                profile_ratings = []
                for file_path in analysis_files:
                    try:
                        data = storage.read_json(file_path)
                        file_name = file_path.split('/')[-1]
                        profile_id = data.get('profile_id', file_name.replace('_analysis.json', ''))
                        profile_label = data.get('profile_label', 'No label')
                        ratings = data.get('ratings', {})
                        
                        # Find rating for this test
                        if test_title in ratings:
                            rating_data = ratings[test_title]
                            profile_ratings.append({
                                'profile_id': profile_id,
                                'label': profile_label,
                                'affinity': rating_data.get('affinity', 'unknown'),
                                'score': rating_data.get('score', 0),
                                'confidence': rating_data.get('confidence', 0),
                                'commentary': rating_data.get('commentary', 'No commentary')
                            })
                    except Exception as e:
                        pass
                
                if profile_ratings:
                    # Sort by score descending
                    profile_ratings.sort(key=lambda x: x['score'], reverse=True)
                    
                    # Summary stats
                    affinity_counts = {
                        'native_fit': sum(1 for r in profile_ratings if r['affinity'] == 'native_fit'),
                        'workable': sum(1 for r in profile_ratings if r['affinity'] == 'workable'),
                        'resistant': sum(1 for r in profile_ratings if r['affinity'] == 'resistant')
                    }
                    avg_score = sum(r['score'] for r in profile_ratings) / len(profile_ratings) if profile_ratings else 0
                    
                    st.markdown(f"**Summary:** {len(profile_ratings)} profiles rated | Avg: {avg_score:.1f}/10 | ✅ {affinity_counts['native_fit']} native | ⚠️ {affinity_counts['workable']} workable | ❌ {affinity_counts['resistant']} resistant")
                    
                    # Build single text with all profiles
                    all_profiles_text = []
                    for rating in profile_ratings:
                        affinity_emoji = {'native_fit': '✅', 'workable': '⚠️', 'resistant': '❌'}.get(rating['affinity'], '❓')
                        
                        # Handle confidence - convert to float or use as-is if it's a string like "Medium"
                        confidence = rating.get('confidence', 0.0)
                        try:
                            confidence_display = f"{float(confidence):.0%}"
                        except (ValueError, TypeError):
                            confidence_display = str(confidence)
                        
                        profile_text = f"{affinity_emoji} {rating['profile_id']} - \"{rating['label']}\" | Score: {rating['score']}/10 | Affinity: {rating['affinity']} | Confidence: {confidence_display}\n\n{rating['commentary']}\n"
                        all_profiles_text.append(profile_text)
                    
                    # Display in single text area
                    combined_text = "\n" + "="*80 + "\n\n".join(all_profiles_text)
                    st.text_area("All Profile Analyses", combined_text, height=400, key=f"analysis_{test.get('id', '')}")
                else:
                    st.info("No profile ratings found for this test")
                
                # Add button to run analysis for all profiles for this test
                st.markdown("---")
                test_id_for_button = test.get('id', '')
                if st.button(f"🤖 Run AI Analysis for All Profiles", key=f"analyze_all_{test_id_for_button}", help="Analyze this test across all profiles that have uploaded images"):
                    # Find all profiles with images for this test
                    profiles_to_analyze = []
                    all_profile_dirs = storage.list_files("profile_results", "*")
                    profile_ids = set()
                    for file_path in all_profile_dirs:
                        parts = file_path.split('/')
                        if len(parts) >= 2:
                            profile_ids.add(parts[1])
                    
                    # Check which profiles have images for this test
                    for prof_id in profile_ids:
                        output_dir = Path(f"profile_results/{prof_id}")
                        img_path = find_image_file(output_dir, prof_id, test_title, None)
                        if img_path:
                            profiles_to_analyze.append(prof_id)
                    
                    if not profiles_to_analyze:
                        st.warning("⚠️ No profiles found with uploaded images for this test")
                    else:
                        with st.spinner(f"🤖 Analyzing {len(profiles_to_analyze)} profiles for test '{test_title}'..."):
                            import config
                            if not config.OPENAI_API_KEY:
                                st.error("❌ OpenAI API key not configured")
                            else:
                                success_count = 0
                                error_count = 0
                                
                                for prof_id in profiles_to_analyze:
                                    try:
                                        # Load existing analysis
                                        analysis_file = Path("profile_analyses") / f"{prof_id}_analysis.json"
                                        analysis_data = storage.read_json(str(analysis_file))
                                        
                                        if not analysis_data:
                                            # Create new analysis structure if doesn't exist
                                            analysis_data = {
                                                'profile_id': prof_id,
                                                'ratings': {},
                                                'profile_label': '',
                                                'profile_dna': []
                                            }
                                        
                                        # Get the image path
                                        output_dir = Path(f"profile_results/{prof_id}")
                                        img_path = find_image_file(output_dir, prof_id, test_title, None)
                                        
                                        if img_path:
                                            # Convert to string to ensure compatibility
                                            img_path_str = str(img_path)
                                            
                                            # Create a row dict with the expected keys (capital letters)
                                            test_row = {
                                                'Title': test.get('title', ''),
                                                'Prompt': test.get('prompt', ''),
                                                'Section': test.get('section', ''),
                                                'Parameter Values': test.get('params', '')
                                            }
                                            
                                            # Rate this single test
                                            result = batch_ai_rate_images(
                                                uploaded_tests=[(test_title, img_path_str, test_row)],
                                                profile_id=prof_id,
                                                profile_label=analysis_data.get('profile_label', ''),
                                                existing_ratings=analysis_data.get('ratings', {})
                                            )
                                            
                                            if result and 'ratings' in result and test_title in result['ratings']:
                                                # Update the rating for this test
                                                analysis_data['ratings'][test_title] = result['ratings'][test_title]
                                                
                                                # Save updated analysis
                                                save_analysis(prof_id, analysis_data)
                                                success_count += 1
                                            else:
                                                error_count += 1
                                        
                                    except Exception as e:
                                        st.error(f"Error analyzing {prof_id}: {str(e)}")
                                        error_count += 1
                                
                                if success_count > 0:
                                    st.success(f"✅ Successfully analyzed {success_count} profile(s)")
                                if error_count > 0:
                                    st.warning(f"⚠️ {error_count} profile(s) failed")
                                
                                st.rerun()
    
    with test_tabs[1]:  # Add Test
        st.subheader("Add New Test")
        
        with st.form("add_test_form"):
            new_title = st.text_input("Title", placeholder="Moody Foggy Forest")
            new_section = st.selectbox("Section", ["PHOTO", "ART", "VOID_PHOTO", "VOID_ART"])
            new_prompt = st.text_area("Prompt", height=100, placeholder="A moody foggy forest at dawn...")
            new_params = st.text_input("Parameters", value="--ar 16:9 --stylize 1000", placeholder="--ar 16:9 --stylize 1000")
            new_version = st.selectbox("Version", ["v1", "v2", "v3"])
            
            submitted = st.form_submit_button("➕ Add Test", type="primary")
            
            if submitted:
                if not new_title or not new_prompt:
                    st.error("❌ Title and Prompt are required")
                else:
                    # Create test ID from title
                    test_id = f"{new_section}_{new_title.replace(' ', '_')}"
                    
                    # Check if ID already exists
                    if any(t.get('id') == test_id for t in tests):
                        st.error(f"❌ Test ID '{test_id}' already exists. Choose a different title.")
                    else:
                        try:
                            tpm.add_test(
                                title=new_title,
                                prompt=new_prompt,
                                section=new_section,
                                params=new_params,
                                version=new_version
                            )
                            st.success(f"✅ Added test: {new_title}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error adding test: {e}")
    
    with test_tabs[2]:  # Edit Test
        st.subheader("Edit Existing Test")
        
        # Select test to edit
        test_titles = [f"{t.get('section', 'N/A')} | {t.get('title', 'Untitled')}" for t in tests]
        if test_titles:
            selected_test_idx = st.selectbox("Select Test", range(len(test_titles)), format_func=lambda i: test_titles[i])
            selected_test = tests[selected_test_idx]
            
            with st.form("edit_test_form"):
                edit_title = st.text_input("Title", value=selected_test.get('title', ''))
                sections = ["PHOTO", "ART", "VOID_PHOTO", "VOID_ART"]
                current_section = selected_test.get('section', 'PHOTO')
                section_index = sections.index(current_section) if current_section in sections else 0
                edit_section = st.selectbox("Section", sections, index=section_index)
                edit_prompt = st.text_area("Prompt", value=selected_test.get('prompt', ''), height=100)
                edit_params = st.text_input("Parameters", value=selected_test.get('params', ''))
                
                # Safely get version index
                test_version = selected_test.get('version', 'v2')
                try:
                    version_index = ["v1", "v2", "v3"].index(test_version)
                except (ValueError, TypeError):
                    version_index = 1  # Default to v2
                
                edit_version = st.selectbox("Version", ["v1", "v2", "v3"], index=version_index)
                edit_status = st.selectbox("Status", ["current", "archived"], index=0 if selected_test.get('status') == 'current' else 1)
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    update_btn = st.form_submit_button("💾 Update Test", type="primary")
                with col2:
                    duplicate_btn = st.form_submit_button("📋 Duplicate Test")
                
                if update_btn:
                    try:
                        tpm.update_test(
                            test_id=selected_test['id'],
                            title=edit_title,
                            prompt=edit_prompt,
                            section=edit_section,
                            params=edit_params,
                            version=edit_version,
                            status=edit_status
                        )
                        st.success(f"✅ Updated test: {edit_title}")
                        
                        # Show prompts for all profiles
                        st.markdown("---")
                        st.markdown("### 📝 Generate New Images for Updated Test")
                        st.info("Copy these prompts to regenerate images for all profiles with this test:")
                        
                        # Get all profiles
                        storage = get_storage()
                        all_profile_dirs = storage.list_files("profile_results", "*")
                        profile_ids = set()
                        for file_path in all_profile_dirs:
                            parts = file_path.split('/')
                            if len(parts) >= 2:
                                profile_ids.add(parts[1])
                        
                        # Build prompts for each profile
                        all_prompts = []
                        
                        # Add baseline prompt (no profile)
                        baseline_prompt = f"{edit_prompt} {edit_params}"
                        all_prompts.append(f"# Baseline (no profile)\n{baseline_prompt}")
                        
                        # Add prompts for each profile
                        for prof_id in sorted(profile_ids):
                            if prof_id != 'baseline':
                                profile_prompt = f"{edit_prompt} {edit_params} --p {prof_id}"
                                all_prompts.append(f"# Profile: {prof_id}\n{profile_prompt}")
                        
                        # Display in text area for easy copying
                        prompts_text = "\n\n".join(all_prompts)
                        st.text_area(
                            f"Prompts for '{edit_title}'",
                            value=prompts_text,
                            height=400,
                            key=f"updated_prompts_{selected_test['id']}"
                        )
                        
                    except Exception as e:
                        st.error(f"❌ Error updating test: {e}")
                
                if duplicate_btn:
                    try:
                        # Auto-increment version for duplicate
                        version_map = {'v1': 'v2', 'v2': 'v3', 'v3': 'v3'}
                        new_version = version_map.get(edit_version, 'v2')
                        
                        tpm.duplicate_test(selected_test['id'], new_version=new_version)
                        st.success(f"✅ Duplicated test as version {new_version}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error duplicating test: {e}")
        else:
            st.info("No tests available to edit")
    
    with test_tabs[3]:  # Archive
        st.subheader("Archive Tests")
        st.markdown("Archived tests are hidden from active use but preserved for reference.")
        
        # Show current tests that can be archived
        current_tests = [t for t in tests if t.get('status') == 'current']
        
        if current_tests:
            for idx, test in enumerate(current_tests):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{test.get('title', 'Untitled')}** ({test.get('version', 'v1')})")
                with col2:
                    if st.button("📦 Archive", key=f"archive_{idx}_{test.get('id', idx)}"):
                        try:
                            tpm.archive_test(test['id'])
                            st.success(f"✅ Archived: {test.get('title')}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
        else:
            st.info("No current tests to archive")
        
        st.markdown("---")
        
        # Show archived tests that can be restored
        archived_tests = [t for t in tests if t.get('status') == 'archived']
        
        if archived_tests:
            st.subheader("Restore Archived Tests")
            for idx, test in enumerate(archived_tests):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{test.get('title', 'Untitled')}** ({test.get('version', 'v1')})")
                with col2:
                    if st.button("♻️ Restore", key=f"restore_{idx}_{test.get('id', idx)}"):
                        try:
                            tpm.update_test(test['id'], status='current')
                            st.success(f"✅ Restored: {test.get('title')}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
    
    with test_tabs[4]:  # Import/Export
        st.subheader("Import/Export Tests")
        
        # Export
        st.markdown("### 📤 Export Tests")
        col1, col2 = st.columns([1, 1])
        with col1:
            export_status = st.selectbox("Export Status", ["current", "archived", "all"], key="export_status")
        with col2:
            export_format = st.selectbox("Format", ["JSON", "CSV"])
        
        if st.button("📥 Download Tests", type="primary"):
            export_tests = tests
            if export_status != "all":
                export_tests = [t for t in tests if t.get('status') == export_status]
            
            if export_format == "JSON":
                import json
                json_str = json.dumps(export_tests, indent=2)
                st.download_button(
                    label="💾 Download JSON",
                    data=json_str,
                    file_name=f"test_prompts_{export_status}.json",
                    mime="application/json"
                )
            else:  # CSV
                import pandas as pd
                df = pd.DataFrame(export_tests)
                csv_str = df.to_csv(index=False)
                st.download_button(
                    label="💾 Download CSV",
                    data=csv_str,
                    file_name=f"test_prompts_{export_status}.csv",
                    mime="text/csv"
                )
        
        st.markdown("---")
        
        # Import
        st.markdown("### 📥 Import Tests")
        uploaded_file = st.file_uploader("Upload JSON or CSV file", type=["json", "csv"])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.json'):
                    import json
                    imported_tests = json.load(uploaded_file)
                else:  # CSV
                    import pandas as pd
                    df = pd.read_csv(uploaded_file)
                    
                    # Handle different CSV formats (old Google Sheets format vs new format)
                    # Old format: Section, Title, Prompt, Parameter Category, Parameter Values
                    # New format: section, title, prompt, params, status, version, created_date
                    
                    # Normalize column names
                    df_normalized = df.copy()
                    column_mapping = {
                        'Title': 'title',
                        'Prompt': 'prompt',
                        'Section': 'section',
                        'Parameter Values': 'params',
                        'Parameter Category': 'param_category'  # We'll ignore this
                    }
                    df_normalized = df_normalized.rename(columns=column_mapping)
                    
                    imported_tests = df_normalized.to_dict('records')
                
                st.info(f"Found {len(imported_tests)} tests in file")
                
                # Show preview of what will be imported
                with st.expander("📋 Preview First 3 Tests"):
                    for i, test in enumerate(imported_tests[:3], 1):
                        st.markdown(f"**{i}. {test.get('title', test.get('Title', 'Untitled'))}**")
                        st.markdown(f"- Section: {test.get('section', test.get('Section', 'N/A'))}")
                        st.markdown(f"- Prompt: {test.get('prompt', test.get('Prompt', 'N/A'))[:80]}...")
                        st.markdown(f"- Params: {test.get('params', test.get('Parameter Values', 'N/A'))}")
                
                if st.button("➕ Import Tests", type="primary"):
                    added = 0
                    errors = []
                    
                    for test in imported_tests:
                        try:
                            # Get values with fallbacks for different formats
                            title = test.get('title', test.get('Title', 'Imported Test'))
                            prompt = test.get('prompt', test.get('Prompt', ''))
                            section = test.get('section', test.get('Section', 'PHOTO'))
                            params = test.get('params', test.get('Parameter Values', ''))
                            version = test.get('version', 'v1')  # Default to v1 for old imports
                            status = test.get('status', 'current')
                            
                            # Skip if no title or prompt
                            if not title or not prompt:
                                errors.append(f"Skipped test with missing title or prompt")
                                continue
                            
                            # Generate test ID
                            test_id = f"{section}_{title.replace(' ', '_').replace('/', '_')}"
                            
                            # Check if test ID already exists
                            if not any(t.get('id') == test_id for t in tests):
                                tpm.add_test(
                                    title=title,
                                    prompt=prompt,
                                    section=section,
                                    params=params,
                                    version=version,
                                    status=status
                                )
                                added += 1
                            else:
                                errors.append(f"Skipped duplicate: {test_id}")
                        except Exception as e:
                            errors.append(f"Error importing {title}: {e}")
                    
                    st.success(f"✅ Imported {added} tests")
                    if errors:
                        st.warning(f"⚠️ {len(errors)} errors:\n" + "\n".join(errors[:5]))
                    st.rerun()
            
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")

else:
    st.info("👆 Enter a profile ID to generate test prompts")
    
    # Show instructions
    with st.expander("ℹ️ How to use"):
        st.markdown("""
        **Prompts Page:**
        1. Enter a MidJourney profile ID (e.g., `9hoxpdm`)
        2. Copy prompts individually or all at once
        3. Paste into MidJourney to generate images
        
        **Images Grid Page:**
        1. Upload the generated images for each test
        2. Images are saved to `profile_results/{profile_id}/`
        3. Grid shows 5 images per row (20 total)
        
        **Rate Page (Recommended):**
        1. View each uploaded image with its test prompt
        2. Rate affinity (Native Fit/Workable/Resistant) and score (1-10)
        3. Add commentary per test
        4. Add Profile DNA traits as you notice patterns
        5. Auto-saves to recommendation engine database
        
        **Parse Page (Alternative):**
        1. Enter a new prompt you want to generate
        2. System analyzes similarity to test categories
        3. Recommends best profiles based on historical performance
        4. Shows confidence scores and Profile DNA traits
        
        The app automatically applies:
        - Photography-specific parameters for photography tests
        - Art-specific parameters for 2D art tests
        - Your profile ID to each prompt
        """)

