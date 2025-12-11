# main.py
from fastmcp import FastMCP
import notmuch2
import re
from email import message_from_file
from string import Template
from pathlib import Path

# Prompt loading functionality
PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt_template(filename: str) -> Template:
    """
    Load a prompt template from the prompts directory with error handling.

    Args:
        filename: The name of the prompt file

    Returns:
        Template: A string Template object for the prompt

    Raises:
        FileNotFoundError: If the prompt file doesn't exist
        PermissionError: If the file cannot be read due to permissions
        IOError: If there's an error reading the file
    """
    prompt_file = PROMPTS_DIR / filename

    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    try:
        content = prompt_file.read_text(encoding='utf-8')
        return Template(content)
    except PermissionError:
        raise PermissionError(f"Permission denied reading prompt file: {prompt_file}")
    except Exception as e:
        raise IOError(f"Error reading prompt file {prompt_file}: {e}")

# Create an MCP server instance
mcp = FastMCP("Notmuch Server")

def get_header(message: notmuch2.Message, header_name: str) -> str:
    """Safely get a header from a notmuch message, returning empty string if not found."""
    try:
        return message.header(header_name) or ''
    except LookupError:
        return ''

def is_patch(message: notmuch2.Message, toplevel_message_id: str) -> bool:
    """
    Check if a message is a patch based on:
    1. Its In-Reply-To header equals the toplevel message ID
    2. Its subject contains a PATCH tag (e.g., [PATCH], [RFC PATCH v2], etc.)

    Args:
        message: The notmuch message to check
        toplevel_message_id: The Message-ID of the toplevel/cover letter message

    Returns:
        bool: True if the message is a patch, False otherwise
    """
    try:
        # Check if In-Reply-To matches the toplevel message ID
        in_reply_to = get_header(message, 'in-reply-to')
        in_reply_to = in_reply_to.strip().strip('<>')

        if in_reply_to != toplevel_message_id:
            return False

        # Check if subject contains PATCH tag
        subject = get_header(message, 'subject')

        # Check if it's a reply (starts with Re:, R:, etc.)
        is_reply = bool(re.match(r'^\s*(re?|aw|fwd?):', subject, re.IGNORECASE))
        if is_reply:
            return False

        # Look for PATCH within square brackets at the start, case insensitive
        patch_pattern = r'^\s*\[.*?PATCH.*?\]'
        is_patch = bool(re.search(patch_pattern, subject, re.IGNORECASE))
        return is_patch

    except Exception:
        return False

def walk_replies(message, filter_func=None):
    """
    Walk through message replies, optionally filtering them.

    Args:
        message: The message whose replies to walk
        filter_func: Optional filter function that takes (reply_message, original_message)
                    and returns True if the reply should be included

    Returns:
        list: List of filtered reply messages
    """
    messages = []
    for reply in message.replies():
        # If no filter function is provided, include all messages (original behavior)
        if filter_func is None or filter_func(reply, message):
            messages.append(reply)

        # Recursively walk replies regardless of whether current message was included
        messages.extend(walk_replies(reply, filter_func))

    return messages

def retrieve_thread(db: notmuch2.Database, thread_id: str, all_messages=True) -> list[notmuch2.Message]:
    """
    Retrieve messages in a thread given its thread ID.

    Args:
        db (notmuch2.Database): The open notmuch database
        thread_id (str): The thread ID to retrieve messages from
        all_messages (bool): If True, returns all messages. If False, returns only
                           cover letter and patches.

    Returns:
        list[notmuch2.Message]: A list of Message objects in the thread
    """
    messages = []

    try:
        # Search for the specific thread
        threads = db.threads(f"thread:{thread_id}")

        # Get the first (and should be only) thread
        thread = next(iter(threads), None)

        if thread:
            # Get toplevel messages in the thread
            for toplevel_message in thread.toplevel():
                # Always include the toplevel/cover letter message
                messages.append(toplevel_message)

                # Define filter function based on all_messages parameter
                if all_messages:
                    filter_func = None  # Include all replies
                else:
                    # Create a filter function that identifies patches
                    def patch_filter(reply_message, original_message):
                        return is_patch(reply_message, toplevel_message.messageid)
                    filter_func = patch_filter

                # Get replies using the appropriate filter
                messages.extend(walk_replies(toplevel_message, filter_func))
        else:
            print(f"Thread with ID {thread_id} not found")

    except Exception as e:
        print(f"Error: {e}")
        return []

    return messages

def get_email_body(msg) -> str:
    """
    Extract the body from an email.message.Message object.
    Handles plain text and multipart messages.
    """
    if msg.is_multipart():
        # Walk through the parts and find the first text/plain part
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = part.get("Content-Disposition", "")
            if content_type == "text/plain" and "attachment" not in content_disposition:
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="replace")
        # If no text/plain part found, fallback to first part's payload
        first_part = msg.get_payload(0)
        charset = first_part.get_content_charset() or "utf-8"
        return first_part.get_payload(decode=True).decode(charset, errors="replace")
    else:
        # Not multipart - just decode the payload
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="replace")


def get_message_info(message: notmuch2.Message) -> str:
    """
    Helper function to format basic information about a message as a string.

    Args:
        message (notmuch2.Message): The message object to format info for

    Returns:
        str: Formatted string containing message information
    """
    result = []
    result.append(f"Message ID: {message.messageid}")

    # Get headers directly from notmuch message, handle missing headers gracefully
    result.append(f"In-Reply-To: {get_header(message, 'in-reply-to').strip().strip('<>')}")
    result.append(f"From: {get_header(message, 'from')}")
    result.append(f"To: {get_header(message, 'to')}")
    result.append(f"Cc: {get_header(message, 'cc')}")
    result.append(f"Subject: {get_header(message, 'subject')}")
    result.append(f"Date: {get_header(message, 'date')}")
    result.append(f"Tags: {', '.join(message.tags)}")

    # Get body from file
    with message.path.open() as f:
        email_msg = message_from_file(f)

    body = get_email_body(email_msg)
    result.append("Body:")
    result.append(body)
    result.append("-" * 50)

    return '\n'.join(result)

