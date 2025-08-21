# main.py
from fastmcp import FastMCP
import notmuch2
from email import message_from_file

# Create an MCP server instance
mcp = FastMCP("Notmuch Server")

def walk_replies(messages, message):
    for reply in message.replies():
        messages.append(reply)
        walk_replies(messages, reply)

def retrieve_thread(thread_id: str) -> list[notmuch2.Message]:
    """
    Retrieve all messages in a thread given its thread ID.
    
    Args:
        thread_id (str): The thread ID to retrieve messages from
    
    Returns:
        list[notmuch2.Message]: A list of Message objects in the thread
    """
    messages = []
    
    try:
        # Open the notmuch database
        with notmuch2.Database(mode=notmuch2.Database.MODE.READ_ONLY) as db:
            # Search for the specific thread
            threads = db.threads(f"thread:{thread_id}")

            # Get the first (and should be only) thread
            thread = next(iter(threads), None)

            if thread:
                # Get all messages in the thread
                for message in thread.toplevel():
                    messages.append(message)
                    walk_replies(messages, message)
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
    
    with message.path.open() as f:
        email_msg = message_from_file(f)
    
    result.append(f"From: {email_msg.get('From')}")
    result.append(f"To: {message.header('to')}")
    result.append(f"Subject: {email_msg.get('Subject')}")
    result.append(f"Date: {message.header('date')}")
    result.append(f"Message-id: {message.messageid}")
    result.append(f"Tags: {', '.join(message.tags)}")
    
    body = get_email_body(email_msg)
    result.append("Body:")
    result.append(body)
    result.append("-" * 50)
    
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
    result = []

    messages = retrieve_thread(thread_id)
    for msg in messages:
        result.append(get_message_info(msg))

    return '\n'.join(result)

@mcp.tool()
def find_threads(notmuch_filter: str) -> list[tuple[str, str]]:
    """
    Finds threads using a notmuch filter string and returns a list containing the pair
    (thread id, thread subject) corresponding to each thread matching the filter.

    Args:
        notmuch_filter: The notmuch query to execute. 
                       Example: "from:jane@example.com AND tag:unread"

    Returns:
        list[(str, str)]: A list of thread IDs and subjects for each thread matching the search criteria
    """
    thread_ids = []
    
    try:
        # Open the notmuch database
        with notmuch2.Database(mode=notmuch2.Database.MODE.READ_ONLY) as db:
            # Perform the search query
            threads = db.threads(notmuch_filter)
            
            # Extract thread IDs
            for thread in threads:
                thread_ids.append((thread.threadid, thread.subject))
                
    except Exception as e:
        print(f"Error: {e}")
        return []
    
    return thread_ids

if __name__ == "__main__":
    # To run this server:
    # 1. Make sure you have notmuch installed and configured.
    # 2. Install the required Python libraries:
    #    pip install fastmcp python-notmuch2
    # 3. Run the server from your terminal:
    #    fastmcp run main.py
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/")
