"""SmartSight AI — hackathon prototype of an audio scene-description assistant.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import hashlib
import io

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

import speech
import tinyfish_client as tf

st.set_page_config(page_title="SmartSight AI", page_icon="👁️", layout="wide")


@st.cache_resource(show_spinner="Loading the vision model (first run downloads it)…")
def get_model():
    import detector

    return detector.load_model()


@st.cache_data(show_spinner=False, max_entries=32)
def cached_wav(text: str) -> bytes | None:
    return speech.synthesize_wav(text)


def speak(text: str, autoplay: bool) -> None:
    """Show an audio player (server TTS) or fall back to browser speech."""
    wav = cached_wav(text)
    if wav:
        st.audio(wav, format="audio/wav", autoplay=autoplay)
    elif autoplay:
        components.html(speech.browser_speech_html(text), height=0)
    else:
        st.caption("Server speech engine unavailable; use the Replay button to speak in your browser.")


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    speech_on = st.toggle("Speak results aloud", value=True)
    conf = st.slider("Detection confidence", 0.10, 0.90, 0.35, 0.05,
                     help="Higher = fewer, more certain detections.")
    st.divider()
    if tf.is_configured():
        st.success("TinyFish API key found")
    else:
        st.warning("TINYFISH_API_KEY not set. Web lookup is disabled until you add it to .env.")
    st.caption(
        "Prototype only. SmartSight AI is not a certified mobility aid and cannot judge "
        "distance, obstacles, or traffic. Do not rely on it for safety."
    )

st.title("👁️ SmartSight AI")
st.write("Take or upload a photo and hear a short description of the everyday objects it contains.")

# ------------------------------------------------------------------ input
tab_upload, tab_camera = st.tabs(["Upload image", "Use camera"])
with tab_upload:
    uploaded = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png", "webp"])
with tab_camera:
    snap = st.camera_input("Take a picture")

source = snap or uploaded
if source is None:
    st.info("Add an image to begin.")

# -------------------------------------------------------------- detection
if source is not None:
    raw = source.getvalue()
    key = hashlib.sha256(raw + str(conf).encode()).hexdigest()

    if st.session_state.get("scene_key") != key:
        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
        except Exception:
            st.error("That file could not be read as an image. Try a JPG or PNG.")
            st.stop()
        import detector

        with st.spinner("Looking at the image…"):
            annotated, dets = detector.detect(get_model(), image, conf=conf)
        st.session_state.scene_key = key
        st.session_state.annotated = annotated
        st.session_state.dets = dets
        st.session_state.sentence = speech.describe_detections([d.label for d in dets])
        st.session_state.autoplay = True  # speak automatically for a new scene

    annotated = st.session_state.annotated
    dets = st.session_state.dets
    sentence = st.session_state.sentence

    left, right = st.columns([3, 2])
    with left:
        st.image(annotated, caption="Detected objects", use_container_width=True)
    with right:
        st.subheader("What I found")
        st.write(sentence)
        if dets:
            st.dataframe(
                [{"Object": d.label, "Confidence": f"{d.confidence:.0%}"} for d in dets],
                hide_index=True, use_container_width=True,
            )
        else:
            st.caption("Try a clearer photo, better lighting, or a lower confidence setting.")
        st.caption("The model recognises 80 common COCO classes. Doors, stairs and "
                   "signs are not among them.")

        if speech_on:
            if st.button("🔁 Replay"):
                st.session_state.autoplay = True
            speak(sentence, autoplay=st.session_state.pop("autoplay", False))
        else:
            st.session_state.pop("autoplay", None)

    st.divider()

    # -------------------------------------------------------- web lookup
    st.subheader("Look something up")
    st.caption("Powered by TinyFish Search and Fetch.")

    labels = sorted({d.label for d in dets})
    c1, c2 = st.columns([1, 3])
    with c1:
        pick = st.selectbox("Detected object", ["(none)"] + labels)
    default_q = f"what is a {pick}" if pick != "(none)" else ""
    with c2:
        query = st.text_input("Search query", value=default_q, key=f"q_{pick}",
                              placeholder="e.g. how to identify medication labels")

    if st.button("🔎 Search the web", disabled=not tf.is_configured()):
        try:
            with st.spinner("Searching…"):
                st.session_state.web_results = tf.search(query)[:5]
            st.session_state.web_query = query
            st.session_state.pop("page", None)
        except tf.TinyFishError as exc:
            st.error(str(exc))

    results = st.session_state.get("web_results")
    if results is not None:
        if not results:
            st.info("No web results found for that query.")
        for i, r in enumerate(results):
            with st.container(border=True):
                st.markdown(f"**{r.get('title', 'Untitled')}**  \n{r.get('site_name', '')}")
                if r.get("snippet"):
                    st.write(r["snippet"])
                if r.get("url"):
                    st.markdown(f"[Open source]({r['url']})")
                    if st.button("📄 Read this page", key=f"read_{i}", disabled=not tf.is_configured()):
                        try:
                            with st.spinner("Fetching page…"):
                                st.session_state.page = tf.fetch_page_text(r["url"])
                        except tf.TinyFishError as exc:
                            st.error(str(exc))

        if speech_on and results:
            top = results[0]
            brief = f"Top result: {top.get('title', '')}. {top.get('snippet', '')}".strip()
            if st.button("🔊 Read top result aloud"):
                speak(brief[:500], autoplay=True)

    page = st.session_state.get("page")
    if page:
        with st.expander(f"Page: {page['title']}", expanded=True):
            st.markdown(page["text"])
            st.caption(page["url"])
            if speech_on and st.button("🔊 Read the start aloud"):
                speak(page["text"][:600], autoplay=True)
