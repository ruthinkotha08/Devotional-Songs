import streamlit as st
import json
import html
import uuid
from datetime import datetime

from supabase import create_client
from openai import OpenAI


# ============================================================
# PAGE SETTINGS
# ============================================================

st.set_page_config(
    page_title="Devotional Songs",
    page_icon="🎵",
    layout="wide"
)


# ============================================================
# LANGUAGE OPTIONS
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
# SECRETS
# ============================================================

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

    ADMIN_USERNAME = st.secrets["ADMIN_USERNAME"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

except Exception:
    st.error(
        "Secrets are missing. Please configure SUPABASE_URL, "
        "SUPABASE_KEY, OPENAI_API_KEY, ADMIN_USERNAME and ADMIN_PASSWORD "
        "in Streamlit Secrets."
    )
    st.stop()


# ============================================================
# CLIENTS
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
# DATABASE FUNCTIONS
# ============================================================

def load_songs():
    """
    Load all songs from Supabase.
    """

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
        st.error(f"Could not load songs: {e}")
        return []


def add_song(title, lyrics, cover_url=None):
    """
    Add a new song to Supabase.
    """

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
        st.error(f"Could not add song: {e}")
        return None


def update_song(song_id, title, lyrics, cover_url=None):
    """
    Update an existing song.

    When lyrics change, previously generated translations
    are cleared because they may no longer match the lyrics.
    """

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
            .update(data)
            .eq("id", int(song_id))
            .execute()
        )

        return response.data

    except Exception as e:
        st.error(f"Could not update song: {e}")
        return None


def delete_song(song_id):
    """
    Delete a song from Supabase.
    """

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
        st.error(f"Could not delete song: {e}")
        return None


# ============================================================
# COVER IMAGE UPLOAD
# ============================================================

