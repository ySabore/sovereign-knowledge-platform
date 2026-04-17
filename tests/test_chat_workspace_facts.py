from app.services.chat_workspace_facts import is_workspace_fact_query


def test_detects_workspace_fact_count_queries():
    assert is_workspace_fact_query("How many documents do we have in this workspace?")
    assert is_workspace_fact_query("number of indexed docs")
    assert is_workspace_fact_query("count files here")
    assert is_workspace_fact_query("how many chunks are indexed?")


def test_detects_workspace_fact_listing_queries():
    assert is_workspace_fact_query("what documents do we have?")
    assert is_workspace_fact_query("list documents in this workspace")
    assert is_workspace_fact_query("show documents")


def test_detects_workspace_fact_operational_queries():
    assert is_workspace_fact_query("How many documents were added this week?")
    assert is_workspace_fact_query("Show source breakdown for docs")
    assert is_workspace_fact_query("How many conversations do I have in this workspace?")
    assert is_workspace_fact_query("Which failed documents do we have?")
    assert is_workspace_fact_query("Are there stuck processing documents?")


def test_ignores_regular_semantic_questions():
    assert not is_workspace_fact_query("Summarize the retention policy.")
    assert not is_workspace_fact_query("What does checkpoint band 3 mean?")
    assert not is_workspace_fact_query("Explain conflicts of interest.")
