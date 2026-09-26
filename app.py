import streamlit as st
import streamlit.components.v1 as components
import json
import html
import uuid
from datetime import datetime

from supabase import create_client
from google import genai


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Devotional Songs",
    page_icon="🕉️",
    layout="wide"
)


# ============================================================
# LANGUAGES
# ============================================================

LANGUAGES = {
    "English": "English",
    "Telugu": "Telugu",
    "Hindi": "Hindi",
    "Tamil": "Tamil",
    "Kannada": "Kannada",
    "Malayalam": "Malayalam",
    "Sanskrit": "Sanskrit"
}


# ============================================================
# STREAMLIT SECRETS
# ============================================================

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

    ADMIN_USERNAME = st.secrets["ADMIN_USERNAME"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

except Exception as e:

    st.error(
        """
        Missing Streamlit Secrets.

        Please configure:

        SUPABASE_URL
        SUPABASE_KEY
        OPENAI_API_KEY
        ADMIN_USERNAME
        ADMIN_PASSWORD
        """
    )

    st.stop()


# ============================================================
# CREATE CLIENTS
# ============================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
)


# ============================================================
# CONSTANTS
# ============================================================

SONGS_TABLE = "songs"
COVER_BUCKET = "song-covers"


# ============================================================
# SESSION STATE
# ============================================================

if "selected_song_id" not in st.session_state:
    st.session_state.selected_song_id = None

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "show_admin_login" not in st.session_state:
    st.session_state.show_admin_login = False

if "songs" not in st.session_state:
    st.session_state.songs = []

if "translation_cache" not in st.session_state:
    st.session_state.translation_cache = {}


# ============================================================
# LOAD SONGS
# ============================================================

def load_songs():

    try:

        response = (
            supabase
            .table(SONGS_TABLE)
            .select("*")
            .order("id")
            .execute()
        )

        return response.data or []

    except Exception as e:

        st.error(
            f"Could not load songs: {e}"
        )

        return []


# ============================================================
# ADD SONG
# ============================================================

def add_song(
    title,
    lyrics,
    cover_url=None
):

    data = {
        "title": title,
        "lyrics": lyrics,
        "cover_url": cover_url,
        "translations": {}
    }

    try:

        response = (
            supabase
            .table(SONGS_TABLE)
            .insert(data)
            .execute()
        )

        return response.data

    except Exception as e:

        st.error(
            f"Could not add song: {e}"
        )

        return None


# ============================================================
# UPDATE SONG
# ============================================================

def update_song(
    song_id,
    title,
    lyrics,
    cover_url=None
):

    data = {
        "title": title,
        "lyrics": lyrics,
        "cover_url": cover_url,

        # Clear old translations because lyrics
        # may have changed.
        "translations": {}
    }

    try:

        response = (
            supabase
            .table(SONGS_TABLE)
            .update(data)
            .eq("id", int(song_id))
            .execute()
        )

        return response.data

    except Exception as e:

        st.error(
            f"Could not update song: {e}"
        )

        return None


# ============================================================
# DELETE SONG
# ============================================================

def delete_song(song_id):

    try:

        response = (
            supabase
            .table(SONGS_TABLE)
            .delete()
            .eq("id", int(song_id))
            .execute()
        )

        return response.data

    except Exception as e:

        st.error(
            f"Could not delete song: {e}"
        )

        return None


# ============================================================
# UPLOAD COVER IMAGE
# ============================================================

def upload_cover(uploaded_file):

    if uploaded_file is None:
        return None

    try:

        extension = (
            uploaded_file.name
            .split(".")[-1]
            .lower()
        )

        filename = (
            "covers/"
            + datetime.now().strftime(
                "%Y%m%d%H%M%S"
            )
            + "_"
            + uuid.uuid4().hex
            + "."
            + extension
        )

        file_bytes = uploaded_file.getvalue()

        supabase.storage.from_(
            COVER_BUCKET
        ).upload(
            filename,
            file_bytes,
            {
                "content-type": uploaded_file.type,
                "upsert": "false"
            }
        )

        public_url = (
            supabase
            .storage
            .from_(COVER_BUCKET)
            .get_public_url(filename)
        )

        return public_url

    except Exception as e:

        st.error(
            f"Could not upload cover image: {e}"
        )

        return None


