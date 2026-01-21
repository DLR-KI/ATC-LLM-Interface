# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""Testing ollama api."""

import logging

import ollama
import pydantic
import pytest

from ali.alignment import llm
from ali.alignment.llm import MockedClient, OllamaOptions, chat, generate

SEED = 42

llm.CLIENT = MockedClient()


def test_options_control():
    with pytest.raises(KeyError):
        options = OllamaOptions(abc=0)

    with pytest.raises(pydantic.ValidationError):
        options = OllamaOptions(numa=123)

    messages = [
        {"role": "user", "content": "hello"},
    ]
    options = {"seed": 0}

    with pytest.raises(AssertionError):
        chat(messages=messages, options=options)

    with pytest.raises(AssertionError):
        generate(prompt="Hello", options=options)


def test_chat():
    question = "Why is the sky blue?"
    print(f"question sent to ollama: {question}")

    messages = [ollama.Message(role="user", content=question)]
    response = chat(messages=messages)["sequences"][0]

    assert len(response) > 0, f"received empty response: {response}"
    print(f"ollama response: {response}")


def test_chat_errors(caplog: pytest.LogCaptureFixture):
    """Chat must not fail in case of error, instead, it must retry a few times
    and log a warning."""
    question = "Why is the sky blue?"
    print(f"question sent to ollama: {question}")

    m = Exception

    with caplog.at_level(logging.DEBUG):
        response = chat(messages=[m])["sequences"][0]
        print("Log capture:\v", caplog.record_tuples)
        # Check if last message is a warning
        assert len(caplog.record_tuples) > 0
        assert logging.WARNING == caplog.record_tuples[-1][1]
        assert "Failed to get response" in caplog.record_tuples[-1][-1]

    print(f"ollama response: {response}")


@pytest.mark.skip(
    reason="testing if fixing the seed actually works "
    "(meaning the generation is reproducible)"
    "is only useful to have reproducible results.",
)
def test_chat_seed():
    question = "Why is the sky blue?"
    print(f"question sent to ollama: {question}")

    messages = [ollama.Message(role="user", content=question)]

    options = OllamaOptions(seed=SEED, temperature=0.9, num_ctx=1024)
    response = chat(messages=messages, options=options)["sequences"][0]
    response2 = chat(messages=messages, options=options)["sequences"][0]

    options = OllamaOptions(seed=SEED + 1, temperature=0.9, num_ctx=1024)
    response3 = chat(messages=messages, options=options)["sequences"][0]

    assert len(response) > 0, f"received empty response: {response}"
    assert len(response3) > 0, f"received empty response: {response3}"
    assert response == response2, (
        f"Received different responses with identical \
        seed:\nresponse 1:{response}\nresponse2:{response2}"
    )
    assert response != response3, (
        f"Received identical responses with different \
            seed:\nresponse 1:{response}\nresponse3:{response3}"
    )

    print(f"ollama response: {response}")


@pytest.mark.skip(
    reason="Testing correct greedy decoding is only useful to reproduce experiments.",
)
def test_chat_greedy():
    """Testing if temperature < 0 triggers greedy decoding as expected."""
    question = "Why is the sky blue?"
    print(f"question sent to ollama: {question}")

    messages = [ollama.Message(role="user", content=question)]

    options = OllamaOptions(seed=SEED, temperature=-1.0, num_ctx=1024)
    response_greedy1 = chat(messages=messages, options=options)["sequences"][0]
    response_greedy2 = chat(messages=messages, options=options)["sequences"][0]

    options = OllamaOptions(seed=SEED, temperature=0.9)
    response_sampled = chat(messages=messages, options=options)["sequences"][0]

    for response in [response_greedy1, response_greedy2, response_sampled]:
        assert len(response) > 0, f"received empty response: {response}"
    assert response_greedy1 == response_greedy2, (
        f"Received different \
            responses:\nresponse 1:{response_greedy1}\nresponse2:{response_greedy2}"
    )
    assert response_greedy1 != response_sampled, (
        f"Received identical \
            responses:\nresponse 1:{response_greedy1}\nresponse3:{response_sampled}"
    )

    print(f"ollama response: {response_greedy1}")


def test_generate():
    question = "Why is the sky blue?"
    print(f"question sent to ollama: {question}")

    response = generate(prompt=question)["sequences"][0]

    assert isinstance(response, str), f"received non-str response: {response}"
    assert len(response) > 0, f"received empty response: {response}"
    print(f"ollama response: {response}")
