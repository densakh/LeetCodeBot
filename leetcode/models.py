from dataclasses import dataclass, field


@dataclass
class CodeSnippet:
    lang: str
    lang_slug: str
    code: str


@dataclass
class Problem:
    question_id: str
    frontend_id: str
    title: str
    title_slug: str
    difficulty: str
    content: str
    topic_tags: list[str] = field(default_factory=list)
    code_snippets: list[CodeSnippet] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    sample_test_case: str = ""


@dataclass
class SubmissionResult:
    status_code: int
    runtime_display: str = ""
    runtime_percentile: float = 0.0
    memory_display: str = ""
    memory_percentile: float = 0.0
    total_correct: int = 0
    total_testcases: int = 0
    expected_output: str = ""
    code_output: str = ""
    compile_error: str = ""
    runtime_error: str = ""
    is_pending: bool = False
