import streamlit as st
from supabase import create_client, Client
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
        padding: 20px;
        border-radius: 18px;
        border: 1px solid #dddddd;
        margin-bottom: 20px;
    }

    .song-title {
        font-size: 26px;
        font-weight: 700;
    }

    .lyrics-box {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #dddddd;
        white-space: pre-wrap;
        font-size: 17px;
        line-height: 1.7;
    }

    .admin-title {
        font-size: 32px;
        font-weight: 700;
    }

    footer {
        visibility: hidden;
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
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

    supabase: Client = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

except Exception:
    st.error(
        "Supabase is not connected yet. "
        "Please configure SUPABASE_URL and SUPABASE_KEY "
        "in Streamlit Secrets."
    )
    st.stop()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_songs():
    """Load all songs from Supabase."""
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


def add_song(title, lyrics, cover_url=""):
    """Add a new song."""
    try:
        data = {
            "title": title.strip(),
            "lyrics": lyrics,
            "cover_url": cover_url
        }

        supabase.table("songs").insert(data).execute()
        return True

    except Exception as e:
        st.error(f"Could not add song: {e}")
        return False


def update_song(song_id, title, lyrics, cover_url=""):
    """Update an existing song."""
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


def delete_song(song_id):
    """Delete a song."""
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


def upload_cover(uploaded_file):
    """Upload a cover image to Supabase Storage."""

    if uploaded_file is None:
        return ""

    try:
        file_extension = uploaded_file.name.split(".")[-1].lower()

        filename = f"{uuid.uuid4()}.{file_extension}"

        file_bytes = uploaded_file.getvalue()

        supabase.storage.from_("song-covers").upload(
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


def copy_button(text, button_id):
    """Create a copy-to-clipboard button."""

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
        const button = document.getElementById("copy_{safe_id}");

        button.onclick = function() {{
            const text = `{safe_text}`;

            navigator.clipboard.writeText(text).then(function() {{
                button.innerText = "✅ Copied!";
                setTimeout(function() {{
                    button.innerText = "📋 Copy Lyrics";
                }}, 2000);
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
    '<div class="main-title">🙏 Devotional Songs</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Listen with devotion • Read • Sing • Share'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🎵 Devotional Songs")

    page = st.radio(
        "Navigate",
        [
            "🏠 Home",
            "🔐 Admin"
        ]
    )


# ============================================================
# HOME PAGE
# ============================================================

if page == "🏠 Home":

    songs = load_songs()

    st.markdown("## 🎵 Song Library")

    search = st.text_input(
        "🔎 Search songs",
        placeholder="Search by song title..."
    )

    if search:
        songs = [
            song for song in songs
            if search.lower() in song.get("title", "").lower()
        ]

    if not songs:

        st.info(
            "No songs are available yet. "
            "The administrator can add songs from the Admin page."
        )

    else:

        for song in songs:

            title = song.get("title", "Untitled Song")
            lyrics = song.get("lyrics", "")
            cover_url = song.get("cover_url", "")

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
                f'<div class="song-title">🎵 '
                f'{html.escape(title)}</div>',
                unsafe_allow_html=True
            )

            st.divider()

            st.markdown("### 📖 Lyrics")

            st.markdown(
                f'<div class="lyrics-box">'
                f'{html.escape(lyrics)}'
                f'</div>',
                unsafe_allow_html=True
            )

            st.write("")

            copy_button(
                lyrics,
                song.get("id", "song")
            )

            st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# ADMIN PAGE
# ============================================================

elif page == "🔐 Admin":

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    if not st.session_state.admin_logged_in:

        st.markdown(
            '<div class="admin-title">🔐 Admin Login</div>',
            unsafe_allow_html=True
        )

        st.write(
            "Only the administrator can add, edit, or delete songs."
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

                st.success("Login successful!")

                st.rerun()

            else:

                st.error(
                    "Incorrect username or password."
                )

    # --------------------------------------------------------
    # ADMIN DASHBOARD
    # --------------------------------------------------------

    else:

        st.markdown(
            '<div class="admin-title">'
            '⚙️ Admin Dashboard'
            '</div>',
            unsafe_allow_html=True
        )

        if st.button("🚪 Logout"):

            st.session_state.admin_logged_in = False

            st.rerun()

        st.divider()

        admin_action = st.radio(
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

        if admin_action == "➕ Add Song":

            st.subheader("➕ Add New Song")

            title = st.text_input(
                "Song Title"
            )

            lyrics = st.text_area(
                "Lyrics",
                height=350,
                placeholder="Write the complete lyrics here..."
            )

            cover = st.file_uploader(
                "🖼️ Song Cover Image (optional)",
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

                    if cover is not None:

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

        elif admin_action == "✏️ Edit Song":

            songs = load_songs()

            if not songs:

                st.info(
                    "There are no songs to edit."
                )

            else:

                song_options = {
                    f"{song['title']} (ID: {song['id']})":
                    song
                    for song in songs
                }

                selected_label = st.selectbox(
                    "Select a song",
                    list(song_options.keys())
                )

                selected_song = song_options[
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
                    height=350
                )

                new_cover = st.file_uploader(
                    "🖼️ Replace Cover Image (optional)",
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

                    if new_cover is not None:

                        uploaded_url = upload_cover(
                            new_cover
                        )

                        if uploaded_url:
                            cover_url = uploaded_url

                    if update_song(
                        selected_song["id"],
                        edit_title,
                        edit_lyrics,
                        cover_url
                    ):

                        st.success(
                            "✅ Song updated successfully!"
                        )

                        st.rerun()

        # ====================================================
        # DELETE SONG
        # ====================================================

        elif admin_action == "🗑️ Delete Song":

            songs = load_songs()

            if not songs:

                st.info(
                    "There are no songs to delete."
                )

            else:

                song_options = {
                    f"{song['title']} (ID: {song['id']})":
                    song
                    for song in songs
                }

                selected_label = st.selectbox(
                    "Select a song to delete",
                    list(song_options.keys())
                )

                selected_song = song_options[
                    selected_label
                ]

                st.warning(
                    f'You are about to delete '
                    f'"{selected_song["title"]}". '
                    f'This cannot be undone.'
                )

                confirm = st.checkbox(
                    "I understand that this song will be permanently deleted."
                )

                if st.button(
                    "🗑️ Delete Song",
                    use_container_width=True
                ):

                    if not confirm:

                        st.warning(
                            "Please confirm the deletion first."
                        )

                    else:

                        if delete_song(
                            selected_song["id"]
                        ):

                            st.success(
                                "Song deleted successfully."
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
