from bot_v2.utils import split_long_message


def test_split_long_message_respects_limit_and_preserves_content():
    text = ("# Project Plan\n\n" + "This is a very long paragraph. " * 40)[:1500]

    chunks = split_long_message(text, max_chars=200)

    assert chunks
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert "".join(chunks) == text
