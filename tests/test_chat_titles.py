from app.services.chat_titles import (
    derive_chat_session_title,
    is_low_signal_chat_title,
    should_replace_chat_title,
)


def test_derive_chat_session_title_trims_and_truncates():
    assert derive_chat_session_title("  Hello   there ") == "Hello there"
    long_query = "Explain the legal implications of contract clauses " * 8
    out = derive_chat_session_title(long_query, max_len=60)
    assert out is not None
    assert len(out) <= 61
    assert out.endswith("…")


def test_low_signal_title_detection():
    assert is_low_signal_chat_title("conversation")
    assert is_low_signal_chat_title("Hi")
    assert is_low_signal_chat_title("hello?")
    assert not is_low_signal_chat_title("Summarize vendor risks from MSA")


def test_should_replace_only_second_turn_for_low_signal_title():
    assert should_replace_chat_title(None, "Summarize procurement policy", user_turn_count=1)
    assert should_replace_chat_title("hi", "Summarize procurement policy", user_turn_count=2)
    assert not should_replace_chat_title("hi", "thanks", user_turn_count=2)
    assert not should_replace_chat_title("Project kickoff notes", "Summarize procurement policy", user_turn_count=2)
    assert not should_replace_chat_title("hi", "Summarize procurement policy", user_turn_count=3)
