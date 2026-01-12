"""Tests for task creation."""

from specieval.tasks import attitude_meat, attitude_seafood, sentience, speciesism
from specieval.translations import Language


def test_speciesism_task_creation():
    """Test that the speciesism task can be created."""
    task = speciesism()

    assert task is not None
    assert task.dataset is not None
    assert len(task.dataset) == 4  # 4 speciesism questions
    assert task.scorer is not None
    assert "speciesism_en" in task.name


def test_speciesism_task_with_language():
    """Test speciesism task with different language."""
    task = speciesism(language=Language.GERMAN)

    assert "speciesism_de" in task.name
    assert task.dataset is not None


def test_speciesism_task_with_string_language():
    """Test speciesism task accepts language as string."""
    task = speciesism(language="fr")

    assert "speciesism_fr" in task.name


def test_sentience_task_creation():
    """Test that the sentience task can be created."""
    task = sentience()

    assert task is not None
    assert task.dataset is not None
    assert len(task.dataset) == 6  # 6 sentience questions
    assert "sentience_en" in task.name


def test_attitude_meat_task_creation():
    """Test that the attitude meat task can be created."""
    task = attitude_meat()

    assert task is not None
    assert task.dataset is not None
    assert len(task.dataset) == 4  # 4 questions
    assert "attitude_meat_en" in task.name


def test_attitude_seafood_task_creation():
    """Test that the attitude seafood task can be created."""
    task = attitude_seafood()

    assert task is not None
    assert task.dataset is not None
    assert len(task.dataset) == 4  # 4 questions
    assert "attitude_seafood_en" in task.name


def test_task_samples_have_required_fields():
    """Test that all task samples have required fields."""
    task = speciesism()

    for sample in task.dataset:
        assert sample.id is not None
        assert sample.input is not None
        assert len(sample.input) > 0
        assert sample.metadata is not None
        assert "levels" in sample.metadata
        assert sample.metadata["levels"] == 7


def test_task_with_reverse_scoring():
    """Test that reverse scoring parameter is passed to samples."""
    task = speciesism(reverse=True)

    for sample in task.dataset:
        assert sample.metadata.get("reverse") is True


def test_task_epochs_parameter():
    """Test that epochs parameter is respected."""
    task = speciesism(epochs=5)

    assert task.epochs is not None


def test_all_tasks_in_all_languages():
    """Test that all tasks can be created in all languages."""
    tasks = [speciesism, sentience, attitude_meat, attitude_seafood]

    for task_fn in tasks:
        for lang in Language:
            task = task_fn(language=lang)
            assert task is not None
            assert task.dataset is not None
            assert len(task.dataset) > 0
