import streamlit as st

from app.client import VerityError, ask, upload_pdf

st.set_page_config(page_title="Verity", page_icon="??")
st.title("Verity")
st.caption(
    "Answers from your documents, with page citations. "
    "If it is not in your documents, Verity says so."
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded" not in st.session_state:
    st.session_state.uploaded = []

with st.sidebar:
    st.header("Documents")
    file = st.file_uploader("Upload a PDF", type="pdf")
    if file is not None and file.name not in st.session_state.uploaded:
        with st.spinner("Reading and indexing..."):
            try:
                result = upload_pdf(file.name, file.getvalue())
                st.session_state.uploaded.append(file.name)
                st.success(f"{result['filename']}: {result['chunks']} chunks")
            except VerityError as exc:
                st.error(str(exc))
    for name in st.session_state.uploaded:
        st.write(f"- {name}")


def render(message):
    with st.chat_message(message["role"]):
        st.write(message["content"])
        for source in message.get("sources", []):
            st.caption(f"Source: {source['source']}, page {source['page']}")
        if message.get("status") not in (None, "answered"):
            st.caption(f"status: {message['status']}")


for message in st.session_state.messages:
    render(message)

question = st.chat_input("Ask about your documents")
if question:
    user_message = {"role": "user", "content": question}
    st.session_state.messages.append(user_message)
    render(user_message)
    try:
        with st.spinner("Searching your documents..."):
            result = ask(question)
        reply = {
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
            "status": result["status"],
        }
    except VerityError as exc:
        reply = {"role": "assistant", "content": str(exc), "sources": []}
    st.session_state.messages.append(reply)
    render(reply)
