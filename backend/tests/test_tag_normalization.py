"""
Tests for tag generation and normalization.
"""
import pytest
from app.services.tag_generator import (
    _normalize_tag, 
    _is_valid_tag, 
    generate_tags,
    detect_language,
    extract_korean_keywords,
    extract_tech_terms,
    deduplicate_similar_tags,
)


class TestDetectLanguage:
    """Tests for detect_language function."""

    def test_korean_text(self):
        """Korean text should be detected as 'ko'."""
        assert detect_language("파이썬으로 배우는 머신러닝") == "ko"
        assert detect_language("안녕하세요 반갑습니다") == "ko"

    def test_english_text(self):
        """English text should be detected as 'en'."""
        assert detect_language("Introduction to Machine Learning") == "en"
        assert detect_language("Hello World") == "en"

    def test_mixed_text(self):
        """Mixed text should be detected based on ratio."""
        # More Korean
        assert detect_language("파이썬 Python 머신러닝 튜토리얼") == "ko"
        # More English
        assert detect_language("Python Machine Learning Tutorial 입문") == "en"

    def test_empty_text(self):
        """Empty text should default to 'en'."""
        assert detect_language("") == "en"


class TestNormalizeTag:
    """Tests for _normalize_tag function."""

    def test_lowercase_english(self):
        """English tags should be lowercased."""
        assert _normalize_tag("Python") == "python"
        assert _normalize_tag("MACHINE LEARNING") == "machine_learning"

    def test_korean_preserved(self):
        """Korean characters should be preserved as-is."""
        assert _normalize_tag("파이썬", "ko") == "파이썬"
        assert _normalize_tag("머신러닝", "ko") == "머신러닝"

    def test_mixed_korean_english(self):
        """Mixed Korean/English should work."""
        assert _normalize_tag("Python 튜토리얼", "ko") == "python_튜토리얼"

    def test_whitespace_to_underscore(self):
        """Whitespace should become underscores."""
        assert _normalize_tag("machine learning") == "machine_learning"
        assert _normalize_tag("deep  learning") == "deep_learning"

    def test_special_chars_removed(self):
        """Special characters should be removed."""
        # "C++" becomes "c" which is too short, so returns None
        assert _normalize_tag("C++") is None
        assert _normalize_tag("node.js") == "nodejs"
        assert _normalize_tag("re:invent") == "reinvent"

    def test_underscore_preserved(self):
        """Existing underscores should be preserved."""
        assert _normalize_tag("machine_learning") == "machine_learning"

    def test_length_constraints_english(self):
        """English tags outside length limits should return None."""
        # Too short
        assert _normalize_tag("a") is None
        assert _normalize_tag("") is None
        
        # Too long
        assert _normalize_tag("a" * 25) is None
        
        # Just right
        assert _normalize_tag("ab") == "ab"
        assert _normalize_tag("a" * 24) == "a" * 24

    def test_length_constraints_korean(self):
        """Korean single character nouns should be allowed."""
        # Single Korean character is allowed for Korean language
        assert _normalize_tag("앱", "ko") == "앱"
        assert _normalize_tag("웹", "ko") == "웹"

    def test_strips_surrounding_underscores(self):
        """Leading/trailing underscores should be stripped."""
        assert _normalize_tag("_python_") == "python"
        assert _normalize_tag("__test__") == "test"


class TestIsValidTag:
    """Tests for _is_valid_tag function."""

    def test_stopwords_rejected(self):
        """Stopwords should be rejected."""
        assert _is_valid_tag("the") is False
        assert _is_valid_tag("and") is False
        assert _is_valid_tag("은") is False
        assert _is_valid_tag("는") is False

    def test_valid_tags_accepted(self):
        """Valid tags should be accepted."""
        assert _is_valid_tag("python") is True
        assert _is_valid_tag("machine_learning") is True
        assert _is_valid_tag("파이썬") is True

    def test_mostly_numbers_rejected(self):
        """Tags that are mostly numbers should be rejected."""
        assert _is_valid_tag("12345") is False
        # "123abc" has 50% letters (3/6), which is above 30% threshold
        assert _is_valid_tag("123abc") is True
        # "1234ab" has 33% letters, just above threshold
        assert _is_valid_tag("1234ab") is True
        # "12345a" has ~17% letters, below threshold
        assert _is_valid_tag("12345a") is False
        
        # Regular alphanumeric tags are okay
        assert _is_valid_tag("python3") is True
        assert _is_valid_tag("web2") is True


class TestExtractKoreanKeywords:
    """Tests for extract_korean_keywords function."""

    def test_basic_extraction(self):
        """Should extract nouns from Korean text."""
        text = "파이썬으로 머신러닝을 배우는 튜토리얼입니다"
        keywords = extract_korean_keywords(text)
        
        assert len(keywords) > 0
        # Should contain main nouns
        assert "파이썬" in keywords or "머신러닝" in keywords or "튜토리얼" in keywords

    def test_empty_text(self):
        """Empty text should return empty list."""
        assert extract_korean_keywords("") == []
        assert extract_korean_keywords("짧음") == []

    def test_extracts_proper_nouns(self):
        """Should extract proper nouns (company names, etc.)."""
        text = "OpenAI와 Anthropic은 AI 기업입니다"
        keywords = extract_korean_keywords(text)
        
        # Should extract foreign words
        assert any("OpenAI" in k or "Anthropic" in k for k in keywords) or "기업" in keywords


