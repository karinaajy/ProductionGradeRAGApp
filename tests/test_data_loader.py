from data_loader import load_and_chunk_pdf

def test_chunking_produces_nonempty_chunks(tmp_path):
    # you'll need a tiny sample PDF in tests/fixtures/ for this
    sample_pdf = "tests/fixtures/sample.pdf"
    chunks = load_and_chunk_pdf(sample_pdf)
    assert len(chunks) > 0
    assert all(isinstance(c, str) and len(c) > 0 for c in chunks)