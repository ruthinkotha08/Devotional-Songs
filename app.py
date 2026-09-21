import streamlit as st
from supabase import create_client, Client
from openai import OpenAI
import html
import uuid


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Devotional Songs",
    page_icon="🙏",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# INDIAN LANGUAGES
# ============================================================

LANGUAGES = {
    "English": "English",
    "Telugu": "Telugu",
    "Hindi": "Hindi",
    "Tamil": "Tamil",
    "Kannada": "Kannada",
    "Malayalam": "Malayalam",
    "Sanskrit": "Sanskrit",
}


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        text-align: center;
        font-size: 48px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .subtitle {
        text-align: center;
        font-size: 18px;
        margin-bottom: 35px;
    }

    .song-card {
        padding: 25px;
        border-radius: 18px;
        border: 1px solid #dddddd;
        margin-bottom: 25px;
    }

    .song-title {
        font-size: 28px;
        font-weight: 700;
    }

    .lyrics-box {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #dddddd;
        white-space: pre-wrap;
        font-size: 18px;
        line-height: 1.8;
    }

    .admin-title {
        font-size: 32px;
        font-weight: 700;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SUPABASE CONNECTION
# ============================================================

try:

    SUPABASE_URL = st.secrets["SUPABASE_URL"]

    # Use the server-side Supabase key here.
    # Keep this ONLY in Streamlit Secrets.
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

    supabase: Client = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

except Exception as e:

    st.error("Supabase connection is not configured.")
    st.stop()


# ============================================================
# OPENAI CONNECTION
# ============================================================

try:

    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

    openai_client = OpenAI(
        api_key=OPENAI_API_KEY
    )

except Exception:

    openai_client = None


# ============================================================
# LOAD SONGS
# ============================================================

def load_songs():

    try:

        response = (
            supabase
            .table("songs")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []

    except Exception as e:

        st.error(f"Could not load songs: {e}")

        return []


# ============================================================
# ADD SONG
# ============================================================

def add_song(title, lyrics, cover_url=""):

    try:

        data = {
            "title": title.strip(),
            "lyrics": lyrics,
            "cover_url": cover_url,
            "translations": {}
        }

        supabase.table("songs").insert(data).execute()

        return True

    except Exception as e:

        st.error(f"Could not add song: {e}")

        return False


# ============================================================
# UPDATE SONG
# ============================================================

def update_song(song_id, title, lyrics, cover_url=""):

    try:

        data = {
            "title": title.strip(),
            "lyrics": lyrics,
            "cover_url": cover_url
        }

        (
            supabase
            .table("songs")
            .update(data)
            .eq("id", song_id)
            .execute()
        )

        return True

    except Exception as e:

        st.error(f"Could not update song: {e}")

        return False


# ============================================================
# DELETE SONG
# ============================================================

def delete_song(song_id):

    try:

        (
            supabase
            .table("songs")
            .delete()
            .eq("id", song_id)
            .execute()
        )

        return True

    except Exception as e:

        st.error(f"Could not delete song: {e}")

        return False


# ============================================================
# UPLOAD COVER
# ============================================================

def upload_cover(uploaded_file):

    if uploaded_file is None:
        return ""

    try:

        extension = uploaded_file.name.split(".")[-1].lower()

        filename = f"{uuid.uuid4()}.{extension}"

        file_bytes = uploaded_file.getvalue()

        supabase.storage \
            .from_("song-covers") \
            .upload(
                filename,
                file_bytes,
                {
                    "content-type": uploaded_file.type
                }
            )

        public_url = (
            supabase
            .storage
            .from_("song-covers")
            .get_public_url(filename)
        )

        return public_url

    except Exception as e:

        st.error(f"Could not upload cover image: {e}")

        return ""


# ============================================================
# AI SCRIPT CONVERSION
# ============================================================

def convert_to_language(lyrics, target_language):

    if not lyrics.strip():
        return ""

    if target_language == "English":

        return lyrics

    if openai_client is None:

        st.error(
            "AI translation is not configured. "
            "Please add OPENAI_API_KEY to Streamlit Secrets."
        )

        return ""

    prompt = f"""
You are a multilingual Indian-language transliteration specialist.

The user has provided devotional song lyrics written using
English/Roman letters.

Your job is NOT to translate the meaning.

Your job is to convert the SAME WORDS, sounds, pronunciation,
and lyrical content into the writing system normally used
for {target_language}.

IMPORTANT RULES:

1. DO NOT translate the meaning.
2. DO NOT summarize.
3. DO NOT rewrite the lyrics.
4. DO NOT add explanations.
5. Preserve the original line breaks.
6. Preserve repeated lines and words.
7. Preserve names of gods, goddesses, people and places.
8. Preserve devotional words.
9. Convert the Roman/English spelling into the appropriate
   script for {target_language}.
10. Make the result readable and natural in that script.
11. Do not add quotation marks.
12. Return ONLY the converted lyrics.

Example:

Input:
Namaskaram andariki

Target language:
Telugu

Output:
నమస్కారం అందరికీ

Example:

Input:
Namaskaram andariki

Target language:
Hindi

Output:
नमस्कारम अंदरिकी

Example:

Input:
Namaskaram andariki

Target language:
Tamil

Output:
நமஸ்காரம் அந்தரிகீ

Now convert these lyrics to {target_language}:

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

        return ""


# ============================================================
# GET TRANSLATION / SCRIPT VERSION
# ============================================================

def get_language_version(song, language):

    if language == "English":

        return song.get("lyrics", "")

    translations = song.get(
        "translations"
    ) or {}

    if language in translations:

        return translations[language]

    lyrics = song.get(
        "lyrics",
        ""
    )

    with st.spinner(
        f"Converting lyrics to {language}..."
    ):

        converted = convert_to_language(
            lyrics,
            language
        )

    if not converted:

        return ""

    # Save generated version
    translations[language] = converted

    try:

        (
            supabase
            .table("songs")
            .update(
                {
                    "translations": translations
                }
            )
            .eq(
                "id",
                song["id"]
            )
            .execute()
        )

    except Exception as e:

        # The user can still see the generated result
        # even if saving the translation fails.
        pass

    return converted


# ============================================================
# COPY BUTTON
# ============================================================

def copy_button(text, button_id):

    safe_text = html.escape(text)
    safe_id = html.escape(str(button_id))

    st.components.v1.html(
        f"""
        <button
            id="copy_{safe_id}"
            style="
                padding:10px 18px;
                border:none;
                border-radius:8px;
                cursor:pointer;
                font-size:15px;
            "
        >
            📋 Copy Lyrics
        </button>

        <script>

        const button =
            document.getElementById("copy_{safe_id}");

        button.onclick = function() {{

            const text = `{safe_text}`;

            navigator.clipboard
                .writeText(text)
                .then(function() {{

                    button.innerText = "✅ Copied!";

                    setTimeout(
                        function() {{
                            button.innerText =
                                "📋 Copy Lyrics";
                        }},
                        2000
                    );

                }});
        }};

        </script>
        """,
        height=55
    )


# ============================================================
# SESSION STATE
# ============================================================

if "admin_logged_in" not in st.session_state:

    st.session_state.admin_logged_in = False


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="main-title">
        🙏 Devotional Songs
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="subtitle">
        Read • Sing • Share • Experience in your language
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🙏 Devotional Songs"
    )

    page = st.radio(
        "Navigate",
        [
            "🏠 Home",
            "🔐 Admin"
        ]
    )


# ============================================================
# HOME
# ============================================================

if page == "🏠 Home":

    songs = load_songs()

    st.markdown(
        "## 🎵 Song Library"
    )

    search = st.text_input(
        "🔎 Search songs",
        placeholder="Search by song title..."
    )

    if search:

        songs = [
            song
            for song in songs
            if search.lower()
            in song.get(
                "title",
                ""
            ).lower()
        ]

    if not songs:

        st.info(
            "No songs are available yet."
        )

    else:

        for song in songs:

            title = song.get(
                "title",
                "Untitled Song"
            )

            lyrics = song.get(
                "lyrics",
                ""
            )

            cover_url = song.get(
                "cover_url",
                ""
            )

            st.markdown(
                '<div class="song-card">',
                unsafe_allow_html=True
            )

            if cover_url:

                st.image(
                    cover_url,
                    use_container_width=True
                )

            st.markdown(
                f"""
                <div class="song-title">
                    🎵 {html.escape(title)}
                </div>
                """,
                unsafe_allow_html=True
            )

            st.divider()

            # ------------------------------------------------
            # LANGUAGE SELECTOR
            # ------------------------------------------------

            language = st.selectbox(
                "🌐 Choose language/script",
                list(LANGUAGES.keys()),
                key=f"language_{song['id']}"
            )

            # ------------------------------------------------
            # GET SELECTED VERSION
            # ------------------------------------------------

            displayed_lyrics = get_language_version(
                song,
                language
            )

            st.markdown(
                "### 📖 Lyrics"
            )

            st.markdown(
                f"""
                <div class="lyrics-box">
                {html.escape(displayed_lyrics)}
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write("")

            copy_button(
                displayed_lyrics,
                f"{song['id']}_{language}"
            )

            st.markdown(
                "</div>",
                unsafe_allow_html=True
            )


# ============================================================
# ADMIN
# ============================================================

elif page == "🔐 Admin":

    # ========================================================
    # ADMIN LOGIN
    # ========================================================

    if not st.session_state.admin_logged_in:

        st.markdown(
            """
            <div class="admin-title">
                🔐 Admin Login
            </div>
            """,
            unsafe_allow_html=True
        )

        username = st.text_input(
            "Username"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button(
            "🔓 Login",
            use_container_width=True
        ):

            admin_username = st.secrets.get(
                "ADMIN_USERNAME",
                ""
            )

            admin_password = st.secrets.get(
                "ADMIN_PASSWORD",
                ""
            )

            if (
                username == admin_username
                and password == admin_password
            ):

                st.session_state.admin_logged_in = True

                st.success(
                    "Login successful!"
                )

                st.rerun()

            else:

                st.error(
                    "Incorrect username or password."
                )


    # ========================================================
    # ADMIN DASHBOARD
    # ========================================================

    else:

        st.markdown(
            """
            <div class="admin-title">
                ⚙️ Admin Dashboard
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button("🚪 Logout"):

            st.session_state.admin_logged_in = False

            st.rerun()

        st.divider()

        action = st.radio(
            "Choose an action",
            [
                "➕ Add Song",
                "✏️ Edit Song",
                "🗑️ Delete Song"
            ],
            horizontal=True
        )


        # ====================================================
        # ADD SONG
        # ====================================================

        if action == "➕ Add Song":

            st.subheader(
                "➕ Add New Song"
            )

            title = st.text_input(
                "Song Title"
            )

            lyrics = st.text_area(
                "Lyrics",
                height=400,
                placeholder=(
                    "Write your lyrics using "
                    "English/Roman letters..."
                )
            )

            cover = st.file_uploader(
                "🖼️ Song Cover Image",
                type=[
                    "jpg",
                    "jpeg",
                    "png",
                    "webp"
                ]
            )

            if st.button(
                "💾 Add Song",
                use_container_width=True
            ):

                if not title.strip():

                    st.warning(
                        "Please enter a song title."
                    )

                elif not lyrics.strip():

                    st.warning(
                        "Please enter the lyrics."
                    )

                else:

                    cover_url = ""

                    if cover:

                        cover_url = upload_cover(
                            cover
                        )

                    if add_song(
                        title,
                        lyrics,
                        cover_url
                    ):

                        st.success(
                            "🎉 Song added successfully!"
                        )

                        st.rerun()


        # ====================================================
        # EDIT SONG
        # ====================================================

        elif action == "✏️ Edit Song":

            songs = load_songs()

            if not songs:

                st.info(
                    "No songs available."
                )

            else:

                options = {
                    f"{song['title']} "
                    f"(ID: {song['id']})":
                    song
                    for song in songs
                }

                selected_label = st.selectbox(
                    "Select song",
                    list(options.keys())
                )

                selected_song = options[
                    selected_label
                ]

                edit_title = st.text_input(
                    "Song Title",
                    value=selected_song.get(
                        "title",
                        ""
                    )
                )

                edit_lyrics = st.text_area(
                    "Lyrics",
                    value=selected_song.get(
                        "lyrics",
                        ""
                    ),
                    height=400
                )

                new_cover = st.file_uploader(
                    "🖼️ Replace Cover",
                    type=[
                        "jpg",
                        "jpeg",
                        "png",
                        "webp"
                    ]
                )

                if st.button(
                    "💾 Save Changes",
                    use_container_width=True
                ):

                    cover_url = selected_song.get(
                        "cover_url",
                        ""
                    )

                    if new_cover:

                        new_url = upload_cover(
                            new_cover
                        )

                        if new_url:

                            cover_url = new_url

                    if update_song(
                        selected_song["id"],
                        edit_title,
                        edit_lyrics,
                        cover_url
                    ):

                        st.success(
                            "✅ Song updated!"
                        )

                        st.rerun()


        # ====================================================
        # DELETE SONG
        # ====================================================

        elif action == "🗑️ Delete Song":

            songs = load_songs()

            if not songs:

                st.info(
                    "No songs available."
                )

            else:

                options = {
                    f"{song['title']} "
                    f"(ID: {song['id']})":
                    song
                    for song in songs
                }

                selected_label = st.selectbox(
                    "Select song to delete",
                    list(options.keys())
                )

                selected_song = options[
                    selected_label
                ]

                st.warning(
                    f'You are deleting '
                    f'"{selected_song["title"]}".'
                )

                confirm = st.checkbox(
                    "I understand this cannot be undone."
                )

                if st.button(
                    "🗑️ Delete Song",
                    use_container_width=True
                ):

                    if not confirm:

                        st.warning(
                            "Please confirm deletion."
                        )

                    else:

                        if delete_song(
                            selected_song["id"]
                        ):

                            st.success(
                                "Song deleted."
                            )

                            st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.markdown(
    """
    <div style="text-align:center;">
        🙏 <b>Devotional Songs</b><br>
        Read • Sing • Share
    </div>
    """,
    unsafe_allow_html=True
)
