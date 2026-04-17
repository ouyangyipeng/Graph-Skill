"""Unit tests for QueryProcessor."""

import pytest

from graphskill.routing.query_processor import QueryProcessor


class TestQueryProcessor:
    """Tests for QueryProcessor."""

    def setup_method(self) -> None:
        self.processor = QueryProcessor()

    # ---- process() ----

    def test_process_basic_query(self) -> None:
        result = self.processor.process("I need to commit my changes to git")
        assert result.original == "I need to commit my changes to git"
        assert result.cleaned == "i need to commit my changes to git"
        assert "git" in result.intent_keywords

    def test_process_with_context(self) -> None:
        context = {
            "environment": {"git_repo": True},
            "previous_skills": ["git:config_user"],
        }
        result = self.processor.process("commit changes", context)
        assert "git repository" in result.enriched
        assert "git:config_user" in result.previous_skills

    def test_process_empty_context(self) -> None:
        result = self.processor.process("read a file")
        assert result.previous_skills == []
        assert result.environment == {}

    def test_process_none_context(self) -> None:
        result = self.processor.process("read a file", None)
        assert result.previous_skills == []

    # ---- _clean_text() ----

    def test_clean_text_whitespace(self) -> None:
        assert self.processor._clean_text("  hello   world  ") == "hello world"

    def test_clean_text_special_chars(self) -> None:
        result = self.processor._clean_text("hello! @world# $test%")
        assert "!" not in result
        assert "@" not in result
        assert "hello" in result
        assert "world" in result

    def test_clean_text_lowercase(self) -> None:
        result = self.processor._clean_text("Hello WORLD")
        assert result == "hello world"

    def test_clean_text_cjk_preserved(self) -> None:
        result = self.processor._clean_text("提交代码到仓库")
        assert "提交代码到仓库" in result

    def test_clean_text_mixed_cjk_english(self) -> None:
        result = self.processor._clean_text("使用 git commit 提交")
        assert "git" in result
        assert "提交" in result

    # ---- _enrich_with_context() ----

    def test_enrich_git_repo(self) -> None:
        result = self.processor._enrich_with_context(
            "commit changes", {"environment": {"git_repo": True}}
        )
        assert "git repository" in result

    def test_enrich_database(self) -> None:
        result = self.processor._enrich_with_context(
            "query data", {"environment": {"database_connected": True}}
        )
        assert "database" in result

    def test_enrich_multiple_env(self) -> None:
        result = self.processor._enrich_with_context(
            "deploy", {"environment": {"git_repo": True, "docker_available": True}}
        )
        assert "git repository" in result
        assert "docker" in result

    def test_enrich_no_env(self) -> None:
        result = self.processor._enrich_with_context("test", {})
        assert result == "test"

    # ---- _extract_intent_keywords() ----

    def test_intent_git(self) -> None:
        keywords = self.processor._extract_intent_keywords("commit and push to git")
        assert "git" in keywords

    def test_intent_database(self) -> None:
        keywords = self.processor._extract_intent_keywords("query the postgres database")
        assert "database" in keywords

    def test_intent_file(self) -> None:
        keywords = self.processor._extract_intent_keywords("read file from disk")
        assert "file" in keywords

    def test_intent_network(self) -> None:
        keywords = self.processor._extract_intent_keywords("fetch data from http api")
        assert "network" in keywords

    def test_intent_docker(self) -> None:
        keywords = self.processor._extract_intent_keywords("build docker container")
        assert "docker" in keywords

    def test_intent_test(self) -> None:
        keywords = self.processor._extract_intent_keywords("run pytest with coverage")
        assert "test" in keywords

    def test_intent_multiple(self) -> None:
        keywords = self.processor._extract_intent_keywords(
            "commit to git and deploy to docker"
        )
        assert "git" in keywords
        assert "docker" in keywords

    def test_intent_no_match(self) -> None:
        keywords = self.processor._extract_intent_keywords("random text about nothing")
        assert keywords == []

    def test_intent_no_duplicate_categories(self) -> None:
        keywords = self.processor._extract_intent_keywords("git commit git push git pull")
        # Should only have "git" once
        assert keywords.count("git") == 1
