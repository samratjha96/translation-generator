import os
import re
import pytest
import shutil
import subprocess
import yaml
import json

translator = os.path.abspath("../translator")

def run_translator(path, args):
    return subprocess.run([translator, *args],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          encoding="utf-8",
                          errors="utf-8",
                          cwd = path)

def generate(path):
    return run_translator(path, ["--generate"])

def generate_with_config(path, file):
    return run_translator(path, ["--generate", "--config", file])

key_error_cases = [
    ("bundle_key_error"),
    ("extension_key_error"),
    ("path_key_error")
]

@pytest.mark.parametrize("file", key_error_cases)
def test_bad_keys(file):
    test_data_path = "data/configuration/bad_config_keys/"
    output = generate_with_config(test_data_path, f"{file}.yml")
    assert 0 != output.returncode
    with open(f"{test_data_path}{file}.stderr", "r") as file:
        assert output.stderr.strip() == file.read().strip()

def test_no_default_locale():
    test_data_path = "data/configuration/bad_configuration"
    output = generate_with_config(test_data_path, "no_default_locale.yml")
    assert 0 != output.returncode
    std_err_regex = re.compile("Bundle: Expected default locale file to match regex .*_en_US but no files in .* matched")
    assert std_err_regex.match(output.stderr.strip()) is not None

bad_configuration_cases = [
    ("no_bundles_in_path"),
    ("invalid_extension")
]
@pytest.mark.parametrize("file", bad_configuration_cases)
def test_bad_configuration(file):
    test_data_path = "data/configuration/bad_configuration/"
    output = generate_with_config(test_data_path, f"{file}.yml")
    assert 0 != output.returncode
    std_err_regex = re.compile("Validator: no .* file found in.*")
    assert std_err_regex.match(output.stderr.strip()) is not None

def test_bad_config_file():
    config_file = "hi.yml"
    output = generate_with_config(".", config_file)
    assert 0 != output.returncode
    assert output.stderr.strip() == "translator: Configuration file hi.yml not found"
