from app.application.use_cases.generate_technical_document import GenerateTechnicalDocumentUseCase


def test_empty_or_whitespace_settings_prompt_leaves_existing_prompt_unchanged():
    original_prompt = "Existing BRD instructions.\nRepository evidence."

    for value in (None, "", "     "):
        assert GenerateTechnicalDocumentUseCase._append_optional_settings_prompt(
            original_prompt, value
        ) == original_prompt


def test_settings_prompt_is_additive_to_existing_instructions_and_evidence():
    original_prompt = "Existing BRD instructions.\nRepository evidence."
    setting_prompt = "Focus on authentication, authorization and user roles."

    result = GenerateTechnicalDocumentUseCase._append_optional_settings_prompt(
        original_prompt, setting_prompt
    )

    assert result.startswith(original_prompt)
    assert f"OPTIONAL USER SETTINGS FOCUS (supplemental instructions):\n{setting_prompt}" in result
    assert "Repository evidence controls factual claims" in result
