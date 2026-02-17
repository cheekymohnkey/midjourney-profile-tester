import time
import json
import datetime
from pathlib import Path
import streamlit as st
from services.test_data_service import get_test_data_service
tpm = get_test_data_service()
from storage import get_storage
from services.test_runner import run_test_for_profile
from services.analysis import score_v1_from_checks
import logging
from services.results_data_service import get_results_data_service

logger = logging.getLogger(__name__)


def _build_summary_from_rating(rating):
    """Return the best available short summary for a rating.

    Preference order: `notes` -> `commentary` -> auto-build from checks/metrics.
    """
    if not rating:
        return "No commentary or analysis details available."
    notes = rating.get('notes')
    if notes:
        return notes
    commentary = rating.get('commentary')
    if commentary:
        return commentary

    checks = rating.get('checks', {}) or {}
    must = checks.get('must', []) or []
    avoid = checks.get('avoid', []) or []
    prefer = checks.get('prefer', []) or []

    parts = []
    if must:
        must_pass = sum(1 for c in must if c.get('pass'))
        parts.append(f"MUST passed {must_pass}/{len(must)}")
    if avoid:
        avoid_present = sum(1 for c in avoid if c.get('present'))
        parts.append(f"AVOID present {avoid_present}/{len(avoid)}")
    if prefer:
        pref_vals = [c.get('rating', 0) for c in prefer]
        if pref_vals:
            parts.append(f"PREFER avg {sum(pref_vals)/len(pref_vals):.2f}/2")

    failure_modes = rating.get('failure_modes') or []
    if failure_modes:
        parts.append("Failures: " + ", ".join(failure_modes[:3]))

    metrics = rating.get('metrics_v1') or rating.get('metrics') or {}
    if metrics:
        try:
            mstr = f"metrics must={metrics.get('must_pass_rate', '?')}, avoid={metrics.get('avoid_clean_rate', '?')}, prefer={metrics.get('prefer_rate', '?')}"
            parts.append(mstr)
        except Exception:
            pass

    if parts:
        return "; ".join(parts)
    return "No commentary or analysis details available."


