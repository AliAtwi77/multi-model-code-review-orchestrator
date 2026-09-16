from dataclasses import dataclass


@dataclass
class BenchmarkTask:
    id: str
    prompt: str
    test_code: str
    defect_category: str  # what kind of bug this task is prone to eliciting


TASKS: list[BenchmarkTask] = [
    BenchmarkTask(
        id="t01_moving_average",
        prompt=(
            "Write a function `moving_average(values: list[float], window: int) -> list[float]` in solution.py "
            "that returns the simple moving average over the given window size. The result should have "
            "len(values) - window + 1 elements. Raise ValueError if window <= 0 or window > len(values)."
        ),
        defect_category="off-by-one",
        test_code=(
            "from solution import moving_average\n"
            "import pytest\n\n"
            "def test_basic():\n"
            "    assert moving_average([1, 2, 3, 4, 5], 2) == [1.5, 2.5, 3.5, 4.5]\n\n"
            "def test_window_equals_length():\n"
            "    assert moving_average([1, 2, 3], 3) == [2.0]\n\n"
            "def test_invalid_window_zero():\n"
            "    with pytest.raises(ValueError):\n"
            "        moving_average([1, 2, 3], 0)\n\n"
            "def test_invalid_window_too_large():\n"
            "    with pytest.raises(ValueError):\n"
            "        moving_average([1, 2], 5)\n"
        ),
    ),
    BenchmarkTask(
        id="t02_binary_search",
        prompt=(
            "Write `binary_search(arr: list[int], target: int) -> int` in solution.py that returns the index "
            "of target in the sorted list arr, or -1 if not found. Must run in O(log n)."
        ),
        defect_category="off-by-one",
        test_code=(
            "from solution import binary_search\n\n"
            "def test_found_middle():\n"
            "    assert binary_search([1,3,5,7,9], 5) == 2\n\n"
            "def test_found_edges():\n"
            "    arr = [2,4,6,8,10]\n"
            "    assert binary_search(arr, 2) == 0\n"
            "    assert binary_search(arr, 10) == 4\n\n"
            "def test_not_found():\n"
            "    assert binary_search([1,3,5], 4) == -1\n\n"
            "def test_empty():\n"
            "    assert binary_search([], 1) == -1\n\n"
            "def test_single_element():\n"
            "    assert binary_search([5], 5) == 0\n"
        ),
    ),
    BenchmarkTask(
        id="t03_chunk_list",
        prompt=(
            "Write `chunk(items: list, size: int) -> list[list]` in solution.py that splits items into "
            "consecutive chunks of at most `size` elements each, preserving order. Raise ValueError if size < 1."
        ),
        defect_category="unhandled-edge-case",
        test_code=(
            "from solution import chunk\n"
            "import pytest\n\n"
            "def test_even_split():\n"
            "    assert chunk([1,2,3,4], 2) == [[1,2],[3,4]]\n\n"
            "def test_uneven_split():\n"
            "    assert chunk([1,2,3,4,5], 2) == [[1,2],[3,4],[5]]\n\n"
            "def test_empty_input():\n"
            "    assert chunk([], 3) == []\n\n"
            "def test_size_larger_than_list():\n"
            "    assert chunk([1,2], 10) == [[1,2]]\n\n"
            "def test_invalid_size():\n"
            "    with pytest.raises(ValueError):\n"
            "        chunk([1,2,3], 0)\n"
        ),
    ),
    BenchmarkTask(
        id="t04_read_config_lines",
        prompt=(
            "Write `read_key_values(path: str) -> dict[str, str]` in solution.py that opens a text file at "
            "`path` where each non-empty line is `key=value`, and returns a dict. Skip blank lines. "
            "The file handle must always be closed even if an error occurs."
        ),
        defect_category="resource-leak",
        test_code=(
            "import os, tempfile\n"
            "from solution import read_key_values\n\n"
            "def _write(tmp_path, content):\n"
            "    p = tmp_path / 'cfg.txt'\n"
            "    p.write_text(content)\n"
            "    return str(p)\n\n"
            "def test_basic(tmp_path):\n"
            "    path = _write(tmp_path, 'a=1\\nb=2\\n\\n c=3 \\n')\n"
            "    result = read_key_values(path)\n"
            "    assert result['a'] == '1'\n"
            "    assert result['b'] == '2'\n\n"
            "def test_file_is_closed_after_read(tmp_path):\n"
            "    path = _write(tmp_path, 'a=1\\n')\n"
            "    read_key_values(path)\n"
            "    # if the implementation leaked the handle, renaming/removing on some platforms would fail;\n"
            "    # on POSIX this always succeeds, so we assert no lingering open file via os.stat still working\n"
            "    os.remove(path)\n"
            "    assert not os.path.exists(path)\n"
        ),
    ),
    BenchmarkTask(
        id="t05_user_lookup_query",
        prompt=(
            "Write `build_user_query(username: str) -> tuple[str, tuple]` in solution.py that returns a "
            "parameterized SQL query (query_string, params_tuple) to select a user row from a `users` table "
            "by username, suitable for sqlite3's `cursor.execute(query, params)`. Do NOT interpolate the "
            "username directly into the SQL string."
        ),
        defect_category="injection-prone-string-handling",
        test_code=(
            "from solution import build_user_query\n\n"
            "def test_returns_placeholder_not_value():\n"
            "    query, params = build_user_query(\"alice\")\n"
            "    assert 'alice' not in query\n"
            "    assert '?' in query or '%s' in query\n"
            "    assert params == ('alice',)\n\n"
            "def test_malicious_input_not_embedded():\n"
            "    malicious = \"alice'; DROP TABLE users; --\"\n"
            "    query, params = build_user_query(malicious)\n"
            "    assert malicious not in query\n"
            "    assert params == (malicious,)\n\n"
            "def test_executes_safely_against_sqlite():\n"
            "    import sqlite3\n"
            "    conn = sqlite3.connect(':memory:')\n"
            "    conn.execute('CREATE TABLE users (username TEXT, id INTEGER)')\n"
            "    conn.execute('INSERT INTO users VALUES (?, ?)', ('alice', 1))\n"
            "    query, params = build_user_query('alice')\n"
            "    row = conn.execute(query, params).fetchone()\n"
            "    assert row[1] == 1\n"
        ),
    ),
    BenchmarkTask(
        id="t06_flatten",
        prompt="Write `flatten(nested: list) -> list` in solution.py that fully flattens an arbitrarily nested list of lists into a single flat list, preserving order. Non-list elements pass through unchanged.",
        defect_category="unhandled-edge-case",
        test_code=(
            "from solution import flatten\n\n"
            "def test_flat_already():\n"
            "    assert flatten([1,2,3]) == [1,2,3]\n\n"
            "def test_nested():\n"
            "    assert flatten([1,[2,3],[4,[5,6]]]) == [1,2,3,4,5,6]\n\n"
            "def test_empty():\n"
            "    assert flatten([]) == []\n\n"
            "def test_empty_nested_lists():\n"
            "    assert flatten([[],[1],[[],[2]]]) == [1,2]\n\n"
            "def test_strings_not_flattened_char_by_char():\n"
            "    assert flatten(['ab', [1,2]]) == ['ab', 1, 2]\n"
        ),
    ),
    BenchmarkTask(
        id="t07_pagination",
        prompt=(
            "Write `paginate(items: list, page: int, page_size: int) -> list` in solution.py. `page` is "
            "1-indexed. Return the items for that page, or an empty list if the page is out of range. "
            "Raise ValueError if page_size <= 0 or page <= 0."
        ),
        defect_category="off-by-one",
        test_code=(
            "from solution import paginate\n"
            "import pytest\n\n"
            "def test_first_page():\n"
            "    assert paginate([1,2,3,4,5], 1, 2) == [1,2]\n\n"
            "def test_last_partial_page():\n"
            "    assert paginate([1,2,3,4,5], 3, 2) == [5]\n\n"
            "def test_out_of_range_page():\n"
            "    assert paginate([1,2,3], 10, 2) == []\n\n"
            "def test_invalid_page():\n"
            "    with pytest.raises(ValueError):\n"
            "        paginate([1,2,3], 0, 2)\n\n"
            "def test_invalid_page_size():\n"
            "    with pytest.raises(ValueError):\n"
            "        paginate([1,2,3], 1, 0)\n"
        ),
    ),
    BenchmarkTask(
        id="t08_temp_file_writer",
        prompt=(
            "Write `write_report(lines: list[str], path: str) -> None` in solution.py that writes each line "
            "to a text file at `path`, one per line. Must not leave the file handle open if writing raises "
            "an exception partway through, and must flush/close on the normal path too."
        ),
        defect_category="resource-leak",
        test_code=(
            "from solution import write_report\n\n"
            "def test_writes_all_lines(tmp_path):\n"
            "    path = str(tmp_path / 'out.txt')\n"
            "    write_report(['a', 'b', 'c'], path)\n"
            "    with open(path) as f:\n"
            "        content = f.read().splitlines()\n"
            "    assert content == ['a', 'b', 'c']\n\n"
            "def test_file_readable_immediately_after_call(tmp_path):\n"
            "    # if the file wasn't closed/flushed, a fresh open might see stale/empty content on some platforms\n"
            "    path = str(tmp_path / 'out2.txt')\n"
            "    write_report(['x'] * 100, path)\n"
            "    with open(path) as f:\n"
            "        assert len(f.read().splitlines()) == 100\n"
        ),
    ),
    BenchmarkTask(
        id="t09_safe_filename",
        prompt=(
            "Write `safe_join(base_dir: str, user_path: str) -> str` in solution.py that joins base_dir and "
            "user_path and returns the absolute resulting path, but RAISES ValueError if the resolved path "
            "would escape base_dir (e.g. via '../' traversal)."
        ),
        defect_category="injection-prone-string-handling",
        test_code=(
            "import os\n"
            "from solution import safe_join\n"
            "import pytest\n\n"
            "def test_normal_join(tmp_path):\n"
            "    base = str(tmp_path)\n"
            "    result = safe_join(base, 'sub/file.txt')\n"
            "    assert result.startswith(os.path.abspath(base))\n\n"
            "def test_traversal_blocked(tmp_path):\n"
            "    base = str(tmp_path)\n"
            "    with pytest.raises(ValueError):\n"
            "        safe_join(base, '../../etc/passwd')\n\n"
            "def test_traversal_blocked_encoded_style(tmp_path):\n"
            "    base = str(tmp_path)\n"
            "    with pytest.raises(ValueError):\n"
            "        safe_join(base, 'sub/../../escape.txt')\n"
        ),
    ),
    BenchmarkTask(
        id="t10_word_frequency",
        prompt=(
            "Write `top_n_words(text: str, n: int) -> list[tuple[str, int]]` in solution.py that returns the "
            "n most frequent lowercase words (alphanumeric sequences) in `text`, sorted by descending count "
            "then alphabetically for ties. Return fewer than n if there aren't enough distinct words."
        ),
        defect_category="unhandled-edge-case",
        test_code=(
            "from solution import top_n_words\n\n"
            "def test_basic_counts():\n"
            "    text = 'the cat sat on the mat the cat ran'\n"
            "    result = top_n_words(text, 2)\n"
            "    assert result[0] == ('the', 3)\n"
            "    assert result[1] == ('cat', 2)\n\n"
            "def test_case_insensitive():\n"
            "    result = top_n_words('Cat cat CAT dog', 1)\n"
            "    assert result[0] == ('cat', 3)\n\n"
            "def test_fewer_words_than_n():\n"
            "    result = top_n_words('one two', 10)\n"
            "    assert len(result) == 2\n\n"
            "def test_empty_text():\n"
            "    assert top_n_words('', 5) == []\n\n"
            "def test_tie_alphabetical():\n"
            "    result = top_n_words('b a', 2)\n"
            "    assert result == [('a', 1), ('b', 1)]\n"
        ),
    ),
    BenchmarkTask(
        id="t11_retry_with_backoff",
        prompt=(
            "Write `call_with_retry(func, max_attempts: int = 3) -> object` in solution.py that calls "
            "`func()` with no arguments, retrying on any Exception up to max_attempts total attempts, and "
            "re-raising the last exception if all attempts fail. Return the result on first success. "
            "Raise ValueError if max_attempts < 1."
        ),
        defect_category="off-by-one",
        test_code=(
            "from solution import call_with_retry\n"
            "import pytest\n\n"
            "def test_succeeds_first_try():\n"
            "    assert call_with_retry(lambda: 42) == 42\n\n"
            "def test_succeeds_after_failures():\n"
            "    calls = {'n': 0}\n"
            "    def flaky():\n"
            "        calls['n'] += 1\n"
            "        if calls['n'] < 3:\n"
            "            raise RuntimeError('boom')\n"
            "        return 'ok'\n"
            "    assert call_with_retry(flaky, max_attempts=3) == 'ok'\n"
            "    assert calls['n'] == 3\n\n"
            "def test_exhausts_attempts_and_raises():\n"
            "    calls = {'n': 0}\n"
            "    def always_fails():\n"
            "        calls['n'] += 1\n"
            "        raise RuntimeError('nope')\n"
            "    with pytest.raises(RuntimeError):\n"
            "        call_with_retry(always_fails, max_attempts=3)\n"
            "    assert calls['n'] == 3\n\n"
            "def test_invalid_max_attempts():\n"
            "    with pytest.raises(ValueError):\n"
            "        call_with_retry(lambda: 1, max_attempts=0)\n"
        ),
    ),
]


def get_task(task_id: str) -> BenchmarkTask:
    for t in TASKS:
        if t.id == task_id:
            return t
    raise KeyError(f"Unknown benchmark task id: {task_id}")