# ============================================================
# NORMALIZE SONG NAME
# ============================================================

def normalize_song_name(name):

    return " ".join(
        name.strip().lower().split()
    )


# ============================================================
# FIND DUPLICATE SONG
# ============================================================

def find_duplicate_song(
    title,
    exclude_song_id=None
):

    normalized_title = normalize_song_name(
        title
    )

    for song in st.session_state.songs:

        song_id = song.get("id")

        # Ignore the song currently being edited
        if (
            exclude_song_id is not None
            and int(song_id) == int(exclude_song_id)
        ):
            continue

        existing_title = song.get(
            "title",
            ""
        )

        if (
            normalize_song_name(
                existing_title
            )
            == normalized_title
        ):

            return song

    return None


# ============================================================
# OPENAI TRANSLITERATION
# ============================================================

def transliterate_lyrics(
    lyrics,
    language
):

    # English should show original lyrics.
    if language == "English":
        return lyrics

    language_instruction = {

        "Telugu": """
Convert the lyrics into Telugu script.
Preserve the same words and pronunciation.
Do NOT translate the meaning.
""",

        "Hindi": """
Convert the lyrics into Devanagari script.
Preserve the same words and pronunciation.
Do NOT translate the meaning.
""",

        "Tamil": """
Convert the lyrics into Tamil script.
Preserve the same words and pronunciation.
Do NOT translate the meaning.
""",

        "Kannada": """
Convert the lyrics into Kannada script.
Preserve the same words and pronunciation.
Do NOT translate the meaning.
""",

        "Malayalam": """
Convert the lyrics into Malayalam script.
Preserve the same words and pronunciation.
Do NOT translate the meaning.
""",

        "Sanskrit": """
Convert the Romanized lyrics into Devanagari script.
Preserve the same words and pronunciation.
Do NOT translate the meaning.
"""
    }

    prompt = f"""
You are a devotional song script transliteration assistant.

The user provides lyrics written using English/Roman letters.

Your task is to convert the SAME lyrics into
{language} script.

{language_instruction.get(language, "")}

IMPORTANT RULES:

1. This is transliteration, NOT translation.
2. Do not change the meaning.
3. Do not replace words with synonyms.
4. Preserve deity names.
5. Preserve devotional terms.
6. Preserve repetitions.
7. Preserve punctuation where possible.
8. Preserve every line break.
9. Do not add explanations.
10. Do not add headings.
11. Return ONLY the converted lyrics.

Example:

Input:
Namaskaram andariki

Telugu:
నమస్కారం అందరికీ

Lyrics:

{lyrics}
"""

    try:

        response = openai_client.responses.create(
            model="gpt-5.6-luna",
            input=prompt
        )

        result = response.output_text.strip()

        return result

    except Exception as e:

        st.error(
            f"AI conversion failed: {e}"
        )

        return lyrics


# ============================================================
# GET LANGUAGE VERSION
# ============================================================

def get_language_version(
    song,
    language
):

    original_lyrics = song.get(
        "lyrics",
        ""
    )

    # English = original lyrics
    if language == "English":
        return original_lyrics

    song_id = str(
        song.get("id")
    )

    cache_key = (
        f"{song_id}_{language}"
    )

    # --------------------------------------------------------
    # CHECK SESSION CACHE
    # --------------------------------------------------------

    if cache_key in st.session_state.translation_cache:

        return st.session_state.translation_cache[
            cache_key
        ]

    # --------------------------------------------------------
    # CHECK DATABASE CACHE
    # --------------------------------------------------------

    translations = (
        song.get("translations")
        or {}
    )

    if isinstance(
        translations,
        dict
    ):

        saved_translation = translations.get(
            language
        )

        if saved_translation:

            st.session_state.translation_cache[
                cache_key
            ] = saved_translation

            return saved_translation

    # --------------------------------------------------------
    # GENERATE USING OPENAI
    # --------------------------------------------------------

    with st.spinner(
        f"Converting lyrics to {language}..."
    ):

        converted = transliterate_lyrics(
            original_lyrics,
            language
        )

    # --------------------------------------------------------
    # SAVE IN CURRENT USER SESSION
    # --------------------------------------------------------

    st.session_state.translation_cache[
        cache_key
    ] = converted

    # --------------------------------------------------------
    # ONLY ADMIN CAN SAVE TRANSLATION TO DATABASE
    # --------------------------------------------------------

    if st.session_state.admin_logged_in:

        try:

            new_translations = dict(
                translations
            )

            new_translations[
                language
            ] = converted

            (
                supabase
                .table(SONGS_TABLE)
                .update({
                    "translations":
                    new_translations
                })
                .eq(
                    "id",
                    int(song_id)
                )
                .execute()
            )

        except Exception as e:

            st.warning(
                f"Translation generated but could not be saved: {e}"
            )

    return converted


