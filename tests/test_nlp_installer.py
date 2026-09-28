from mobilitik.nlp_installer import CPU_TORCH_INDEX, TRANSFORMERS_SPEC, install_commands


def test_nlp_install_commands_use_cpu_torch_and_transformers():
    commands = install_commands("python-test")
    assert commands[0][:4] == ["python-test", "-m", "pip", "install"]
    assert "torch" in commands[0]
    assert CPU_TORCH_INDEX in commands[0]
    assert commands[1][:4] == ["python-test", "-m", "pip", "install"]
    assert TRANSFORMERS_SPEC in commands[1]
