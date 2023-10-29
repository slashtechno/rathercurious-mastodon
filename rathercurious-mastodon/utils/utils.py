from bs4 import BeautifulSoup
import re
from mastodon import Mastodon, StreamListener
from .command import Command
import trio

class stream_listener:
    """
    A class of functions to allow for easy streaming of Mastodon statuses with sensible defaults.
    """

    def __init__(
        self,
        mastodon_access_token: str,
        mastodon_api_base_url: str,
        delete_when_done: bool = False,
        always_mention: bool = True,
        commands: list = None,
    ):
        """
        Initialize the class.
        """
        # self.mastodon_access_token = mastodon_access_token
        # self.mastodon_api_base_url = mastodon_api_base_url
        self.delete_when_done = delete_when_done
        self.always_mention = always_mention
        self.commands = commands

        self.mastodon = Mastodon(
            access_token=mastodon_access_token, api_base_url=mastodon_api_base_url
        )

    class partially_configured_stream_listener(StreamListener):
        """
        What events cause what actions.
        """

        def __init__(
            self,
            mastodon: Mastodon,
            delete_when_done: bool = False,
            always_mention: bool = True,
            commands: list = None,
        ):
            self.mastodon = mastodon
            self.always_mention = always_mention
            self.commands = commands
            self.posts_to_delete = []

        def on_update(self, status):
            # As far as I can tell, an update caused when you reblog or when an account you follow posts something  # noqa E501
            # logger.info(f"JSON: {json.dumps(status, indent=4, default=str)}")
            # https://docs.joinmastodon.org/entities/Status/
            # https://docs.joinmastodon.org/entities/Notification/
            pass

        def on_notification(self, notification):
            if notification["type"] == "mention":
                content = Command.parse_status(
                    status=notification["status"],
                    always_mention=self.always_mention,
                    commands=self.commands,
                )  # noqa E501
                post = self.mastodon.status_post(
                    # Set the content of the status to the string returned above
                    content,
                    # Reply to the mention
                    in_reply_to_id=notification["status"]["id"],
                    # Match the visibility of the mention
                    visibility=notification["status"]["visibility"],
                )
                self.posts_to_delete.append(post["id"])

            elif notification["type"] == "favourite":
                pass
            else:
                pass
    def stream(self):
        """
        Stream statuses.
        """
        self.fully_configured_stream_listener = self.partially_configured_stream_listener(
            mastodon=self.mastodon,
            delete_when_done=self.delete_when_done,
            always_mention=self.always_mention,
            commands=self.commands,
        )
        self.mastodon.stream_user(self.fully_configured_stream_listener, run_async=True)
        trio.run(self.sleep_or_not)

    async def sleep_or_not(self):
        '''Used to optionally run other code while the stream is running, in addition to optionally deleting posts when done'''
        try:
            async with trio.open_nursery() as nursery:
                nursery.start_soon(trio.sleep_forever)
                nursery.start_soon(self.need_to_run)
        except KeyboardInterrupt:
            if self.delete_when_done:
                for post in self.fully_configured_stream_listener.posts_to_delete:
                    self.mastodon.status_delete(post)

    @staticmethod
    async def need_to_run():
        '''Code that needs to run while the stream is running'''
        pass

def return_raw_argument(status: dict):
    """
    Return the raw arguments (everything after the hashtag) as a string.
    Uses utils.parse_html() to parse the HTML, adding newlines after every <p> tag
    In many cases, if regex is being used anyway, it's better to use that instead
    """
    content = parse_html(html_content=status["content"])
    # Match from the beginning of the string, a hashtag, a space, and then ANYTHING, including newlines # noqa E501
    # re.DOTALL is present so commands can span multiple lines
    if matches := re.search(
        r"^(?:@\w+\s+)(?:#\w+\s+)(.+)$",
        # From what I can tell, there will always be a mention if it's a reply. Some clients just don't show it in the body content
        content,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        return matches.group(1)
    else:
        # Unsure if it should return None or an empty string
        return None


def parse_html(html_content: str):
    """Return the raw post content, with newlines after every <p> tag"""

    content = BeautifulSoup(html_content, "html.parser")
    for p in content.find_all("p"):
        p.insert_after("\n")
        # Perhaps don't insert a newline if it's the last <p> tag?
    raw_content = content.get_text(separator="")
    return raw_content
