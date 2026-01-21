# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Providing LLM generations function.

# Resources:

ollama-python doc: https://github.com/ollama/ollama-python

chat completion doc:
https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion

list of valid options:
https://github.com/ollama/ollama/blob/main/docs/modelfile.md#valid-parameters-and-values

WARNING: do not confuse parameters and options.
parameters are arguments of Client.chat or Client.generate
option is a dict of advanced options, given a parameter

You can find examples in `tests/`
"""

import configparser
from collections.abc import Sequence
from pathlib import Path
from time import sleep

import ollama
import pydantic

from ali.ui.logger import LOGGER_LLM

N_RETRIES = 5  # Retry when ollama service is unaccessible / return an error


class ModelNotFoundError(Exception):
    """Exception raised when a model is not available on the Ollama server."""


def read_config(config_file: str | Path) -> dict:
    """Read the ini config.

    Args:
        config_file (str | Path): path to ini file.

    Returns:
        dict: dictionary with parameters.
    """

    def is_floatable(value: float | str) -> bool:
        try:
            float(value)
            return True
        except ValueError:
            return False

    config = configparser.ConfigParser()
    config.read(config_file)

    config_dict: dict[str, int | float | str | bool | None] = {}

    for section in config.sections():
        # config_dict[section] = {}
        for key, value in config.items(section):
            if value.isdigit():
                config_dict[key] = int(value)
            elif is_floatable(value):
                config_dict[key] = float(value)
            elif value.lower() in {"yes", "no"}:
                config_dict[key] = config.getboolean(section, key)
            elif value == "":
                config_dict[key] = None
            else:
                config_dict[key] = value

    return config_dict


CONFIG_FILE = Path(__file__).parents[3] / "config.ini"
if not CONFIG_FILE.exists():
    raise FileNotFoundError(f"LLM Config not found: {CONFIG_FILE}")


CONFIG_DICT = read_config(CONFIG_FILE)
_config_dict_tmp = CONFIG_DICT.copy()  # temporary config to check for unused keys


class OllamaOptions(ollama.Options):
    """A simple wrapper to control Ollama options."""

    def __init__(
        self,
        **kwargs: bool | float | str | Sequence[str] | None,
    ) -> None:
        for key, value in kwargs.items():
            if (
                isinstance(value, int)
                and ollama.Options.__annotations__.get(key) is float
            ):
                LOGGER_LLM.debug(
                    f"Changing type int to float for option {key}: {value}",
                )
                kwargs[key] = float(value)

            if key not in ollama.Options.__annotations__:
                raise KeyError(f"Key `{key}` is not a valid Ollama Option")

        try:
            super().__init__(**kwargs)
        except pydantic.ValidationError as e:
            LOGGER_LLM.warning(
                f'Wrong type in ollama option: "{key}" must be \
                    {ollama.Options.__annotations__.get(key)}, \
                        not {value} of type {type(value)}.\n\
                        Pydantic error:\n\
                            {e}',
            )
            raise


class MockedClient:
    """A mocked LLM client for debug and tests.

    It contains the `chat` and `generate` functions,
    with similar signature as the real client.

    Raises:
        TypeError: for incorrect argument type.
    """

    answer = "This is an answer"

    def chat(
        self, model: str, messages: list[ollama.Message], options: OllamaOptions
    ) -> dict:
        """Mocked chat generation.

        Args:
            model (str): cf. ollama.client
            messages (list[ollama.Message]): cf. ollama.client
            options (OllamaOptions): cf. ollama.client

        Raises:
            TypeError: for incorrect argument type.

        Returns:
            dict: cf. ollama.client
        """
        if not isinstance(model, str):
            raise TypeError("Model must be a str.")

        if not isinstance(messages, list):
            raise TypeError(
                f"messages must be a list of ollama messages. \
                            Received `{messages}` of type {type(messages).__name__}"
            )
        for m in messages:
            if not isinstance(m, ollama.Message):
                raise TypeError(
                    f"messages must be a list of ollama messages. \
                            Received `{m}` of type {type(m).__name__}"
                )

        if not isinstance(options, OllamaOptions):
            raise TypeError(
                f"options must be of type ollama.Options. \
                            Received `{options}` of type {type(options).__name__}"
            )

        return {"message": {"content": self.answer}}

    def generate(self, model: str, prompt: str, options: OllamaOptions) -> dict:
        """Mocked generation.

        Args:
            model (str): cf. ollama.client
            prompt (list[ollama.Message]): cf. ollama.client
            options (OllamaOptions): cf. ollama.client

        Raises:
            TypeError: for incorrect argument type.

        Returns:
            dict: cf. ollama.client
        """
        if not isinstance(model, str):
            raise TypeError("Model must be a str.")

        if not isinstance(prompt, str):
            raise TypeError(
                f"prompt must be a str. \
                            Received `{prompt}` of type {type(prompt).__name__}"
            )

        if not isinstance(options, ollama.Options):
            raise TypeError(
                f"options must be of type ollama.Options. \
                            Received `{options}` of type {type(options).__name__}"
            )

        return {"response": self.answer}


CLIENT = ollama.Client(host=_config_dict_tmp.pop("ollama_ip"))
MODEL = _config_dict_tmp.pop("ollama_model")

# check if MODEL is in the list of available models on the ollama server.
try:
    if not any(MODEL == m.model for m in ollama.list().models):
        raise ModelNotFoundError(
            f"Model '{MODEL}' is not available on the ollama server. "
            f"List of available models:"
            f"{[m.model for m in ollama.list().models]}"
            f"\nYou can either change the `ollama_model` value in `config.ini` "
            f"for one of the available models. "
            f"Or execute `ollama pull {MODEL}` to add the model to your ollama server."
        )
except ConnectionError:
    LOGGER_LLM.error("It looks like your ollama server is not reachable.")


# ollama default generation options
options = {
    "temperature": 0.5,
    "top_p": 0.5,
}

# updating options from config file
for key in ["seed", "temperature", "top_p"]:
    value = _config_dict_tmp.pop(key, None)
    if value is not None:
        options[key] = value

ollama_options = OllamaOptions(**options)


if len(_config_dict_tmp) > 0:
    LOGGER_LLM.warning(
        f"The following items from config are ignored: {_config_dict_tmp.keys()}",
    )

LOGGER_LLM.info("Ollama options: " + str(ollama_options.model_dump()))


def chat(
    messages: list[ollama.Message],
    options: OllamaOptions = ollama_options,
) -> dict:
    """LLM generation as chat.

    Args:
        messages (dict): list of chat messages history.
        options (OllamaOptions, optional): Ollama options. Defaults to default_options.

    Returns:
        dict: with key `sequences` containing generated sequences from the LLM
    """
    assert isinstance(options, OllamaOptions)
    for attempt in range(N_RETRIES):
        try:
            response = CLIENT.chat(model=MODEL, messages=messages, options=options)
            return {"sequences": [response.get("message").get("content")]}
        except (
            ollama.ResponseError,
            pydantic.ValidationError,
            TypeError,
            ValueError,
        ) as e:
            LOGGER_LLM.debug(
                f"Failed to get response due to error \
                    (retry {attempt}/{N_RETRIES}): {e}",
            )
            sleep(min(0.1 + attempt, 5))

    LOGGER_LLM.warning(
        f"Failed to get response after {N_RETRIES} attempts. \
            See debug logs for details.",
    )
    return {"sequences": [""]}


def generate(prompt: str, options: OllamaOptions = ollama_options) -> dict:
    """LLM generation.

    Args:
        prompt (str): Prompt to send to the model.
        options (OllamaOptions, optional): Ollama options. Defaults to default_options.

    Returns:
        dict: with key `sequences` containing generated sequences from the LLM.
    """
    assert isinstance(options, OllamaOptions)

    for attempt in range(N_RETRIES):
        try:
            response = CLIENT.generate(model=MODEL, prompt=prompt, options=options)
            return {"sequences": [response["response"]]}
        except ollama.ResponseError as e:
            LOGGER_LLM.debug(
                f"Failed to get response due to error \
                    (retry {attempt}/{N_RETRIES}): {e}",
            )
            sleep(min(0.1 + attempt, 5))

    LOGGER_LLM.warning(
        f"Failed to get response after {N_RETRIES} attempts. \
            See debug logs for details.",
    )
    return {"sequences": [""]}