# ============================================================
# COPY LYRICS BUTTON
# ============================================================

def copy_button(text):

    # Convert Python string safely to JavaScript string
    safe_text = json.dumps(
        text,
        ensure_ascii=False
    )

    copy_html = f"""
    <div>

        <button
            onclick="copyLyrics()"
            style="
                padding: 10px 18px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 15px;
                font-weight: bold;
                background-color: #f0f0f0;
            "
        >
            📋 Copy Lyrics
        </button>

        <span
            id="copyMessage"
            style="
                margin-left: 10px;
                font-weight: bold;
            "
        ></span>

    </div>

    <script>

        const lyricsText = {safe_text};

        async function copyLyrics() {{

            try {{

                await navigator.clipboard.writeText(
                    lyricsText
                );

                document.getElementById(
                    "copyMessage"
                ).innerText = "✅ Copied!";

            }} catch (error) {{

                const textarea =
                    document.createElement("textarea");

                textarea.value = lyricsText;

                document.body.appendChild(
                    textarea
                );

                textarea.select();

                document.execCommand("copy");

                textarea.remove();

                document.getElementById(
                    "copyMessage"
                ).innerText = "✅ Copied!";

            }}

        }}

    </script>
    """

    components.html(
        copy_html,
        height=60
    )


# ============================================================
# FIND SONG
# ============================================================

def find_song(song_id):

    for song in st.session_state.songs:

        if int(song["id"]) == int(song_id):

            return song

    return None


# ============================================================
# CLEAR TRANSLATION CACHE
# ============================================================

def clear_song_translation_cache(
    song_id
):

    prefix = f"{song_id}_"

    keys_to_remove = [

        key

        for key
        in st.session_state.translation_cache

        if key.startswith(prefix)

    ]

    for key in keys_to_remove:

        del st.session_state.translation_cache[
            key
        ]


# ============================================================
# ADMIN LOGIN
# ============================================================

