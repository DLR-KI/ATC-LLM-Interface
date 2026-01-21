# SPDX-FileCopyrightText: 2026 German Aerospace Center (DLR e.V.) <https://dlr.de>
#
# SPDX-License-Identifier: Apache-2.0
"""A browser UI based on Gradio.

By default, is accessible on http://127.0.0.1:7860/

The UI displays the CD/CR steps, the policy and the LLM generations.
"""

import logging
import typing
from queue import Empty

import gradio as gr
from gradio import ChatMessage

from ali.alignment.policy import ATCPolicy
from ali.ui.logger import LOGGER_ALI, LOGGER_CD, LOGGER_CLEARANCES, LOGGER_CR

formatter = logging.Formatter("%(message)s")

cd_queue = LOGGER_CD.handlers[2].queue  # type: ignore[attr-defined]
cr_queue = LOGGER_CR.handlers[2].queue  # type: ignore[attr-defined]
med_queue = LOGGER_ALI.handlers[2].queue  # type: ignore[attr-defined]
clear_queue = LOGGER_CLEARANCES.handlers[2].queue  # type: ignore[attr-defined]

queues = [cd_queue, cr_queue, med_queue, clear_queue]


css = """
code {
  white-space : pre-wrap !important;
}

.contain { display: flex; flex-direction: column; }
.gradio-container {height: 100vh !important; max-width: unset !important; \
    width: 100vw !important;}
.chatbot { flex-grow: 1; overflow: auto;}
#component-0 { height: 100%; width: 100%;}
#chats-container {flex-grow: 1; overflow: auto;}
#chat-op {height: 100%;}
#chat-postop {height: 100%;}
"""


ChatHistory = typing.NewType("ChatHistory", list[ChatMessage])


def update_histories(
    histories_to_update: list[ChatHistory],
    text: str,
    log_name: str,
) -> None:
    """Updates the given histories with the text from the log record.

    Args:
        histories_to_update (list): list of chat histories to update.
            A chat history is a list of ChatMessages.
        text (str): text to be converted into ChatMessage and added to the histories.
        log_name (str): name of the log record which provided the text.
            This information is useful to provide context messages.
    """
    for history in histories_to_update:
        # based on some rules,
        # the message is either displayed on the left ('assistant')
        # or on the right ('user') of the chat.
        if log_name == "RADAR-CD":
            history.append(
                ChatMessage(role="user", content="# RADAR\nConflict Detected"),
            )
            history.append(ChatMessage(role="assistant", content=text))
        elif log_name == "DATCO-CR":
            history.append(
                ChatMessage(
                    role="user",
                    content="# ATCO assistant\nConflict Resolution",
                ),
            )
            history.append(ChatMessage(role="assistant", content=text))
        elif log_name == "DATCO-CLEARANCES":
            if not (str(history[-1].content).startswith("Scheduling task")):
                history.append(
                    ChatMessage(
                        role="user",
                        content="# ATCO assistant\nScheduling clearances",
                    ),
                )
            history.append(ChatMessage(role="assistant", content=text))
        elif log_name == "ALI":
            if text.startswith("# Best solution"):
                history.append(ChatMessage(role="user", content="# ALI\nResult"))
                history.append(ChatMessage(role="assistant", content=text))
            elif text.startswith("\n### LLM ANSWER \n"):
                history.append(ChatMessage(role="assistant", content=text))
            elif text.startswith("\n### LLM PROMPT\n"):
                history.append(ChatMessage(role="user", content=text))
            else:
                history.append(ChatMessage(role="user", content=text))
        else:
            # technically, all case must be covered above
            # this is just to collect uncaught cases.
            history.append(ChatMessage(role="assistant", content=text))


def display_resolution(
    history_op: ChatHistory,
    history_detailed: ChatHistory,
) -> typing.Generator[tuple[ChatHistory, ChatHistory], None, None]:
    """Display the messages in the gradio app.

    The message are extracted from the log record,
    and added to the respective chat message history.

    Args:
        history_op (list): message history for the "During operation explanation" chat
        history_detailed (list): message history for
            the "post-operation explanation" chat

    Yields:
        Iterator[typing.Generator[tuple[list, list], None, None]]: _description_
    """
    for que in queues:
        while not que.empty():
            try:
                log_record = que.get(block=False)
                message = str(log_record.message)
                # History op is only updated if log level >= 20
                # (i.e. info and above)
                histories_to_update = (
                    [history_op, history_detailed]
                    if log_record.levelno >= 20
                    else [history_detailed]
                )

                update_histories(histories_to_update, message, log_record.name)
                yield history_op, history_detailed
            except Empty:
                break

    yield history_op, history_detailed


def init(policy: ATCPolicy | None = None, gui: bool = True) -> None:
    """Setup and launch the gradio app.

    Args:
        policy (ATCPolicy, optional): Policy to be displayed. Defaults to None.
        gui (bool, optional): if true, the web interface will pops up in a browser.
            If false, the app is still running in the background and can be accessed.
    """
    with gr.Blocks(css=css, title="ALI demo") as demo:
        gr.Markdown("# Conflict resolution with *policy compliance*")

        if policy is not None:
            with gr.Accordion("Policy", open=True):
                md = "# Filtering rules\n"
                md += "```\n"
                for rule in policy.filtering_rules:
                    md += str(rule) + "\n"
                md += "```\n"
                md += "# Sorting rules\n"
                md += "```\n"
                for rule in policy.sorting_rules:
                    md += str(rule) + "\n"
                md += "```\n"

                gr.Markdown(md)

        with gr.Row(elem_id="chats-container"):
            with gr.Column(elem_id="chat-op"):
                gr.Markdown("# During operation explanation ")
                chat_op = gr.Chatbot(
                    elem_classes="chatbot",
                    show_label=False,
                    type="messages",
                )
            with gr.Column(elem_id="chat-postop"):
                gr.Markdown("# Post-operation explanation ")
                chat_details = gr.Chatbot(
                    elem_classes="chatbot",
                    show_label=False,
                    type="messages",
                )

        timer = gr.Timer(value=2)

        timer.tick(
            display_resolution,
            inputs=[chat_op, chat_details],
            outputs=[chat_op, chat_details],
        )

    demo.launch(
        prevent_thread_lock=True,
        inbrowser=gui,
    )
