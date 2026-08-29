# CLAUDE.md

정본 문서는 `AGENTS.md`(작업 규칙)와 `README.md`(사용법)다. 구조적 의사결정은
`docs/decisions.md`, 최근 변경은 `CHANGELOG.md`를 참고한다.

품질 게이트는 `AGENTS.md`의 검증 섹션을 그대로 따른다
(`poetry run pytest`, `poetry run pytest -m live`, `poetry run ruff check src tests`,
`poetry run mypy src`).
