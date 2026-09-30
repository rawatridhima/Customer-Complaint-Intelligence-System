"""Contract tests for the ML boundary.

These run in CI without torch, transformers, or the model files, so they
exercise the stub path. What they protect is the interface between the ML
side (ml/src) and the backend: text normalisation, the label vocabulary,
and the shape of what predict() returns.
"""

import pytest

from app.models.enums import Category, Sentiment
from app.services import classifier_service as cs
from label_mapping import CATEGORIES
from preprocess import light_clean, normalise


class TestNormalise:
    """normalise() must behave identically at training and inference time.
    Any change here invalidates the trained model (train-serve skew)."""

    def test_lowercases(self):
        assert normalise("EQUIFAX") == "equifax"

    def test_replaces_dates(self):
        assert "<date>" in normalise("on XX/XX/2018 I paid")
        assert "2018" not in normalise("on XX/XX/2018 I paid")

    def test_replaces_money(self):
        # The literal "00" from amounts was polluting the vocabulary.
        assert "<money>" in normalise("they charged me {$1,500.00}")
        assert "00" not in normalise("they charged me {$1,500.00}")

    def test_strips_cfpb_redactions(self):
        assert "x" not in normalise("paid to XXXX XXXX bank")

    def test_replaces_urls_and_long_numbers(self):
        assert "<url>" in normalise("see http://example.com/x")
        assert "<num>" in normalise("account 12345678")

    def test_collapses_whitespace(self):
        assert normalise("  a\n\n  b  ") == "a b"

    def test_is_idempotent(self):
        once = normalise("On XX/XX/2018 I paid {$50.00}")
        assert normalise(once) == once

    @pytest.mark.parametrize("text", ["", "   ", "\n"])
    def test_handles_empty_input(self, text):
        assert normalise(text) == ""


class TestLightClean:
    """Sentiment keeps case and punctuation: they carry emotional intensity."""

    def test_removes_redactions(self):
        assert "XXXX" not in light_clean("paid XXXX bank")

    def test_preserves_case_and_punctuation(self):
        assert light_clean("This is UNACCEPTABLE!!!") == "This is UNACCEPTABLE!!!"


class TestLabelVocabulary:
    """The training vocabulary and the backend enum must not drift apart.
    If they do, the model returns a string the backend cannot represent."""

    def test_training_categories_match_the_enum(self):
        assert set(CATEGORIES) == {c.value for c in Category}

    def test_every_training_label_constructs_a_category(self):
        for label in CATEGORIES:
            assert isinstance(Category(label), Category)

    def test_priority_engine_scores_every_category(self):
        from app.services.priority_service import PriorityService

        for category in Category:
            assert category in PriorityService.CATEGORY_SEVERITY


class TestClassifierContract:
    """The shape of predict() output, which the worker and API depend on."""

    @pytest.fixture
    def service(self):
        return cs.ClassifierService()

    def test_returns_a_classification_result(self, service):
        result = service.predict("my mortgage servicer will not release escrow")
        assert isinstance(result, cs.ClassificationResult)

    def test_category_is_a_valid_enum_member(self, service):
        assert service.predict("unauthorized hard inquiry").category in set(Category)

    def test_confidence_is_a_probability(self, service):
        assert 0.0 <= service.predict("a debt collector keeps calling").confidence <= 1.0

    def test_needs_review_follows_the_threshold(self, service):
        from app.core.config import settings

        result = service.predict("equifax is reporting an account that is not mine")
        assert result.needs_review == (result.confidence < settings.CONFIDENCE_THRESHOLD)

    def test_reports_its_version_and_latency(self, service):
        result = service.predict("my credit card was charged twice")
        assert result.model_version
        assert result.inference_ms >= 0


class TestSentimentContract:
    @pytest.fixture
    def service(self):
        return cs.SentimentService()

    def test_returns_a_sentiment_result(self, service):
        assert isinstance(service.predict("this is terrible"), cs.SentimentResult)

    def test_label_is_a_valid_enum_member(self, service):
        assert service.predict("thanks for the help").label in set(Sentiment)

    def test_score_is_a_probability(self, service):
        assert 0.0 <= service.predict("I am furious").score <= 1.0


class TestLazyLoading:
    """The API process imports this module only to enqueue work. Loading the
    models at import time would put ~1.5 GB into a process that never uses
    them, so loading must stay deferred until warm() or predict()."""

    def test_models_are_not_loaded_at_import_time(self):
        assert cs.classifier._impl is None
        assert cs.sentiment._impl is None

    def test_falls_back_to_the_stub_when_no_model_files_exist(self, tmp_path, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "MODEL_DIR", tmp_path)
        assert isinstance(cs._load_classifier(), cs.ClassifierService)