def show_admin_login():

    st.title(
        "🔐 Admin Login"
    )

    st.write(
        "Only the administrator can manage songs."
    )

    with st.form(
        "admin_login"
    ):

        username = st.text_input(
            "Username"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        login = st.form_submit_button(
            "Login"
        )

        if login:

            if (
                username == ADMIN_USERNAME
                and password == ADMIN_PASSWORD
            ):

                st.session_state.admin_logged_in = True
                st.session_state.show_admin_login = False

                st.success(
                    "✅ Login successful!"
                )

                st.rerun()

            else:

                st.error(
                    "❌ Incorrect username or password."
                )


# ============================================================
# REPLACE EXISTING SONG
# ============================================================

def replace_existing_song(
    old_song_id,
    existing_song_id,
    title,
    lyrics,
    cover_url
):

    # Update the existing song
    result = update_song(
        existing_song_id,
        title,
        lyrics,
        cover_url
    )

    if result is None:
        return False

    # Delete the song currently being edited
    delete_result = delete_song(
        old_song_id
    )

    if delete_result is None:
        return False

    # Clear translation caches
    clear_song_translation_cache(
        old_song_id
    )

    clear_song_translation_cache(
        existing_song_id
    )

    return True


# ============================================================
# ADMIN DASHBOARD
# ============================================================

def admin_dashboard():

    st.title(
        "📊 Admin Dashboard"
    )

    # ========================================================
    # LOGOUT
    # ========================================================

    if st.button(
        "🚪 Logout"
    ):

        st.session_state.admin_logged_in = False
        st.session_state.selected_song_id = None

        st.rerun()

    st.divider()

    # ========================================================
    # ADD NEW SONG
    # ========================================================

    st.subheader(
        "➕ Add New Song"
    )

    with st.form(
        "add_song_form"
    ):

        title = st.text_input(
            "Song Name",
            placeholder="Enter song name"
        )

        lyrics = st.text_area(
            "Lyrics",
            height=250,
            placeholder=(
                "Enter lyrics in English/Roman letters..."
            )
        )

        cover = st.file_uploader(
            "Cover Image (Optional)",
            type=[
                "jpg",
                "jpeg",
                "png"
            ],
            key="add_cover"
        )

        add_button = st.form_submit_button(
            "➕ Add Song"
        )

        if add_button:

            if not title.strip():

                st.error(
                    "Please enter the song name."
                )

            elif not lyrics.strip():

                st.error(
                    "Please enter the lyrics."
                )

            else:

                # Check duplicate
                duplicate = find_duplicate_song(
                    title
                )

                if duplicate:

                    st.warning(
                        f"⚠️ A song named "
                        f"'{duplicate.get('title')}' "
                        f"already exists."
                    )

                    st.info(
                        "Please use a different song name."
                    )

                else:

                    cover_url = None

                    if cover is not None:

                        cover_url = upload_cover(
                            cover
                        )

                    result = add_song(
                        title.strip(),
                        lyrics.strip(),
                        cover_url
                    )

                    if result is not None:

                        st.success(
                            "✅ Song added successfully!"
                        )

                        st.session_state.songs = (
                            load_songs()
                        )

                        st.rerun()

    st.divider()

    # ========================================================
    # MANAGE SONGS
    # ========================================================

    st.subheader(
        "🕉️ Manage Songs"
    )

    if not st.session_state.songs:

        st.info(
            "No songs available."
        )

        return

    # ========================================================
    # DISPLAY EVERY SONG
    # ========================================================

    for song in st.session_state.songs:

        song_id = song["id"]

        current_title = song.get(
            "title",
            ""
        )

        current_lyrics = song.get(
            "lyrics",
            ""
        )

        current_cover = song.get(
            "cover_url"
        )

        with st.expander(
            f"🕉️ {current_title}"
        ):

            st.write(
                f"**Song ID:** {song_id}"
            )

            # =================================================
            # EDIT SONG
            # =================================================

            st.markdown(
                "### ✏️ Edit Song"
            )

            edit_title = st.text_input(
                "Song Name",
                value=current_title,
                key=f"edit_title_{song_id}"
            )

            edit_lyrics = st.text_area(
                "Lyrics",
                value=current_lyrics,
                height=250,
                key=f"edit_lyrics_{song_id}"
            )

            new_cover = st.file_uploader(
                "New Cover Image (Optional)",
                type=[
                    "jpg",
                    "jpeg",
                    "png"
                ],
                key=f"new_cover_{song_id}"
            )

            # =================================================
            # SAVE CHANGES
            # =================================================

            if st.button(
                "💾 Save Changes",
                key=f"save_{song_id}",
                use_container_width=True
            ):

                if not edit_title.strip():

                    st.error(
                        "Song name cannot be empty."
                    )

                elif not edit_lyrics.strip():

                    st.error(
                        "Lyrics cannot be empty."
                    )

                else:

                    duplicate = find_duplicate_song(
                        edit_title,
                        exclude_song_id=song_id
                    )

                    # =========================================
                    # DUPLICATE FOUND
                    # =========================================

                    if duplicate:

                        st.warning(
                            "⚠️ A song with this name "
                            "already exists!"
                        )

                        st.write(
                            f"Existing song: "
                            f"**{duplicate.get('title')}**"
                        )

                        st.info(
                            "Choose one option:"
                        )

                        col1, col2 = st.columns(2)

                        # -------------------------------------
                        # REPLACE
                        # -------------------------------------

                        with col1:

                            if st.button(
                                "🔄 Replace Existing Song",
                                key=(
                                    f"replace_"
                                    f"{song_id}_"
                                    f"{duplicate['id']}"
                                ),
                                use_container_width=True
                            ):

                                cover_url = current_cover

                                if new_cover is not None:

                                    uploaded_url = (
                                        upload_cover(
                                            new_cover
                                        )
                                    )

                                    if uploaded_url:

                                        cover_url = (
                                            uploaded_url
                                        )

                                success = (
                                    replace_existing_song(
                                        old_song_id=song_id,
                                        existing_song_id=duplicate["id"],
                                        title=edit_title.strip(),
                                        lyrics=edit_lyrics.strip(),
                                        cover_url=cover_url
                                    )
                                )

                                if success:

                                    st.session_state.songs = (
                                        load_songs()
                                    )

                                    st.success(
                                        "✅ Existing song "
                                        "replaced successfully."
                                    )

                                    st.rerun()

                        # -------------------------------------
                        # CHANGE NAME
                        # -------------------------------------

                        with col2:

                            if st.button(
                                "✏️ Change Name",
                                key=(
                                    f"change_"
                                    f"{song_id}_"
                                    f"{duplicate['id']}"
                                ),
                                use_container_width=True
                            ):

                                st.info(
                                    "Change the song name "
                                    "above and click "
                                    "'Save Changes' again."
                                )

                    # =========================================
                    # NO DUPLICATE
                    # =========================================

                    else:

                        cover_url = current_cover

                        if new_cover is not None:

                            uploaded_url = upload_cover(
                                new_cover
                            )

                            if uploaded_url:

                                cover_url = uploaded_url

                        result = update_song(
                            song_id,
                            edit_title.strip(),
                            edit_lyrics.strip(),
                            cover_url
                        )

                        if result is not None:

                            clear_song_translation_cache(
                                song_id
                            )

                            st.session_state.songs = (
                                load_songs()
                            )

                            st.success(
                                "✅ Song updated successfully!"
                            )

                            st.rerun()

            st.divider()

            # =================================================
            # DELETE SONG
            # =================================================

            st.markdown(
                "### 🗑️ Delete Song"
            )

            st.warning(
                "Deleting a song cannot be undone."
            )

            confirm_delete = st.checkbox(
                "I understand that this song will be permanently deleted.",
                key=f"confirm_delete_{song_id}"
            )

            if st.button(
                "🗑️ Delete Song",
                key=f"delete_{song_id}",
                use_container_width=True
            ):

                if not confirm_delete:

                    st.error(
                        "Please confirm deletion first."
                    )

                else:

                    result = delete_song(
                        song_id
                    )

                    if result is not None:

                        clear_song_translation_cache(
                            song_id
                        )

                        if (
                            st.session_state.selected_song_id
                            == song_id
                        ):

                            st.session_state.selected_song_id = None

                        st.session_state.songs = (
                            load_songs()
                        )

                        st.success(
                            "✅ Song deleted successfully!"
                        )

                        st.rerun()


# ============================================================
# SONG DETAILS PAGE
# ============================================================

def show_song_details(song):

    # ========================================================
    # BACK TO SONGS
    # ========================================================

    if st.button(
        "← Back to Songs"
    ):

        st.session_state.selected_song_id = None

        st.rerun()

    st.divider()

    # ========================================================
    # SONG TITLE
    # ========================================================

    st.title(
        f"🕉️ {song.get('title', 'Untitled')}"
    )

    # ========================================================
    # COVER IMAGE
    # ========================================================

    cover_url = song.get(
        "cover_url"
    )

    if cover_url:

        try:

            st.image(
                cover_url,
                width=350
            )

        except Exception:
            pass

    # ========================================================
    # LANGUAGE SELECTOR
    # ========================================================

    language = st.selectbox(
        "🌐 Select Language",
        list(LANGUAGES.keys()),
        key=f"language_{song['id']}"
    )

    st.divider()

    # ========================================================
    # GET LYRICS
    # ========================================================

    lyrics = get_language_version(
        song,
        language
    )

    # ========================================================
    # LYRICS TITLE
    # ========================================================

    st.subheader(
        f"📝 Lyrics — {language}"
    )

    # ========================================================
    # LYRICS DISPLAY
    # ========================================================
    #
    # IMPORTANT:
    #
    # We do NOT use disabled st.text_area().
    #
    # We do NOT use st.code().
    #
    # We use st.html() so:
    #
    # - lyrics are clear
    # - lyrics are black
    # - lyrics are selectable
    # - CSS is not shown as text
    # - no blocked cursor appears
    #
    # ========================================================

    safe_lyrics = html.escape(
        lyrics
    )

    st.html(
        f"""
        <div style="
            padding: 22px;
            border: 1px solid #d6d6d6;
            border-radius: 12px;
            background-color: #ffffff;
            color: #222222;
            font-size: 18px;
            line-height: 1.9;
            white-space: pre-wrap;
            word-wrap: break-word;
            overflow-x: auto;
            user-select: text;
        ">{safe_lyrics}</div>
        """
    )

    # ========================================================
    # COPY BUTTON
    # ========================================================

    copy_button(
        lyrics
    )

    st.divider()

    st.caption(
        "The lyrics are converted into the selected "
        "script while preserving the original words "
        "and pronunciation as closely as possible."
    )


# ============================================================
# HOME PAGE
# ============================================================

def home_page():

    st.title(
        "🕉️ Devotional Songs"
    )

    st.write(
        "Search for a devotional song and click "
        "the song name to open it."
    )

    st.divider()

    # ========================================================
    # SEARCH BOX
    # ========================================================

    search = st.text_input(
        "🔍 Search Songs",
        placeholder="Search by song name..."
    )

    # ========================================================
    # FILTER SONGS
    # ========================================================

    if search.strip():

        search_text = (
            search.strip().lower()
        )

        filtered_songs = [

            song

            for song
            in st.session_state.songs

            if search_text
            in song.get(
                "title",
                ""
            ).lower()

        ]

    else:

        filtered_songs = (
            st.session_state.songs
        )

    # ========================================================
    # SONG LIST
    # ========================================================

    st.subheader(
        "🙏 Songs"
    )

    if not filtered_songs:

        st.info(
            "No songs found."
        )

        return

    for song in filtered_songs:

        song_id = song["id"]

        title = song.get(
            "title",
            "Untitled Song"
        )

        if st.button(
            f"🕉️ {title}",
            key=f"song_{song_id}",
            use_container_width=True
        ):

            st.session_state.selected_song_id = (
                song_id
            )

            st.rerun()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title(
        "🕉️ Devotional Songs"
    )

    st.divider()

    # ========================================================
    # ADMIN
    # ========================================================

    if st.session_state.admin_logged_in:

        st.success(
            "👤 Admin logged in"
        )

        page = st.radio(
            "Menu",
            [
                "🏠 Home",
                "📊 Admin Dashboard"
            ]
        )

    # ========================================================
    # PUBLIC USER
    # ========================================================

    else:

        page = st.radio(
            "Menu",
            [
                "🏠 Home"
            ]
        )

        st.divider()

        if st.button(
            "🔐 Admin Login",
            use_container_width=True
        ):

            st.session_state.show_admin_login = True

            st.rerun()


# ============================================================
# LOAD SONGS FROM SUPABASE
# ============================================================

st.session_state.songs = load_songs()


# ============================================================
# PAGE ROUTING
# ============================================================

# ------------------------------------------------------------
# ADMIN LOGIN
# ------------------------------------------------------------

if st.session_state.show_admin_login:

    show_admin_login()


# ------------------------------------------------------------
# ADMIN DASHBOARD
# ------------------------------------------------------------

elif (
    st.session_state.admin_logged_in
    and page == "📊 Admin Dashboard"
):

    admin_dashboard()


# ------------------------------------------------------------
# SONG DETAILS
# ------------------------------------------------------------

elif (
    st.session_state.selected_song_id
    is not None
):

    selected_song = find_song(
        st.session_state.selected_song_id
    )

    if selected_song:

        show_song_details(
            selected_song
        )

    else:

        st.session_state.selected_song_id = None

        st.warning(
            "Song not found."
        )

        st.rerun()


# ------------------------------------------------------------
# HOME
# ------------------------------------------------------------

else:

    home_page()
