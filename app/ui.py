import time

import streamlit as st

from app.client import VerityError, ask_stream, upload_pdf

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
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()


def show_details(message):
    for source in message.get("sources", []):
        st.caption(f"Source: {source['source']}, page {source['page']}")
    if message.get("searched_for"):
        st.caption(f"Searched for: {message['searched_for']}")
    if message.get("status") not in (None, "answered"):
        st.caption(f"status: {message['status']}")


def render(message):
    with st.chat_message(message["role"]):
        st.write(message["content"])
        show_details(message)


def type_out(text):
    """Type an already verified answer out word by word."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02)


def build_history():
    """Previous turns only. Error messages are not sent as history."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m["role"] == "user" or m.get("status")
    ]


for message in st.session_state.messages:
    render(message)

question = st.chat_input("Ask about your documents")
if question:
    history = build_history()
    user_message = {"role": "user", "content": question}
    st.session_state.messages.append(user_message)
    render(user_message)

    with st.chat_message("assistant"):
        status = st.status("Starting...", expanded=False)
        try:
            result = None
            for event in ask_stream(question, history=history):
                if event["event"] == "stage":
                    status.update(label=event["message"])
                elif event["event"] == "result":
                    result = event["result"]
                elif event["event"] == "error":
                    raise VerityError(event["message"])
            if result is None:
                raise VerityError("No answer was returned. Please try again.")
            status.update(label="Done", state="complete")
            st.write_stream(type_out(result["answer"]))
            used = result.get("question_used")
            reply = {
                "role": "assistant",
                "content": result["answer"],
                "sources": result["sources"],
                "status": result["status"],
                "searched_for": used if used and used != question else None,
            }
            show_details(reply)
        except VerityError as exc:
            status.update(label="Failed", state="error")
            st.write(str(exc))
            reply = {"role": "assistant", "content": str(exc), "sources": []}
    st.session_state.messages.append(reply)