def upload_cover(uploaded_file):
    """
    Upload a cover image to Supabase Storage.
    """

    if uploaded_file is None:
        return None

    try:
        file_extension = uploaded_file.name.split(".")[-1].lower()

        filename = (
            f"covers/"
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}_"
            f"{uuid.uuid4().hex}.{file_extension}"
        )

        file_bytes = uploaded_file.getvalue()

        content_type = uploaded_file.type

        supabase.storage.from_(COVER_BUCKET).upload(
            filename,
            file_bytes,
            {
                "content-type": content_type,
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
        st.error(f"Could not upload cover image: {e}")
        return None


# ============================================================
# OPENAI TRANSLITERATION
# ============================================================

def transliterate_lyrics(lyrics, language):
    """
    Convert Romanized lyrics into the selected script.

    IMPORTANT:
    This is transliteration/script conversion.
    It is NOT semantic translation.
    """

    if language == "English":
        return lyrics

    language_instructions = {
        "Telugu": """
Write the lyrics using Telugu script.
Preserve the same words, pronunciation and devotional wording.
Do NOT translate the meaning into different Telugu words.
""",

        "Hindi": """
Write the lyrics using Devanagari script as commonly used for Hindi.
Preserve the same words and pronunciation.
Do NOT translate the meaning.
""",

        "Tamil": """
Write the lyrics using Tamil script.
Preserve the same words and pronunciation as closely as possible.
Do NOT translate the meaning.
""",

        "Kannada": """
Write the lyrics using Kannada script.
Preserve the same words and pronunciation.
Do NOT translate the meaning.
""",

        "Malayalam": """
Write the lyrics using Malayalam script.
Preserve the same words and pronunciation.
Do NOT translate the meaning.
""",

        "Sanskrit": """
Write the lyrics using Devanagari script.
Treat this as phonetic transliteration of the supplied Romanized lyrics.
Do NOT translate the meaning or rewrite the words into different Sanskrit words.
"""
    }

    instruction = language_instructions.get(language, "")

    prompt = f"""
You are a script transliteration assistant for devotional songs.

The user provides lyrics written using English/Roman letters.

Your task is to convert the SAME lyrics into {language} script.

{instruction}

VERY IMPORTANT:

1. This is NOT translation.
2. Do NOT change the meaning.
3. Do NOT replace words with synonyms.
4. Preserve deity names exactly in pronunciation.
5. Preserve devotional words.
6. Preserve repetitions.
7. Preserve punctuation where possible.
8. Preserve every line break.
9. Do not add explanations.
10. Do not add headings.
11. Do not write anything before or after the lyrics.
12. Return ONLY the converted lyrics.

Example:

Input:
Namaskaram andariki

Telugu output:
నమస్కారం అందరికీ

Input:
Jai Sri Ram

Do not translate it into a different phrase.
Convert the sounds into the requested script.

Lyrics to convert:

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
        st.error(f"AI conversion failed: {e}")
        return lyrics


# ============================================================
# GET LANGUAGE VERSION
# ============================================================

def get_language_version(song, language):
    """
    Get lyrics in the selected language.

    English returns the original lyrics.

    For public users:
        generated translations stay in session memory.

    For admins:
        generated translations are also saved to Supabase.
    """

    original_lyrics = song.get("lyrics", "")

    if language == "English":
        return original_lyrics

    song_id = str(song.get("id"))

    cache_key = f"{song_id}_{language}"

    # Check session cache first
    if cache_key in st.session_state.translation_cache:
        return st.session_state.translation_cache[cache_key]

    # Check translations already stored in Supabase
    translations = song.get("translations") or {}

    if isinstance(translations, dict):
        saved_translation = translations.get(language)

        if saved_translation:
            st.session_state.translation_cache[cache_key] = saved_translation
            return saved_translation

    # Generate using OpenAI
    with st.spinner(f"Converting lyrics to {language}..."):
        converted = transliterate_lyrics(
            original_lyrics,
            language
        )

    # Save in current session
    st.session_state.translation_cache[cache_key] = converted

    # IMPORTANT:
    # Only admin users can write generated translations to DB.
    # Public users cannot modify the database.
    if st.session_state.admin_logged_in:

        try:
            updated_translations = dict(translations)
            updated_translations[language] = converted

            (
                supabase
                .table(SONGS_TABLE)
                .update({
                    "translations": updated_translations
                })
                .eq("id", int(song_id))
                .execute()
            )

        except Exception as e:
            st.warning(
                f"Translation was generated but could not be saved: {e}"
            )

    return converted


# ============================================================
# COPY LYRICS BUTTON
# ============================================================

def copy_button(text, button_id):
    """
    Create a browser copy button.
    """

    safe_text = json.dumps(text)

    component_html = f"""
    <div>
        <button
            onclick='copyLyrics()'
            style="
                padding: 10px 18px;
                border-radius: 8px;
                border: none;
                cursor: pointer;
                font-size: 15px;
                font-weight: 600;
            "
        >
            📋 Copy Lyrics
        </button>

        <span
            id="copy-message"
            style="margin-left:10px;"
        ></span>
    </div>

    <script>
        const lyricsText = {safe_text};

        async function copyLyrics() {{
            try {{
                await navigator.clipboard.writeText(lyricsText);

                document.getElementById(
                    "copy-message"
                ).innerText = "Copied!";

            }} catch (error) {{

                const textarea = document.createElement("textarea");

                textarea.value = lyricsText;

                document.body.appendChild(textarea);

                textarea.select();

                document.execCommand("copy");

                textarea.remove();

                document.getElementById(
                    "copy-message"
                ).innerText = "Copied!";
            }}
        }}
    </script>
    """

    st.components.v1.html(
        component_html,
        height=55
    )


# ============================================================
# FIND SONG
# ============================================================

def find_song(song_id):
    """
    Find one song from the loaded songs.
    """

    for song in st.session_state.songs:

        if int(song["id"]) == int(song_id):
            return song

    return None


# ============================================================
# ADMIN LOGIN
# ============================================================

def show_admin_login_page():

    st.title("🔐 Admin Login")

    st.write(
        "Only the administrator can add, edit or delete songs."
    )

    with st.form("admin_login_form"):

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

                st.success("Login successful!")

                st.rerun()

            else:

                st.error(
                    "Incorrect username or password."
                )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

def admin_dashboard():

    st.title("📊 Admin Dashboard")

    if st.button("🚪 Logout"):

        st.session_state.admin_logged_in = False
        st.session_state.selected_song_id = None

        st.rerun()

    st.divider()

    # ========================================================
    # ADD SONG
    # ========================================================

    st.subheader("➕ Add New Song")

    with st.form("add_song_form"):

        title = st.text_input(
            "Song Name"
        )

        lyrics = st.text_area(
            "Lyrics",
            height=250,
            placeholder="Enter lyrics in English/Roman letters..."
        )

        cover = st.file_uploader(
            "Cover Image (Optional)",
            type=["jpg", "jpeg", "png"],
            key="add_cover"
        )

        add = st.form_submit_button(
            "Add Song"
        )

        if add:

            if not title.strip():

                st.error(
                    "Please enter the song name."
                )

            elif not lyrics.strip():

                st.error(
                    "Please enter the lyrics."
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
                        "Song added successfully!"
                    )

                    st.session_state.songs = load_songs()

                    st.rerun()

    st.divider()

    # ========================================================
    # EXISTING SONGS
    # ========================================================

    st.subheader("🎵 Manage Songs")

    if not st.session_state.songs:

        st.info(
            "No songs available."
        )

        return

    for song in st.session_state.songs:

        song_id = song["id"]
        title = song.get("title", "Untitled")

        with st.expander(
            f"🎵 {title}"
        ):

            st.write(
                f"**Song ID:** {song_id}"
            )

            st.write(
                f"**Title:** {title}"
            )

            st.text_area(
                "Current Lyrics",
                song.get("lyrics", ""),
                height=180,
                key=f"view_lyrics_{song_id}",
                disabled=True
            )

            st.divider()

            st.write("### ✏️ Edit Song")

            edit_title = st.text_input(
                "Song Name",
                value=title,
                key=f"edit_title_{song_id}"
            )

            edit_lyrics = st.text_area(
                "Lyrics",
                value=song.get("lyrics", ""),
                height=220,
                key=f"edit_lyrics_{song_id}"
            )

            new_cover = st.file_uploader(
                "Replace Cover Image (Optional)",
                type=["jpg", "jpeg", "png"],
                key=f"edit_cover_{song_id}"
            )

            col1, col2 = st.columns(2)

            with col1:

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

                        cover_url = song.get(
                            "cover_url"
                        )

                        if new_cover is not None:

                            uploaded_url = upload_cover(
                                new_cover
                            )

                            if uploaded_url:
                                cover_url = uploaded_url

                        update_song(
                            song_id,
                            edit_title.strip(),
                            edit_lyrics.strip(),
                            cover_url
                        )

                        # Clear cached versions for this song
                        keys_to_remove = [
                            key
                            for key in st.session_state.translation_cache
                            if key.startswith(f"{song_id}_")
                        ]

                        for key in keys_to_remove:
                            del st.session_state.translation_cache[key]

                        st.session_state.songs = load_songs()

                        st.success(
                            "Song updated successfully!"
                        )

                        st.rerun()

            with col2:

                if st.button(
                    "🗑️ Delete Song",
                    key=f"delete_{song_id}",
                    use_container_width=True
                ):

                    delete_song(song_id)

                    keys_to_remove = [
                        key
                        for key in st.session_state.translation_cache
                        if key.startswith(f"{song_id}_")
                    ]

                    for key in keys_to_remove:
                        del st.session_state.translation_cache[key]

                    st.session_state.songs = load_songs()

                    if (
                        st.session_state.selected_song_id
                        == song_id
                    ):
                        st.session_state.selected_song_id = None

                    st.success(
                        "Song deleted successfully!"
                    )

                    st.rerun()


# ============================================================
# SONG DETAILS PAGE
# ============================================================

def show_song_details(song):

    # --------------------------------------------------------
    # BACK BUTTON
    # --------------------------------------------------------

    if st.button(
        "← Back to Songs",
        use_container_width=False
    ):

        st.session_state.selected_song_id = None

        st.rerun()

    st.divider()

    # --------------------------------------------------------
    # SONG TITLE
    # --------------------------------------------------------

    st.title(
        f"🎵 {song.get('title', 'Untitled')}"
    )

    # --------------------------------------------------------
    # COVER IMAGE
    # --------------------------------------------------------

    cover_url = song.get("cover_url")

    if cover_url:

        try:

            st.image(
                cover_url,
                width=350
            )

        except Exception:
            pass

    # --------------------------------------------------------
    # LANGUAGE SELECTOR
    # --------------------------------------------------------

    st.subheader("🌐 Select Language")

    language = st.selectbox(
        "Choose the script for the lyrics",
        list(LANGUAGES.keys()),
        key=f"language_{song['id']}"
    )

    st.divider()

    # --------------------------------------------------------
    # GET LYRICS
    # --------------------------------------------------------

    lyrics = get_language_version(
        song,
        language
    )

    st.subheader(
        f"📝 Lyrics — {language}"
    )

    # --------------------------------------------------------
    # DISPLAY LYRICS
    # --------------------------------------------------------

    st.text_area(
        "Lyrics",
        value=lyrics,
        height=450,
        key=f"lyrics_display_{song['id']}_{language}",
        disabled=True
    )

    # --------------------------------------------------------
    # COPY BUTTON
    # --------------------------------------------------------

    copy_button(
        lyrics,
        f"{song['id']}_{language}"
    )

    st.divider()

    st.caption(
        "The lyrics are converted from Romanized text "
        "to the selected script without changing the intended words."
    )


# ============================================================
# HOME PAGE
# ============================================================

def home_page():

    st.title("🎵 Devotional Songs")

    st.write(
        "Search for a devotional song and click its name "
        "to read the lyrics."
    )

    st.divider()

    # ========================================================
    # SEARCH
    # ========================================================

    search = st.text_input(
        "🔍 Search Songs",
        placeholder="Enter song name..."
    )

    # ========================================================
    # FILTER SONGS
    # ========================================================

    songs = st.session_state.songs

    if search.strip():

        search_text = search.strip().lower()

        filtered_songs = [
            song
            for song in songs
            if search_text
            in song.get("title", "").lower()
        ]

    else:

        filtered_songs = songs

    # ========================================================
    # SONG LIST
    # ========================================================

    st.subheader("🎶 Songs")

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
            f"🎵 {title}",
            key=f"song_button_{song_id}",
            use_container_width=True
        ):

            st.session_state.selected_song_id = song_id

            st.rerun()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🎵 Devotional Songs")

    st.divider()

    if st.session_state.admin_logged_in:

        st.success(
            "Admin logged in"
        )

        page = st.radio(
            "Menu",
            [
                "🏠 Home",
                "📊 Admin Dashboard"
            ]
        )

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
# LOAD SONGS
# ============================================================

st.session_state.songs = load_songs()


# ============================================================
# PAGE ROUTING
# ============================================================

# ------------------------------------------------------------
# ADMIN LOGIN
# ------------------------------------------------------------

if st.session_state.show_admin_login:

    show_admin_login_page()

# ------------------------------------------------------------
# ADMIN DASHBOARD
# ------------------------------------------------------------

elif (
    st.session_state.admin_logged_in
    and page == "📊 Admin Dashboard"
):

    admin_dashboard()

# ------------------------------------------------------------
# SELECTED SONG
# ------------------------------------------------------------

elif st.session_state.selected_song_id is not None:

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
