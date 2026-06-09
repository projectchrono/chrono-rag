import os
import subprocess
from unittest.mock import patch
from src.preprocess.dataparser import Document, clone_repo, walk_path

def test_document_defaults():
    doc = Document(
        content="hello",
        source_repo="chrono",
        file_path="src/foo.py",
        language="py",
        chunk_type="function",
        chunk_name="my_func",
    )
    assert doc.content == "hello"
    assert doc.embedding == []

def test_document_answer_defaults_to_empty_string():
    doc = Document(
        content="hello",
        source_repo="chrono",
        file_path="src/foo.py",
        language="py",
        chunk_type="function",
        chunk_name="my_func",
    )
    assert doc.answer == ""

def test_clone_repo_skips_if_exists(tmp_path):
    dest = str(tmp_path / "existing")
    os.makedirs(dest)
    with patch("subprocess.run") as mock_run:
        clone_repo("https://github.com/example/repo", dest)
        mock_run.assert_not_called()

def test_clone_repo_calls_git_clone(tmp_path):
    dest = str(tmp_path / "new_repo")
    with patch("subprocess.run") as mock_run:
        clone_repo("https://github.com/example/repo", dest)
        mock_run.assert_called_once_with(
            ["git", "clone", "--depth", "1",
             "https://github.com/example/repo", dest],
            check=True,
        )

def test_walk_path_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text("x = 1")
    (tmp_path / "top.h").write_text("// header")

    files = list(walk_path(str(tmp_path), "", recursive=True))
    assert any("deep.py" in f for f in files)
    assert any("top.h" in f for f in files)

def test_walk_path_non_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("x = 1")
    (tmp_path / "top.py").write_text("y = 2")

    files = list(walk_path(str(tmp_path), "", recursive=False))
    assert any("top.py" in f for f in files)
    assert not any("nested.py" in f for f in files)

def test_walk_path_filters_unsupported_extensions(tmp_path):
    (tmp_path / "code.py").write_text("x = 1")
    (tmp_path / "data.csv").write_text("a,b,c")

    files = list(walk_path(str(tmp_path), "", recursive=False))
    assert any("code.py" in f for f in files)
    assert not any("data.csv" in f for f in files)

def test_walk_path_returns_empty_for_missing_path(tmp_path):
    files = list(walk_path(str(tmp_path), "nonexistent/subdir", recursive=True))
    assert files == []

from src.preprocess.dataparser import chunk_python_file

_SAMPLE_PYTHON = """
import os
import sys

class MyClass:
    def method(self):
        pass

def standalone_function():
    return 42
"""

def test_chunk_python_extracts_class():
    docs = chunk_python_file(_SAMPLE_PYTHON, "test.py", "chrono")
    class_chunks = [d for d in docs if d.chunk_type == "class"]
    assert len(class_chunks) == 1
    assert class_chunks[0].chunk_name == "MyClass"
    assert "class MyClass" in class_chunks[0].content

def test_chunk_python_extracts_function():
    docs = chunk_python_file(_SAMPLE_PYTHON, "test.py", "chrono")
    func_chunks = [d for d in docs if d.chunk_name == "standalone_function"]
    assert len(func_chunks) == 1
    assert "def standalone_function" in func_chunks[0].content

def test_chunk_python_prepends_imports():
    docs = chunk_python_file(_SAMPLE_PYTHON, "test.py", "chrono")
    for doc in docs:
        assert "import os" in doc.content

def test_chunk_python_sets_metadata():
    docs = chunk_python_file(_SAMPLE_PYTHON, "myfile.py", "chrono")
    for doc in docs:
        assert doc.source_repo == "chrono"
        assert doc.file_path == "myfile.py"
        assert doc.language == "py"

def test_chunk_python_fallback_on_syntax_error():
    docs = chunk_python_file("this is not valid python !!!", "bad.py", "chrono")
    assert len(docs) == 1
    assert docs[0].chunk_type == "file"

def test_chunk_python_fallback_on_empty_file():
    docs = chunk_python_file("# just a comment\n", "empty.py", "chrono")
    assert len(docs) == 1
    assert docs[0].chunk_type == "file"

from src.preprocess.dataparser import chunk_cpp_file

_SAMPLE_HEADER = """\
#pragma once

class ChDoubleWishbone : public ChSuspension {
public:
    void Initialize();
    double GetSpindlePos() const;
};

struct WishboneData {
    double mass;
};
"""

_SAMPLE_CPP = """\
#include "ChDoubleWishbone.h"

void ChDoubleWishbone::Initialize(std::shared_ptr<ChChassis> chassis) {
    // implementation
}

double ChDoubleWishbone::GetSpindlePos() const {
    return 0.0;
}
"""

def test_chunk_cpp_header_extracts_class():
    docs = chunk_cpp_file(_SAMPLE_HEADER, "ChDoubleWishbone.h", "chrono")
    names = [d.chunk_name for d in docs if d.chunk_type == "class"]
    assert "ChDoubleWishbone" in names

def test_chunk_cpp_header_extracts_struct():
    docs = chunk_cpp_file(_SAMPLE_HEADER, "ChDoubleWishbone.h", "chrono")
    names = [d.chunk_name for d in docs if d.chunk_type == "class"]
    assert "WishboneData" in names

