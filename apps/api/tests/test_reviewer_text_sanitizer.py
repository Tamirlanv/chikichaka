from invision_api.commission.application.reviewer_text_sanitizer import centered_keyword_snippet


def test_centered_keyword_snippet_centers_on_marker() -> None:
    text = (
        "В начале кандидат описывает контекст, а затем подробно объясняет, как самостоятельно "
        "запустил школьный проект и организовал работу команды, после чего подвёл итоги и описал рост."
    )
    out = centered_keyword_snippet(text, ("запустил", "организ"), max_chars=90)
    assert "запустил" in out
    idx = out.lower().find("запустил")
    assert idx > 10
    assert idx < len(out) - 20


def test_centered_keyword_snippet_falls_back_when_marker_absent() -> None:
    text = "Это длинный текст без целевых маркеров, который должен быть аккуратно сокращён в начале."
    out = centered_keyword_snippet(text, ("инициатив",), max_chars=50)
    assert out.endswith("...")
    assert "инициатив" not in out.lower()
