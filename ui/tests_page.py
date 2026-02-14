import time
import json
import datetime
from pathlib import Path
import streamlit as st
import test_prompts_manager as tpm
from storage import get_storage


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
    tests = tpm.load_tests()
    debug_log.append(f"[{time.time() - start_time:.2f}s] Loaded {len(tests)} tests from tpm.load_tests()")
    debug_container.code("\n".join(debug_log))

    # Cache all image files (jpg and png) once for this page load
    storage = __import__("storage").get_storage()
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
                st.markdown(f"**GUID:** `{test.get('guid', 'N/A')}`")
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
                        test_key = test.get('guid') or test_title
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
                                        'commentary': rating_data.get('commentary', 'No commentary')
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
                                profile_text = f"{affinity_emoji} {rating['profile_id']} - \"{rating['label']}\" | Score: {rating['score']}/10 | Affinity: {rating['affinity']} | Confidence: {confidence_display}\n\n{rating['commentary']}\n"
                                all_profiles_text.append(profile_text)
                            combined_text = "\n" + "="*80 + "\n\n".join(all_profiles_text)
                            st.text_area("All Profile Analyses", combined_text, height=400, key=f"analysis_{test.get('id', '')}")
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
                                        analysis_file = Path("profile_analyses") / f"{prof_id_check}_analysis.json"
                                        analysis_data = __import__("storage").get_storage().read_json(str(analysis_file)) or {"ratings": {}}
                                        rating_key = test.get('guid') or test.get('title')
                                        existing_ratings_dict = analysis_data.get('ratings', {})
                                        if rating_key in existing_ratings_dict or test.get('title') in existing_ratings_dict:
                                            skipped += 1
                                            done += 1
                                            progress.progress(int(done/total*100))
                                            continue

                                        # Find uploaded image(s)
                                        if test.get('title') in ["Null Prompt (Photo)", "Null Prompt (Art)"]:
                                            void_images = []
                                            for img_num in range(1, 9):
                                                fp = find_image_file(Path(f"profile_results/{prof if prof else 'baseline'}"), prof if prof else 'baseline', test.get('title'), image_num=img_num)
                                                if fp:
                                                    void_images.append(fp)
                                            if not void_images:
                                                skipped += 1
                                                done += 1
                                                progress.progress(int(done/total*100))
                                                continue
                                            single_test = [(test.get('title'), void_images, {'Section': '', 'Prompt': '', 'Parameter Values': ''})]
                                        else:
                                            fp = find_image_file(Path(f"profile_results/{prof if prof else 'baseline'}"), prof if prof else 'baseline', test.get('title'))
                                            if not fp:
                                                skipped += 1
                                                done += 1
                                                progress.progress(int(done/total*100))
                                                continue
                                            single_test = [(test.get('title'), fp, {'Section': '', 'Prompt': '', 'Parameter Values': ''})]

                                        with st.spinner(f"Analyzing {prof_id_check}..."):
                                            try:
                                                result = batch_ai_rate_images(single_test, prof_id_check, existing_ratings=analysis_data.get('ratings', {}))
                                            except Exception as e:
                                                import traceback
                                                tb = traceback.format_exc()
                                                errors.append(f"{prof if prof else 'baseline'}: {e}\n{tb}")
                                                result = None

                                            if result and 'ratings' in result:
                                                returned_rating = result['ratings'].get(test.get('title'))
                                                if returned_rating:
                                                    analysis_data.setdefault('ratings', {})
                                                    write_key = test.get('guid') or test.get('title')
                                                    analysis_data['ratings'][write_key] = returned_rating
                                                    if write_key != test.get('title') and test.get('title') in analysis_data['ratings']:
                                                        try:
                                                            del analysis_data['ratings'][test.get('title')]
                                                        except Exception:
                                                            pass
                                                    save_analysis(prof_id_check, analysis_data)
                                                    analyzed += 1
                                                else:
                                                    try:
                                                        keys = list(result.get('ratings', {}).keys())
                                                    except Exception:
                                                        keys = []
                                                    errors.append(f"No rating returned for {prof_id_check} — response rating keys: {keys}")
                                                    try:
                                                        dump_dir = Path("profile_analyses/backups")
                                                        dump_dir.mkdir(parents=True, exist_ok=True)
                                                        dump_file = dump_dir / f"{prof_id_check}_batch_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                                                        dump_file.write_text(json.dumps(result, indent=2))
                                                        print(f"Saved batch response to {dump_file}")
                                                    except Exception as e:
                                                        print(f"Failed to save batch response: {e}")
                                            else:
                                                errors.append(f"No rating returned for {prof_id_check}")

                                    except Exception as e:
                                        errors.append(f"{prof if prof else 'baseline'}: {e}")
                                    done += 1
                                    progress.progress(int(done/total*100))

                                st.success(f"Analysis complete — {analyzed} analyzed, {skipped} skipped, {len(errors)} errors")
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
                                            analysis_file = Path("profile_analyses") / f"{prof_id_check}_analysis.json"
                                            analysis_data = __import__("storage").get_storage().read_json(str(analysis_file)) or {"ratings": {}}
                                            rating_key = test.get('guid') or test_title
                                            existing_ratings_dict = analysis_data.get('ratings', {})
                                            if rating_key in existing_ratings_dict or test_title in existing_ratings_dict:
                                                skipped += 1
                                                done += 1
                                                progress.progress(int(done/total*100))
                                                continue

                                            # Find image(s) for this profile
                                            if test_title in ["Null Prompt (Photo)", "Null Prompt (Art)"]:
                                                void_images = []
                                                for img_num in range(1, 9):
                                                    fp = find_image_file(Path(f"profile_results/{prof if prof else 'baseline'}"), prof if prof else 'baseline', test_title, image_num=img_num)
                                                    if fp:
                                                        void_images.append(fp)
                                                if not void_images:
                                                    skipped += 1
                                                    done += 1
                                                    progress.progress(int(done/total*100))
                                                    continue
                                                single_test = [(test_title, void_images, {'Section': '', 'Prompt': '', 'Parameter Values': ''})]
                                            else:
                                                fp = find_image_file(Path(f"profile_results/{prof if prof else 'baseline'}"), prof if prof else 'baseline', test_title)
                                                if not fp:
                                                    skipped += 1
                                                    done += 1
                                                    progress.progress(int(done/total*100))
                                                    continue
                                                single_test = [(test_title, fp, {'Section': '', 'Prompt': '', 'Parameter Values': ''})]

                                            # Call batch analysis for this single test/profile
                                            with st.spinner(f"Analyzing {prof_id_check}..."):
                                                result = batch_ai_rate_images(single_test, prof_id_check, existing_ratings=analysis_data.get('ratings', {}))

                                            if result and 'ratings' in result:
                                                returned_rating = result['ratings'].get(test_title)
                                                if returned_rating:
                                                    analysis_data.setdefault('ratings', {})
                                                    write_key = test.get('guid') or test_title
                                                    analysis_data['ratings'][write_key] = returned_rating
                                                    # remove legacy title key if GUID used
                                                    if write_key != test_title and test_title in analysis_data['ratings']:
                                                        try:
                                                            del analysis_data['ratings'][test_title]
                                                        except Exception:
                                                            pass
                                                    save_analysis(prof_id_check, analysis_data)
                                                    analyzed += 1
                                                else:
                                                    try:
                                                        keys = list(result.get('ratings', {}).keys())
                                                    except Exception:
                                                        keys = []
                                                    errors.append(f"No rating returned for {prof_id_check} — response rating keys: {keys}")
                                                    # Save full response for debugging
                                                    try:
                                                        dump_dir = Path("profile_analyses/backups")
                                                        dump_dir.mkdir(parents=True, exist_ok=True)
                                                        dump_file = dump_dir / f"{prof_id_check}_batch_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                                                        dump_file.write_text(json.dumps(result, indent=2))
                                                        print(f"Saved batch response to {dump_file}")
                                                    except Exception as e:
                                                        print(f"Failed to save batch response: {e}")
                                            else:
                                                errors.append(f"No rating returned for {prof_id_check}")

                                        except Exception as e:
                                            errors.append(f"{prof if prof else 'baseline'}: {e}")
                                        done += 1
                                        progress.progress(int(done/total*100))

                                    # Summary
                                    st.success(f"Analysis complete — {analyzed} analyzed, {skipped} skipped, {len(errors)} errors")
                                    if errors:
                                        for err in errors:
                                            st.error(err)

                            with col_b:
                                st.markdown("<br>", unsafe_allow_html=True)
                                st.caption("Runs AI rating for any profiles that have an uploaded image but no rating for this test")

                            st.markdown("---")
                            # Collect matching images for this test across all profiles
                            images_found = []
                            test_title_filename = test_title.replace(' ', '_').replace('/', '_')
                            for file_path in all_image_files_for_tests:
                                parts = file_path.split('/')
                                if len(parts) >= 3:
                                    prof = parts[1]
                                    filename = parts[2]
                                    filename_no_ext = filename.rsplit('.', 1)[0]
                                    if filename_no_ext.startswith(f"{prof}_{test_title_filename}"):
                                        images_found.append((prof, file_path))

                            if images_found:
                                images_found.sort(key=lambda x: x[0])
                                cols_per_row = 3
                                for i in range(0, len(images_found), cols_per_row):
                                    cols = st.columns(cols_per_row)
                                    for j, col in enumerate(cols):
                                        idx = i + j
                                        if idx < len(images_found):
                                            profile_id, img_path = images_found[idx]
                                            with col:
                                                st.markdown(f"**{profile_id}**")
                                                try:
                                                    img = load_image_cached(str(img_path))
                                                    st.image(img, width='stretch')
                                                    # Delete button
                                                    if st.button(f"🗑️ Delete image for {profile_id}", key=f"delete_{profile_id}_{test_title}"):
                                                        try:
                                                            __import__("storage").get_storage().delete(img_path)
                                                        except Exception:
                                                            try:
                                                                __import__("storage").get_storage().delete(str(img_path))
                                                            except Exception as e:
                                                                st.error(f"Failed to delete image: {e}")
                                                                continue
                                                        # Clear caches so upload controls reappear
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
                                                        st.success(f"✅ Deleted image for {profile_id}")
                                                        st.rerun()
                                                except Exception as e:
                                                    st.error(f"Failed to load image: {e}")
                            else:
                                st.info("No images found for this test across any profiles")
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
                        test_global_params = st.text_input(
                            "Global parameters for this test",
                            value=st.session_state.get('global_params', '--ar 16:9 --quality 4 --seed 20161027'),
                            key=f"test_global_params_{test.get('id', '')}",
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