def render_tests_page(
    batch_ai_rate_images,
    render_test_upload,
    find_image_file,
    save_analysis,
    get_all_profile_analyses,
    get_existing_profile_ids,
    load_image_cached,
    get_profile_image_files,
    count_profile_images,
    filter_seed_from_params,
):
    """Render the Tests management page.

    This function is intentionally self-contained and receives the few helpers
    that remain implemented in `midjourney_profile_tester.py` to avoid
    circular imports.
    """
    

    debug_container = st.empty()
    start_time = time.time()
    debug_log = []
    debug_log.append(f"[{time.time() - start_time:.2f}s] Tests page load started")
    debug_container.code("\n".join(debug_log))

    st.title("🛠️ Manage Test Prompts")
    st.markdown("Add, edit, archive, and version control your test prompts.")

    # Load current tests
    tests = tpm.list_tests()
    debug_log.append(f"[{time.time() - start_time:.2f}s] Loaded {len(tests)} tests from TestDataService.list_tests()")
    debug_container.code("\n".join(debug_log))

    # Cache all image files (jpg and png) once for this page load
    storage = __import__("storage").get_storage()
    rds = get_results_data_service()
    debug_log.append(f"[{time.time() - start_time:.2f}s] Listing all image files (jpg/png) once for all tests...")
    debug_container.code("\n".join(debug_log[-10:]))
    try:
        all_jpg_files = storage.list_files("profile_results", "*.jpg")
        all_png_files = storage.list_files("profile_results", "*.png")
        all_image_files_for_tests = all_jpg_files + all_png_files
        debug_log.append(f"[{time.time() - start_time:.2f}s] Found {len(all_image_files_for_tests)} total image files.")
    except Exception as e:
        all_image_files_for_tests = []
        debug_log.append(f"[{time.time() - start_time:.2f}s] Error listing image files: {e}")
    debug_container.code("\n".join(debug_log[-10:]))

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
            debug_log.append(f"[{time.time() - start_time:.2f}s] Rendering expander for test: {test.get('title', 'Untitled')}")
            debug_container.code("\n".join(debug_log[-10:]))

            with st.expander(f"{test.get('section', 'N/A')} | {test.get('title', 'Untitled')} ({test.get('version', 'v1')})"):
                st.markdown(f"**ID:** `{test.get('id', 'N/A')}`")
                st.markdown(f"**GUID:** `{test.get('id') or test.get('guid', 'N/A')}`")
                st.markdown(f"**Status:** {test.get('status', 'current')}")
                st.markdown(f"**Prompt:** {test.get('prompt', 'N/A')}")
                st.markdown(f"**Parameters:** `{test.get('params', 'N/A')}`")
                st.markdown(f"**Created:** {test.get('created_date', 'N/A')}")

                # Metadata & Rubric
                st.markdown("---")
                with st.expander("Metadata & Rubric", expanded=False):
                    asv = test.get('analysis_spec_version', '')
                    tv = test.get('taxonomy_version', '')
                    intent = test.get('intent', '')
                    af = test.get('analysis_family', '')
                    if asv:
                        st.markdown(f"- **Analysis Spec Version:** {asv}")
                    if tv:
                        st.markdown(f"- **Taxonomy Version:** {tv}")
                    if intent:
                        st.markdown(f"- **Intent:** {intent}")
                    if af:
                        st.markdown(f"- **Analysis Family:** {af}")

                    rubric = test.get('rubric', {}) or {}
                    if rubric:
                        must = rubric.get('must', [])
                        avoid = rubric.get('avoid', [])
                        prefer = rubric.get('prefer', [])
                        weights = rubric.get('weights', {})
                        notes = rubric.get('notes', '')

                        if must:
                            st.markdown("**Rubric — MUST**")
                            for item in must:
                                st.markdown(f"- {item}")
                        if avoid:
                            st.markdown("**Rubric — AVOID**")
                            for item in avoid:
                                st.markdown(f"- {item}")
                        if prefer:
                            st.markdown("**Rubric — PREFER**")
                            for item in prefer:
                                st.markdown(f"- {item}")

                        if weights:
                            st.markdown(f"**Weights:** must={weights.get('must')}, avoid={weights.get('avoid')}, prefer={weights.get('prefer')}")
                        if notes:
                            st.markdown(f"**Notes:** {notes}")

                # Profile Analyses
                st.markdown("---")
                debug_log.append(f"[{time.time() - start_time:.2f}s]   Entering Profile Analyses expander for test: {test.get('title', 'Untitled')}")
                debug_container.code("\n".join(debug_log[-10:]))
                with st.expander("📊 Profile Analyses", expanded=False):
                    expander_key = f"profile_analyses_expanded_{test.get('id', '')}"
                    expanded = st.checkbox("Show Profile Analyses", key=expander_key)
                    if expanded:
                        test_title = test.get('title', '')
                        test_key = test.get('id') or test.get('guid') or test_title
                        all_analyses = get_all_profile_analyses()
                        profile_ratings = []
                        for profile_id, data in all_analyses.items():
                            try:
                                profile_label = data.get('profile_label', 'No label')
                                ratings = data.get('ratings', {})
                                rating_data = ratings.get(test_key) or ratings.get(test_title)
                                if rating_data:
                                    profile_ratings.append({
                                        'profile_id': profile_id,
                                        'label': profile_label,
                                        'affinity': rating_data.get('affinity', 'unknown'),
                                        'score': rating_data.get('score', 0),
                                        'confidence': rating_data.get('confidence', 0),
                                        'commentary': rating_data.get('commentary'),
                                        'notes': rating_data.get('notes'),
                                        'color_palette': rating_data.get('color_palette'),
                                        'checks': rating_data.get('checks'),
                                        'metrics_v1': rating_data.get('metrics_v1') or rating_data.get('metrics'),
                                        'failure_modes': rating_data.get('failure_modes') or []
                                    })
                            except Exception:
                                pass
                        if profile_ratings:
                            profile_ratings.sort(key=lambda x: x['score'], reverse=True)
                            affinity_counts = {
                                'native_fit': sum(1 for r in profile_ratings if r['affinity'] == 'native_fit'),
                                'workable': sum(1 for r in profile_ratings if r['affinity'] == 'workable'),
                                'resistant': sum(1 for r in profile_ratings if r['affinity'] == 'resistant')
                            }
                            avg_score = sum(r['score'] for r in profile_ratings) / len(profile_ratings) if profile_ratings else 0
                            st.markdown(f"**Summary:** {len(profile_ratings)} profiles rated | Avg: {avg_score:.1f}/10 | ✅ {affinity_counts['native_fit']} native | ⚠️ {affinity_counts['workable']} workable | ❌ {affinity_counts['resistant']} resistant")
                            all_profiles_text = []
                            for rating in profile_ratings:
                                affinity_emoji = {'native_fit': '✅', 'workable': '⚠️', 'resistant': '❌'}.get(rating['affinity'], '❓')
                                confidence = rating.get('confidence', 0.0)
                                try:
                                    confidence_display = f"{float(confidence):.0%}"
                                except (ValueError, TypeError):
                                    confidence_display = str(confidence)

                                # Build a readable summary (prefer notes -> commentary -> auto-build)
                                summary = _build_summary_from_rating({
                                    'notes': rating.get('notes'),
                                    'commentary': rating.get('commentary'),
                                    'checks': rating.get('checks'),
                                    'metrics_v1': rating.get('metrics_v1'),
                                    'failure_modes': rating.get('failure_modes')
                                })

                                # Color palette and metrics (textual) for quick scanning
                                palette = rating.get('color_palette')
                                palette_text = ''
                                if palette:
                                    if isinstance(palette, dict):
                                        dom = palette.get('dominant_hues') or palette.get('dominant') or []
                                        acc = palette.get('accent_hues') or palette.get('accent') or []
                                        sat = palette.get('saturation_level')
                                        temp = palette.get('temperature_bias')
                                        parts = []
                                        if dom:
                                            parts.append(f"dominant={dom}")
                                        if acc:
                                            parts.append(f"accent={acc}")
                                        if sat:
                                            parts.append(f"saturation={sat}")
                                        if temp:
                                            parts.append(f"temperature={temp}")
                                        palette_text = ", ".join(parts)
                                    else:
                                        # fallback: stringify
                                        palette_text = str(palette)

                                metrics = rating.get('metrics_v1') or {}
                                weights = ''
                                if metrics and isinstance(metrics, dict):
                                    w = metrics.get('weights')
                                    if w:
                                        weights = f"weights={w}"

                                profile_text = (
                                    f"{affinity_emoji} {rating['profile_id']} - \"{rating['label']}\" | Score: {rating['score']}/10 | Affinity: {rating['affinity']} | Confidence: {confidence_display}\n"
                                    + (f"Color Palette: {palette_text}\n" if palette_text else "")
                                    + (f"{weights}\n" if weights else "")
                                    + f"\n{summary}\n"
                                )
                                all_profiles_text.append(profile_text)
                            combined_text = "\n" + "="*80 + "\n\n".join(all_profiles_text)
                            st.text_area("All Profile Analyses", combined_text, height=400, key=f"analysis_{test.get('id', '')}")
                            # Rescore button: call scorer for every profile rating and log inputs/outputs to server console
                            if st.button("🔢 Re-Score All (console)", key=f"rescore_all_btn_{test.get('id','')}"):
                                res_count = 0
                                for rating in profile_ratings:
                                    prof = rating.get('profile_id')
                                    try:
                                        analysis_data = rds.read_analysis(prof) or {}
                                        rating_key = test.get('id') or test.get('guid') or test.get('title')
                                        ratings_dict = analysis_data.get('ratings', {})
                                        rating_data = ratings_dict.get(rating_key) or ratings_dict.get(test.get('title'))
                                        if not rating_data:
                                            continue
                                        checks = rating_data.get('checks', {}) or {}
                                        metrics = rating_data.get('metrics_v1') or rating_data.get('metrics') or {}
                                        # Delegate scoring to centralized scoring service which
                                        # will lookup authoritative rubrics by test id/guid.
                                        try:
                                            from services.score_service import apply_scores_to_result
                                            parsed_for_scoring = {'ratings': {rating_key: {'checks': checks, 'test_id': rating_key}}}
                                            scored = apply_scores_to_result(parsed_for_scoring)
                                            scored_rating = scored.get('ratings', {}).get(rating_key)
                                            logger.info('[UI RESCORE] Scored rating_key=%s score=%s affinity=%s', rating_key, scored_rating.get('score'), scored_rating.get('affinity'))
                                        except Exception as e:
                                            logger.exception('[UI RESCORE] Failed to score rating_key=%s: %s', rating_key, e)
                                        res_count += 1
                                    except Exception as e:
                                        st.error(f"Failed to rescore {prof}: {e}")
                                st.success(f"Rescored {res_count} profile(s) — check server console for details")
                            if st.button("🤖 Analyze Missing Across Profiles", key=f"analyze_missing_btn_{test.get('id','')}"):
                                all_profile_ids_local = get_existing_profile_ids()
                                profiles_to_check = [''] + all_profile_ids_local
                                progress = st.progress(0)
                                total = len(profiles_to_check)
                                done = 0
                                analyzed = 0
                                skipped = 0
                                errors = []
                                for prof in profiles_to_check:
                                    try:
                                        prof_id_check = prof if prof else 'baseline'
                                        # Check existing rating to avoid overwriting in the "Analyze Missing" flow
                                        analysis_data = rds.read_analysis(prof_id_check) or {"ratings": {}}
                                        rating_key = test.get('id') or test.get('guid') or test.get('title')
                                        existing_ratings_dict = analysis_data.get('ratings', {})
                                        if rating_key in existing_ratings_dict or test.get('title') in existing_ratings_dict:
                                            skipped += 1
                                            done += 1
                                            progress.progress(int(done/total*100))
                                            continue

                                        # Delegate to shared runner which handles image collection, calling the LLM, and saving
                                        try:
                                            res = run_test_for_profile(test, prof, find_image_file, save_analysis)
                                            if res.get('status') == 'ok' and res.get('saved'):
                                                analyzed += 1
                                            elif res.get('status') == 'no_images':
                                                skipped += 1
                                            else:
                                                errors.append(f"{prof_id_check}: {res.get('error')}")
                                        except Exception as e:
                                            errors.append(f"{prof_id_check}: {e}")

                                    except Exception as e:
                                        errors.append(f"{prof if prof else 'baseline'}: {e}")
                                    done += 1
                                    progress.progress(int(done/total*100))

                                st.success(f"Analysis complete — {analyzed} analyzed, {skipped} skipped, {len(errors)} errors")
                                if errors:
                                    for err in errors:
                                        st.error(err)
                            # Force re-analyze button (overwrites existing ratings)
                            if st.button("🔁 Re-Analyze All Profiles (force)", key=f"reanalyse_all_btn_{test.get('id','')}"):
                                all_profile_ids_local = get_existing_profile_ids()
                                profiles_to_check = [''] + all_profile_ids_local
                                progress = st.progress(0)
                                total = len(profiles_to_check)
                                done = 0
                                analyzed = 0
                                skipped = 0
                                errors = []
                                for prof in profiles_to_check:
                                    try:
                                        res = run_test_for_profile(test, prof, find_image_file, save_analysis)
                                        if res.get('status') == 'ok' and res.get('saved'):
                                            analyzed += 1
                                        elif res.get('status') == 'no_images':
                                            skipped += 1
                                        else:
                                            errors.append(f"{prof if prof else 'baseline'}: {res.get('error')}")
                                    except Exception as e:
                                        errors.append(f"{prof if prof else 'baseline'}: {e}")
                                    done += 1
                                    progress.progress(int(done/total*100))

                                st.success(f"Re-analysis complete — {analyzed} analyzed, {skipped} skipped, {len(errors)} errors")
                                if errors:
                                    for err in errors:
                                        st.error(err)
                        else:
                            st.info("No profile ratings found for this test")

                st.markdown("---")
                st.markdown("#### 🖼️ Test Images Across Profiles")
                debug_log.append(f"[{time.time() - start_time:.2f}s]   Entering Images expander for test: {test.get('title', 'Untitled')}")
                debug_container.code("\n".join(debug_log[-10:]))
                with st.expander("Show images from all profiles", expanded=False):
                    expander_key = f"images_expanded_{test.get('id', '')}"
                    expanded = st.checkbox("Show Images", key=expander_key)
                    if expanded:
                        test_title = test.get('title', '')
                        if test_title:
                            test_title_filename = test_title.replace(' ', '_')
                            # Get all profile IDs
                            all_profile_ids = get_existing_profile_ids()

                            st.markdown("---")
                            st.markdown("### 📤 Upload Images for This Test Across All Profiles")

                            # Baseline upload/delete using shared helper (show individual preview)
                            baseline_dir = Path(f"profile_results/baseline")
                            baseline_dir.mkdir(parents=True, exist_ok=True)
                            render_test_upload('', test_title, baseline_dir, f"{test.get('id', '')}_baseline", show_preview=True)

                            # Profile upload/delete controls using shared helper
                            for prof_id in all_profile_ids:
                                prof_dir = Path(f"profile_results/{prof_id}")
                                prof_dir.mkdir(parents=True, exist_ok=True)
                                render_test_upload(prof_id, test_title, prof_dir, f"{test.get('id', '')}_{prof_id}", show_preview=True)

                            # Analyze missing ratings across profiles
                            col_a, col_b = st.columns([3, 1])
                            with col_a:
                                st.markdown("<br>", unsafe_allow_html=True)
                                if st.button("🤖 Analyze Missing Across Profiles", key=f"analyze_missing_{test.get('id','')}"):
                                    # Gather profiles to check (include baseline as empty id)
                                    profiles_to_check = [''] + all_profile_ids
                                    progress = st.progress(0)
                                    total = len(profiles_to_check)
                                    done = 0
                                    analyzed = 0
                                    skipped = 0
                                    errors = []
                                    for p_idx, prof in enumerate(profiles_to_check):
                                        try:
                                            prof_id_check = prof if prof else 'baseline'
                                            # Skip profiles that already have a rating for this test
                                            try:
                                                analysis_data = rds.read_analysis(prof_id_check) or {"ratings": {}}
                                            except Exception:
                                                # Fallback to direct storage read if ResultsDataService unavailable
                                                analysis_file = Path("profile_analyses") / f"{prof_id_check}_analysis.json"
                                                analysis_data = __import__("storage").get_storage().read_json(str(analysis_file)) or {"ratings": {}}
                                            rating_key = test.get('id') or test.get('guid') or test_title
                                            existing_ratings_dict = analysis_data.get('ratings', {})
                                            if rating_key in existing_ratings_dict or test_title in existing_ratings_dict:
                                                skipped += 1
                                                done += 1
                                                progress.progress(int(done/total*100))
                                                continue

                                            try:
                                                res = run_test_for_profile(test, prof, find_image_file, save_analysis)
                                                if res.get('status') == 'ok' and res.get('saved'):
                                                    analyzed += 1
                                                elif res.get('status') == 'no_images':
                                                    skipped += 1
                                                else:
                                                    errors.append(f"{prof_id_check}: {res.get('error')}")
                                            except Exception as e:
                                                errors.append(f"{prof_id_check}: {e}")

                                        except Exception as e:
                                            errors.append(f"{prof if prof else 'baseline'}: {e}")
                                        done += 1
                                        progress.progress(int(done/total*100))

                                    # Summary
                                    st.success(f"Analysis complete — {analyzed} analyzed, {skipped} skipped, {len(errors)} errors")
                                    if errors:
                                        for err in errors:
                                            st.error(err)
                                # Force re-analyze button (overwrites existing ratings)
                                if st.button("🔁 Re-Analyze All Profiles (force)", key=f"reanalyse_all_{test.get('id','')}"):
                                    all_profile_ids = get_existing_profile_ids()
                                    profiles_to_check = [''] + all_profile_ids
                                    progress = st.progress(0)
                                    total = len(profiles_to_check)
                                    done = 0
                                    analyzed = 0
                                    skipped = 0
                                    errors = []
                                    for p_idx, prof in enumerate(profiles_to_check):
                                        try:
                                            res = run_test_for_profile(test, prof, find_image_file, save_analysis)
                                            if res.get('status') == 'ok' and res.get('saved'):
                                                analyzed += 1
                                            elif res.get('status') == 'no_images':
                                                skipped += 1
                                            else:
                                                errors.append(f"{prof if prof else 'baseline'}: {res.get('error')}")
                                        except Exception as e:
                                            errors.append(f"{prof if prof else 'baseline'}: {e}")
                                        done += 1
                                        progress.progress(int(done/total*100))

                                    st.success(f"Re-analysis complete — {analyzed} analyzed, {skipped} skipped, {len(errors)} errors")
                                    if errors:
                                        for err in errors:
                                            st.error(err)

                            with col_b:
                                st.markdown("<br>", unsafe_allow_html=True)
                                st.caption("Runs AI rating for any profiles that have an uploaded image but no rating for this test")

                            st.markdown("---")
                            # Grid-style image gallery removed — per-profile upload
                            # previews above are the canonical image controls.
                        else:
                            st.warning("Test title missing")

                st.markdown("---")
                st.markdown("#### 📝 Profile Prompts")
                debug_log.append(f"[{time.time() - start_time:.2f}s]   Entering Prompts expander for test: {test.get('title', 'Untitled')}")
                debug_container.code("\n".join(debug_log[-10:]))
                with st.expander("Show full prompts for all profiles", expanded=False):
                    test_prompt = test.get('prompt', '')
                    test_params = test.get('params', '')
                    test_section = test.get('section', '')
                    if test_prompt:
                        st.markdown("**Global Parameters** (applied to all prompts)")
                        # Ensure per-test global params widget stays in sync when
                        # the global params are updated elsewhere in the app.
                        widget_key = f"test_global_params_{test.get('id', '')}"
                        current_token = st.session_state.get('global_params_token', None)
                        last_seen = st.session_state.get(f"{widget_key}_token", None)
                        # Initialize or refresh the per-test widget value when the
                        # widget is not present yet or when the global token changed.
                        if (widget_key not in st.session_state) or (last_seen != current_token):
                            def _randomize_seed(s: str) -> str:
                                import random, re
                                if not s:
                                    return s
                                def _repl(m):
                                    prefix = m.group(1)
                                    return f"{prefix}{random.randint(0, 2**32-1)}"
                                return re.sub(r"(--seed(?:=|\s+))(\d+)", _repl, s, flags=re.IGNORECASE)

                            init_val = st.session_state.get('global_params')
                            if not init_val:
                                init_val = f"--ar 16:9 --quality 4 --seed {__import__('random').randint(0, 2**32-1)}"
                            # Always apply randomization to any existing seed token
                            # so the per-test prompts don't keep the static default.
                            st.session_state[widget_key] = _randomize_seed(init_val)
                            st.session_state[f"{widget_key}_token"] = current_token

                        test_global_params = st.text_input(
                            "Global parameters for this test",
                            value=st.session_state.get(widget_key, '--ar 16:9 --quality 4 --seed 20161027'),
                            key=widget_key,
                            help="Add --ar, --quality, --seed, etc. These will be added to all prompts"
                        )
                        st.caption(f"📌 Test-specific parameters (stored with test): `{test_params if test_params else 'none'}`")
                        st.markdown("---")
                        all_profile_ids = get_existing_profile_ids()
                        all_prompts = []
                        prompt_parts = [test_prompt, test_params]
                        if test_global_params.strip():
                            global_params_to_add = test_global_params.strip()
                            if str(test_section).startswith('VOID'):
                                global_params_to_add = filter_seed_from_params(global_params_to_add)
                            if global_params_to_add:
                                prompt_parts.append(global_params_to_add)
                        baseline_prompt = " ".join(part for part in prompt_parts if part)
                        all_prompts.append(f"# Baseline (no profile)\n{baseline_prompt}")
                        for prof_id in all_profile_ids:
                            prompt_parts = [test_prompt, test_params]
                            if test_global_params.strip():
                                global_params_to_add = test_global_params.strip()
                                if str(test_section).startswith('VOID'):
                                    global_params_to_add = filter_seed_from_params(global_params_to_add)
                                if global_params_to_add:
                                    prompt_parts.append(global_params_to_add)
                            prompt_parts.append(f"--p {prof_id}")
                            profile_prompt = " ".join(part for part in prompt_parts if part)
                            all_prompts.append(f"# Profile: {prof_id}\n{profile_prompt}")
                        prompts_text = "\n\n".join(all_prompts)
                        st.text_area(
                            "Copy prompts for all profiles",
                            value=prompts_text,
                            height=300,
                            key=f"prompts_{test.get('id', '')}",
                            help="Copy these prompts to run in MidJourney"
                        )
                    else:
                        st.warning("Test prompt missing")

            debug_log.append(f"[{time.time() - start_time:.2f}s] Finished rendering test: {test.get('title', 'Untitled')}")
            debug_container.code("\n".join(debug_log[-10:]))

    with test_tabs[1]:  # Add Test
        st.subheader("Add New Test")
        with st.form("add_test_form"):
            new_title = st.text_input("Title", placeholder="Moody Foggy Forest")
            new_section = st.selectbox("Section", ["PHOTO", "ART", "VOID_PHOTO", "VOID_ART"])
            new_prompt = st.text_area("Prompt", height=100, placeholder="A moody foggy forest at dawn...")
            new_params = st.text_input("Parameters", value="--ar 16:9 --stylize 1000", placeholder="--ar 16:9 --stylize 1000")
            new_version = st.selectbox("Version", ["v1", "v2", "v3"])
            # New metadata fields
            new_analysis_spec_version = st.text_input("Analysis Spec Version", value="tests_v1")
            new_taxonomy_version = st.text_input("Taxonomy Version", value="fm_v1")
            new_intent = st.text_input("Intent", value="")
            new_analysis_family = st.text_input("Analysis Family", value="")

            # Rubric inputs (simple multi-line fields)
            new_must = st.text_area("Rubric - MUST (one per line)", value="", height=100)
            new_avoid = st.text_area("Rubric - AVOID (one per line)", value="", height=100)
            new_prefer = st.text_area("Rubric - PREFER (one per line)", value="", height=100)
            new_w_must = st.number_input("Weight - must", value=0.6, step=0.05, format="%.2f")
            new_w_avoid = st.number_input("Weight - avoid", value=0.25, step=0.05, format="%.2f")
            new_w_prefer = st.number_input("Weight - prefer", value=0.15, step=0.05, format="%.2f")
            new_rubric_notes = st.text_area("Rubric Notes", value="", height=60)
            
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
                            # Build rubric dict
                            rubric_obj = {
                                'must': [s.strip() for s in new_must.splitlines() if s.strip()],
                                'avoid': [s.strip() for s in new_avoid.splitlines() if s.strip()],
                                'prefer': [s.strip() for s in new_prefer.splitlines() if s.strip()],
                                'weights': {'must': float(new_w_must), 'avoid': float(new_w_avoid), 'prefer': float(new_w_prefer)},
                                'notes': new_rubric_notes
                            }

                            tpm.add_test(
                                title=new_title,
                                prompt=new_prompt,
                                section=new_section,
                                params=new_params,
                                version=new_version,
                                analysis_spec_version=new_analysis_spec_version,
                                taxonomy_version=new_taxonomy_version,
                                intent=new_intent,
                                analysis_family=new_analysis_family,
                                rubric=rubric_obj
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
                # Show GUID for this test (read-only)
                st.markdown(f"**GUID:** `{selected_test.get('id') or selected_test.get('guid', '(none)')}`")
                # New metadata fields
                edit_analysis_spec_version = st.text_input("Analysis Spec Version", value=selected_test.get('analysis_spec_version', ''))
                edit_taxonomy_version = st.text_input("Taxonomy Version", value=selected_test.get('taxonomy_version', ''))
                edit_intent = st.text_input("Intent", value=selected_test.get('intent', ''))
                edit_analysis_family = st.text_input("Analysis Family", value=selected_test.get('analysis_family', ''))
                
                # Safely get version index
                test_version = selected_test.get('version', 'v2')
                try:
                    version_index = ["v1", "v2", "v3"].index(test_version)
                except (ValueError, TypeError):
                    version_index = 1  # Default to v2
                
                edit_version = st.selectbox("Version", ["v1", "v2", "v3"], index=version_index)
                edit_status = st.selectbox("Status", ["current", "archived"], index=0 if selected_test.get('status') == 'current' else 1)
                # Build rubric structure from editable fields (rendered in form)
                existing_rubric = selected_test.get('rubric', {}) or {}
                must_list = existing_rubric.get('must', [])
                avoid_list = existing_rubric.get('avoid', [])
                prefer_list = existing_rubric.get('prefer', [])
                weights = existing_rubric.get('weights', {})
                notes_val = existing_rubric.get('notes', '')

                # Editable list fields as multi-line textareas
                must_text = st.text_area("Rubric - MUST (one per line)", value="\n".join(must_list), height=120)
                avoid_text = st.text_area("Rubric - AVOID (one per line)", value="\n".join(avoid_list), height=120)
                prefer_text = st.text_area("Rubric - PREFER (one per line)", value="\n".join(prefer_list), height=120)
                # Weights
                w_must = st.number_input("Weight - must", value=float(weights.get('must', 0.6)), step=0.05, format="%.2f")
                w_avoid = st.number_input("Weight - avoid", value=float(weights.get('avoid', 0.25)), step=0.05, format="%.2f")
                w_prefer = st.number_input("Weight - prefer", value=float(weights.get('prefer', 0.15)), step=0.05, format="%.2f")
                notes = st.text_area("Rubric Notes", value=notes_val, height=80)

                col1, col2 = st.columns([1, 1])
                with col1:
                    update_btn = st.form_submit_button("💾 Update Test", type="primary")
                with col2:
                    duplicate_btn = st.form_submit_button("📋 Duplicate Test")

                if update_btn:
                    try:
                        # Parse lists back
                        new_must = [s.strip() for s in must_text.splitlines() if s.strip()]
                        new_avoid = [s.strip() for s in avoid_text.splitlines() if s.strip()]
                        new_prefer = [s.strip() for s in prefer_text.splitlines() if s.strip()]
                        new_rubric = {
                            'must': new_must,
                            'avoid': new_avoid,
                            'prefer': new_prefer,
                            'weights': {
                                'must': float(w_must),
                                'avoid': float(w_avoid),
                                'prefer': float(w_prefer)
                            },
                            'notes': notes
                        }

                        tpm.update_test(
                            test_id=selected_test['id'],
                            title=edit_title,
                            prompt=edit_prompt,
                            section=edit_section,
                            params=edit_params,
                            version=edit_version,
                            status=edit_status,
                            analysis_spec_version=edit_analysis_spec_version,
                            taxonomy_version=edit_taxonomy_version,
                            intent=edit_intent,
                            analysis_family=edit_analysis_family,
                            rubric=new_rubric
                        )
                        # If the title changed, rename existing image files to match new test filename pattern
                        old_title = selected_test.get('title', '')
                        if old_title and old_title != edit_title:
                            old_safe = old_title.replace(' ', '_').replace('/', '_')
                            new_safe = edit_title.replace(' ', '_').replace('/', '_')
                            storage = get_storage()
                            try:
                                all_files = storage.list_files('profile_results', '*')
                            except Exception:
                                all_files = []
                            moved = 0
                            for fp in all_files:
                                parts = fp.split('/')
                                if len(parts) < 3:
                                    continue
                                prof = parts[1]
                                filename = parts[2]
                                filename_no_ext = filename.rsplit('.', 1)[0]
                                if filename_no_ext.startswith(f"{prof}_{old_safe}"):
                                    # Build new filename preserving extension
                                    ext = filename.rsplit('.', 1)[1] if '.' in filename else 'jpg'
                                    new_filename = filename.replace(f"{prof}_{old_safe}", f"{prof}_{new_safe}", 1)
                                    old_path = fp
                                    new_path = f"profile_results/{prof}/{new_filename}"
                                    try:
                                        data = storage.read_bytes(old_path)
                                        storage.write_bytes(new_path, data)
                                        storage.delete(old_path)
                                        moved += 1
                                    except Exception:
                                        pass
                            if moved:
                                st.success(f"✅ Renamed {moved} image file(s) to match new test title")
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
                                profile_prompt = f"{edit_prompt} {edit_params} -p {prof_id}"
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
            st.markdown("Format: **JSON only**")
        
        if st.button("📥 Download Tests", type="primary"):
            export_tests = tests
            if export_status != "all":
                export_tests = [t for t in tests if t.get('status') == export_status]
            import json
            json_str = json.dumps(export_tests, indent=2)
            st.download_button(
                label="💾 Download JSON",
                data=json_str,
                file_name=f"test_prompts_{export_status}.json",
                mime="application/json"
            )
        
        st.markdown("---")
        
        # Import
        st.markdown("### 📥 Import Tests")
        uploaded_file = st.file_uploader("Upload JSON file", type=["json"])

        if uploaded_file:
            try:
                import json
                # Streamlit uploaded files are file-like; read bytes and decode safely.
                raw = uploaded_file.read()
                try:
                    imported_tests = json.loads(raw.decode('utf-8'))
                except Exception:
                    imported_tests = json.loads(raw)
                
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