class TestExtractTechTerms:
    """Tests for extract_tech_terms function."""

    def test_english_tech_terms(self):
        """Should extract English tech terms."""
        text = "OpenAI released GPT-4 which uses advanced AI and ML techniques"
        terms = extract_tech_terms(text)
        
        assert "AI" in terms
        assert "ML" in terms
        assert "OpenAI" in terms

    def test_korean_tech_terms(self):
        """Should extract Korean tech terms."""
        text = "인공지능과 머신러닝을 활용한 클라우드 인프라"
        terms = extract_tech_terms(text)
        
        assert "인공지능" in terms
        assert "머신러닝" in terms
        assert "클라우드" in terms
        assert "인프라" in terms

    def test_case_insensitive(self):
        """English terms should be case-insensitive."""
        text = "nvidia gpu is used for ai training"
        terms = extract_tech_terms(text)
        
        assert "NVIDIA" in terms
        assert "GPU" in terms
        assert "AI" in terms
        assert "Training" in terms


class TestDeduplicateSimilarTags:
    """Tests for deduplicate_similar_tags function."""

    def test_removes_korean_suffix_variants(self):
        """Should remove Korean suffix variants."""
        tags = ["카테고리", "카테고리의", "카테고리에"]
        result = deduplicate_similar_tags(tags)
        
        # Should only keep one
        assert len(result) == 1

    def test_keeps_different_tags(self):
        """Should keep different tags."""
        tags = ["python", "javascript", "rust"]
        result = deduplicate_similar_tags(tags)
        
        assert len(result) == 3

    def test_handles_empty_list(self):
        """Should handle empty list."""
        assert deduplicate_similar_tags([]) == []

    def test_handles_single_item(self):
        """Should handle single item."""
        assert deduplicate_similar_tags(["python"]) == ["python"]


class TestGenerateTags:
    """Tests for generate_tags function."""

    def test_basic_tag_generation(self):
        """Basic tag generation from title and text."""
        title = "Introduction to Machine Learning with Python"
        text = "This tutorial covers the basics of machine learning using Python and scikit-learn library."
        
        tags = generate_tags(title=title, text=text)
        
        assert len(tags) > 0
        assert len(tags) <= 15
        # Should have some relevant tags
        assert any("python" in t or "machine" in t or "learning" in t for t in tags)

    def test_korean_tag_generation(self):
        """Korean content should generate Korean tags."""
        title = "파이썬으로 배우는 머신러닝 입문"
        text = "이 튜토리얼에서는 파이썬과 사이킷런을 사용하여 머신러닝의 기초를 다룹니다."
        
        tags = generate_tags(title=title, text=text)
        
        assert len(tags) > 0
        # Should contain Korean keywords
        assert any(any('\uac00' <= c <= '\ud7a3' for c in t) for t in tags)

    def test_tech_terms_prioritized(self):
        """Tech terms should be extracted and prioritized."""
        title = "OpenAI GPT-4 and AI Trends"
        text = "This article discusses OpenAI's GPT-4 model and AI industry trends."
        
        tags = generate_tags(title=title, text=text)
        
        # Should have tech terms
        assert any(t.lower() in ["ai", "openai", "gpt"] for t in tags)

    def test_empty_content(self):
        """Empty content should return empty tags."""
        tags = generate_tags(title="", text="")
        assert tags == []

    def test_very_short_content(self):
        """Very short content should return empty tags."""
        tags = generate_tags(title="Hi", text="")
        assert tags == []

    def test_no_duplicate_tags(self):
        """Generated tags should not have duplicates."""
        title = "Python Python Python Machine Learning Learning"
        text = "Python tutorial for machine learning with Python."
        
        tags = generate_tags(title=title, text=text)
        
        # No duplicates (case-insensitive)
        lower_tags = [t.lower() for t in tags]
        assert len(lower_tags) == len(set(lower_tags))

    def test_mad_landscape_content(self):
        """Should generate meaningful tags for MAD Landscape article."""
        title = "2025년 MAD (ML, AI, Data) 업계 지도"
        text = """
        이미지 한장으로 정리한 2025년 MAD 업계 지도 : Bubble & Build 및 올해의 25가지 테마 설명
        2025년 AI·데이터 시장은 과열된 투자와 실제 배포의 병존 속에서, 
        챗봇 중심에서 도구·메모리·추론 모델을 갖춘 에이전트 시스템으로 전환 중
        NVIDIA, Databricks, OpenAI 등 하이퍼 스케일러와 카테고리 리더의 비중을 확대
        새로 에이전트 스택과 로컬 AI(온디바이스 LLM) 섹션을 추가
        """
        
        tags = generate_tags(title=title, text=text)
        
        assert len(tags) > 0
        # Should have meaningful tech terms, not garbage n-grams
        tag_str = " ".join(tags).lower()
        assert any(term in tag_str for term in ["ai", "ml", "data", "nvidia", "openai", "에이전트"])
        
        # Should NOT have meaningless combinations
        assert not any("지형도는" in t for t in tags)
        assert not any("한장으로" in t for t in tags)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