def test_chunk_cpp_source_extracts_methods():
    docs = chunk_cpp_file(_SAMPLE_CPP, "ChDoubleWishbone.cpp", "chrono")
    names = [d.chunk_name for d in docs if d.chunk_type == "function"]
    assert any("Initialize" in n for n in names)
    assert any("GetSpindlePos" in n for n in names)

def test_chunk_cpp_fallback_on_no_match():
    content = "// just comments\n#define FOO 1\n"
    docs = chunk_cpp_file(content, "macros.h", "chrono")
    assert len(docs) == 1
    assert docs[0].chunk_type == "file"

def test_chunk_cpp_sets_language():
    docs = chunk_cpp_file(_SAMPLE_HEADER, "foo.h", "chrono")
    for doc in docs:
        assert doc.language == "cpp"

from src.preprocess.dataparser import chunk_json_file, parse_file

def test_chunk_json_returns_single_document():
    content = '{"type": "Vehicle", "mass": 1000}'
    docs = chunk_json_file(content, "hmmwv.json", "chrono")
    assert len(docs) == 1
    assert docs[0].language == "json"
    assert docs[0].chunk_type == "file"
    assert docs[0].chunk_name == "hmmwv.json"
    assert docs[0].content == content

def test_parse_file_dispatches_python(tmp_path):
    f = tmp_path / "demo.py"
    f.write_text("def foo():\n    pass\n")
    docs = parse_file(str(f), "demo.py", "pychrono-examples")
    assert all(d.language == "py" for d in docs)

def test_parse_file_dispatches_cpp(tmp_path):
    f = tmp_path / "Widget.h"
    f.write_text("class Widget {\n};\n")
    docs = parse_file(str(f), "Widget.h", "chrono")
    assert all(d.language == "cpp" for d in docs)

def test_parse_file_dispatches_json(tmp_path):
    f = tmp_path / "spec.json"
    f.write_text('{"key": "value"}')
    docs = parse_file(str(f), "spec.json", "chrono")
    assert len(docs) == 1
    assert docs[0].language == "json"

def test_parse_file_returns_empty_for_unrecognized(tmp_path):
    f = tmp_path / "readme.md"
    f.write_text("# Hello")
    docs = parse_file(str(f), "readme.md", "chrono")
    assert docs == []

from unittest.mock import patch, call
from src.preprocess.dataparser import parse_repos

def test_parse_repos_clones_both_repos(tmp_path):
    repos_dir = str(tmp_path)

    with patch("src.preprocess.dataparser.clone_repo") as mock_clone, \
         patch("src.preprocess.dataparser.walk_path", return_value=iter([])):
        list(parse_repos(repos_dir))

    urls = [c.args[0] for c in mock_clone.call_args_list]
    assert any("projectchrono/chrono" in u for u in urls)
    assert any("pychrono-examples" in u for u in urls)

def test_parse_repos_yields_documents(tmp_path):
    repos_dir = str(tmp_path)
    fake_file = tmp_path / "chrono" / "demo.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text("def hello():\n    pass\n")

    with patch("src.preprocess.dataparser.clone_repo"):
        def fake_walk(base, rel, recursive):
            if "chrono" in base and rel == "src/chrono_vehicle/wheeled_vehicle/suspension":
                yield str(fake_file)

        with patch("src.preprocess.dataparser.walk_path", side_effect=fake_walk):
            docs = list(parse_repos(repos_dir))

    assert len(docs) >= 1
    assert all(hasattr(d, "content") for d in docs)

from src.preprocess.dataparser import parse_example_pair

def test_parse_example_pair_content_is_prompt(tmp_path):
    inp = tmp_path / "input1.txt"
    truth = tmp_path / "truth1.py"
    inp.write_text("Develop a beam buckling simulation.")
    truth.write_text("import pychrono as chrono\n")

    doc = parse_example_pair(str(inp), str(truth))

    assert doc.content == "Develop a beam buckling simulation."


def test_parse_example_pair_answer_is_code(tmp_path):
    inp = tmp_path / "input1.txt"
    truth = tmp_path / "truth1.py"
    inp.write_text("Develop a beam buckling simulation.")
    truth.write_text("import pychrono as chrono\n")

    doc = parse_example_pair(str(inp), str(truth))

    assert doc.answer == "import pychrono as chrono\n"


def test_parse_example_pair_metadata(tmp_path):
    inp = tmp_path / "input1.txt"
    truth = tmp_path / "truth1.py"
    inp.write_text("Some prompt.")
    truth.write_text("x = 1\n")

    doc = parse_example_pair(str(inp), str(truth))

    assert doc.source_repo == "example"
    assert doc.language == "text"
    assert doc.chunk_type == "example"
    assert doc.chunk_name == "input1.txt"
    assert doc.file_path == str(inp)


from src.preprocess.dataparser import parse_example_pairs

def test_parse_example_pairs_returns_one_doc_per_pair(tmp_path):
    pairs = []
    for i in range(3):
        inp = tmp_path / f"input{i}.txt"
        truth = tmp_path / f"truth{i}.py"
        inp.write_text(f"Prompt {i}")
        truth.write_text(f"code_{i} = True\n")
        pairs.append((str(inp), str(truth)))

    docs = parse_example_pairs(pairs)

    assert len(docs) == 3
    assert docs[0].content == "Prompt 0"
    assert docs[2].answer == "code_2 = True\n"