def do_show_thread(tid: str, all_messages=True) -> str:
    """
    Show thread messages with optional filtering.

    Args:
        tid (str): Thread ID to show
        all_messages (bool): If True, shows all messages. If False, shows only
                           cover letter and patches.

    Returns:
        str: Formatted thread content
    """
    result = []

    try:
        # Open the notmuch database and keep it open while processing
        with notmuch2.Database(mode=notmuch2.Database.MODE.READ_ONLY) as db:
            messages = retrieve_thread(db, tid, all_messages)
            for msg in messages:
                result.append(get_message_info(msg))
    except Exception as e:
        print(f"Error: {e}")
        return f"Error: {e}"

    return '\n'.join(result)

@mcp.tool()
def show_thread(thread_id: str) -> str:
    """
    Displays the content of a thread given its ID.

    Args:
        thread_id: The ID of the thread to display (without the prefix "thread:").

    Returns:
        A formatted string containing the messages in the thread,
        or an error message.
    """
    return do_show_thread(thread_id)

@mcp.tool()
def show_series(thread_id: str) -> str:
    """
    Displays only the cover letter and patch messages from a thread,
    filtering out replies and other non-patch messages.

    This tool returns only:
    - The cover letter (toplevel message)
    - Patch messages (replies to the cover letter with PATCH tag in subject)

    Args:
        thread_id: The ID of the thread to display (without the prefix "thread:").

    Returns:
        A formatted string containing only the cover letter and patch messages
        from the thread, or an error message.
    """
    return do_show_thread(thread_id, all_messages=False)

def do_find_threads(notmuch_filter: str) -> list[tuple[str, str]]:
    """
    Find patch series threads from a notmuch filter.

    Args:
        notmuch_filter: The notmuch query string to filter messages

    Returns:
        list[tuple[str, str]]: List of (thread_id, thread_subject) tuples for patch series

    Raises:
        ValueError: If notmuch_filter is empty or None
        RuntimeError: If database access fails
    """
    if not notmuch_filter or not notmuch_filter.strip():
        raise ValueError("notmuch_filter cannot be empty or None")

    series_threads = []
    seen_threads = set()

    try:
        with notmuch2.Database(mode=notmuch2.Database.MODE.READ_ONLY) as db:
            messages = db.messages(notmuch_filter)

            for message in messages:
                thread_id = message.threadid

                # Skip if we've already processed this thread
                if thread_id in seen_threads:
                    continue

                subject = message.header('subject') or ""

                # Check if this is a patch email (not a reply)
                is_patch = "PATCH" in subject.upper()
                is_reply = any(subject.upper().startswith(prefix) for prefix in ["RE:", "R:"])

                if is_patch and not is_reply:
                    # Get thread subject directly from the thread
                    thread_query = db.threads(f"thread:{thread_id}")
                    try:
                        thread = next(iter(thread_query))
                        series_threads.append((thread_id, thread.subject or subject))
                        seen_threads.add(thread_id)
                    except StopIteration:
                        # Thread not found, use message subject as fallback
                        series_threads.append((thread_id, subject))
                        seen_threads.add(thread_id)

    except notmuch2.NotmuchError as e:
        raise RuntimeError(f"Notmuch database error: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error while searching threads: {e}")

    return series_threads

@mcp.tool()
def find_threads(notmuch_filter: str) -> list[tuple[str, str]]:
    """
    Finds series using a notmuch filter string and returns a list containing the pair
    (thread id, thread subject) corresponding to each thread matching the filter.
    notmuch_filter must match only toplevel messages or messages whose subject
    contains "PATCH" and are no "Re:" "RE:" "R:"

    Args:
        notmuch_filter: The notmuch query to execute.
                       Example: "from:jane@example.com AND tag:unread"

    Returns:
        list[(str, str)]: A list of thread IDs and subjects for each thread matching the search criteria
    """
    return do_find_threads(notmuch_filter)

@mcp.prompt
def my_status(notmuch_filter: str) -> str:
    """Show the status of the patches pushed on a mailing list"""
    try:
        template = load_prompt_template("my_status.md")
        return template.safe_substitute(notmuch_filter=notmuch_filter)
    except (FileNotFoundError, PermissionError, IOError) as e:
        return f"Error loading prompt template: {e}"

@mcp.prompt
def next_revision(notmuch_filter: str) -> str:
    """Creates the git notes for the next respin of the series"""
    try:
        template = load_prompt_template("next_revision.md")
        return template.safe_substitute(notmuch_filter=notmuch_filter)
    except (FileNotFoundError, PermissionError, IOError) as e:
        return f"Error loading prompt template: {e}"

@mcp.prompt
def review_series(notmuch_filter: str, review_prompts_path: str) -> str:
    """Review a series of patches from a mailing list using notmuch tools and custom analysis prompts"""
    try:
        template = load_prompt_template("reviews.md")
        return template.safe_substitute(
            notmuch_filter=notmuch_filter,
            review_prompts_path=review_prompts_path
        )
    except (FileNotFoundError, PermissionError, IOError) as e:
        return f"Error loading prompt template: {e}"

if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2 and sys.argv[1] == "stdio":
        mcp.run()
    if len(sys.argv) == 2:
        threads = do_find_threads(sys.argv[1])
        do_show_thread(threads[0][0], False)
    else:
        mcp.run(transport="http", host="0.0.0.0", port=8000, path="/")
