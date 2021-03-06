import xml.etree.ElementTree as etree
from collections import OrderedDict
from itertools import islice
import urllib.request
import threading
import datetime
import random
import time
import sys
import os
import re

from spam_checker import (remove_all_limit, user_spam_check)
from config import (credentials, settings, update)
from utils import printf as print
import functions as func
import utils

from twython import TwythonStreamer


__program__ = "AcePictureBot"
__version__ = "2.9.6"
DEBUG = False


def post_tweet(API, tweet, media="", command=False, rts=False):
    try:
        if rts and command:
            print("[{0}] Tweeting: {1} ({2}): [{3}] {4}".format(
                time.strftime("%Y-%m-%d %H:%M"),
                rts['user']['screen_name'], rts['user']['id_str'],
                command, tweet))
        else:
            print("[{0}] Tweeting: {1}".format(
                time.strftime("%Y-%m-%d %H:%M"),
                tweet))
        if rts:
            if media:
                media_ids = []
                print("(Image: {0})".format(media))
                if isinstance(media, list):
                    for img in media:
                        p = open(img, 'rb')
                        if ".mp4" in img:
                            media_ids.append(
                                API.upload_video(
                                    media=p,
                                    media_type='video/mp4')['media_id'])
                        else:
                            media_ids.append(
                                API.upload_media(media=p)['media_id'])
                else:
                    p = open(media, 'rb')
                    if ".mp4" in media:
                        media_ids.append(
                            API.upload_video(
                                media=p,
                                media_type='video/mp4')['media_id'])
                    else:
                        media_ids.append(
                            API.upload_media(media=p)['media_id'])

                API.update_status(status=tweet, media_ids=media_ids,
                                  in_reply_to_status_id=rts['id'])
            else:
                API.update_status(status=tweet,
                                  in_reply_to_status_id=rts['id'])
    except Exception as e:
        print(e)
        pass


def tweet_command(API, status, message, command):
    tweet = False
    tweet_image = False
    user = status['user']
    # Mod command
    is_mod = [True if user['id_str'] in MOD_IDS else False][0]
    is_patreon = [True if user['id_str'] in PATREON_IDS else False][0]
    if command == "DelLimits":
        if is_mod:
            their_id, cmd = message.split(' ', 2)
            remove_all_limit(their_id, cmd)
            print("[INFO] Removed limits for {0} - {1}".format(
                their_id, cmd))
        return "Removed!", False
    if command == "AllowAcc":
        if is_mod:
            func.allow_user(message)
            print("[INFO] Allowing User {0} to register!".format(message))
            ALLOWED_IDS.append(message)
    if not is_patreon and not is_mod:
        user_is_limited = user_spam_check(user['id_str'],
                                          user['screen_name'], command)
        if isinstance(user_is_limited, str):
            # User hit limit, tweet warning
            command = ""
            tweet = user_is_limited
        elif not user_is_limited:
            # User is limited, return
            print("[{0}] User is limited! Ignoring...".format(
                time.strftime("%Y-%m-%d %H:%M")))
            return False

    if settings['count_on'] and command:
        func.count_command("Global", command, settings['count_file'])
        func.count_command("Commands", command,
                           os.path.join(settings['user_count_loc'],
                                        user['id_str']))

    if command == "PicTag":
        if is_mod or is_patreon:
            get_imgs = 1
            try:
                count = int(re.search(r'\d+', message).group())
            except (AttributeError):
                count = False
            if count:
                if count > 4:
                    get_imgs = 4
                elif count < 1:
                    get_imgs = 1
                else:
                    get_imgs = count
            tweet, tweet_image = func.pictag(message.replace(str(count), ""),
                                             repeat_for=get_imgs)

    if command == "DiscordConnect":
        tweet = func.DiscordConnect(message, user['id_str'])

    if command == "DiscordJoin":
        tweet = ("Invite the bot by using this: "
                 "https://discordapp.com/oauth2/authorize?"
                 "&client_id=170367887393947648&scope=bot")
    # Joke Commands
    if command == "spook":
        tweet, tweet_image = func.spookjoke()
    if command == "Spoiler":
        tweet = random.choice(utils.file_to_list(
            os.path.join(settings['list_loc'],
                         "spoilers.txt")))
    elif command == "!Level":
        tweet = func.get_level(twitter_id=user['id_str'])

    # Main Commands
    if command == "Waifu":
        tweet, tweet_image = func.waifu(0, message, user_id=user['id_str'])
    elif command == "Husbando":
        tweet, tweet_image = func.waifu(1, message, user_id=user['id_str'])

    gender = utils.gender(status['text'])
    if gender == 0:
        g_str = "waifu"
    else:
        g_str = "husbando"
    if "Register" in command:
        is_allowed = [True if user['id_str'] in ALLOWED_IDS else False][0]
        if is_mod:
            is_allowed = True
        follow_result = is_following(user['id_str'], is_allowed)
        if follow_result == "Limited":
            tweet = ("The bot is currently limited on checking stuff.\n"
                     "Try again in 15 minutes!")
            func.remove_one_limit(user['id_str'], g_str.lower() + "register")
        elif follow_result == "Not Genuine":
            tweet = ("Your account wasn't found to be genuine.\n"
                     "Help: {url}").format(
                url=func.config_get('Help URLs', 'not_genuine'))
        elif not follow_result:
            tweet = ("You must follow @AcePictureBot to register!\n"
                     "Help: {url}").format(
                url=func.config_get('Help URLs', 'must_follow'))
        else:
            tweet, tweet_image = func.waifuregister(user['id_str'],
                                                    user['screen_name'],
                                                    message, gender)

    if "My" in command:
        skip_dups = False
        get_imgs = 1
        if "my{g_str}+".format(g_str=g_str) in message.lower():
            skip_dups = True
        if "my{g_str}-".format(g_str=g_str) in message.lower():
            func.delete_used_imgs(user['id_str'], False)
        if is_mod or is_patreon:
            try:
                count = int(re.search(r'\d+', message).group())
            except (AttributeError):
                count = False
            if count:
                if count > 4:
                    get_imgs = 4
                elif count < 1:
                    get_imgs = 1
                else:
                    get_imgs = count

        tweet, tweet_image = func.mywaifu(user['id_str'], gender,
                                          False, skip_dups, get_imgs)

    if "Remove" in command:
        tweet = func.waifuremove(user['id_str'], gender)

    if command == "OTP":
        tweet, tweet_image = func.otp(message)

    list_cmds = ["Shipgirl", "Touhou", "Vocaloid",
                 "Imouto", "Idol", "Shota",
                 "Onii", "Onee", "Sensei",
                 "Monstergirl", "Witchgirl", "Tankgirl",
                 "Senpai", "Kouhai", "Granblue"]
    if command in list_cmds:
        tweet, tweet_image = func.random_list(command, message)

    if command == "Airing":
        tweet = func.airing(message)
        # No results found.
        if not tweet:
            return False

    if command == "Source":
        tweet = func.source(API, status)

    if tweet or tweet_image:
        tweet = "@{0} {1}".format(user['screen_name'], tweet)
        post_tweet(API, tweet, tweet_image, command, status)


def acceptable_tweet(status):
    global USER_LAST_COMMAND
    global IGNORE_WORDS
    global BLOCKED_IDS

    tweet = status['text']
    user = status['user']
    # Ignore ReTweets.
    if tweet.startswith('RT'):
        return False, False
    if tweet.startswith('Retweeted'):
        return False, False

    if DEBUG:
        if user['id_str'] not in MOD_IDS:
            return False, False

    # Reload in case of manual updates.
    BLOCKED_IDS = utils.file_to_list(
        os.path.join(settings['list_loc'],
                     "Blocked Users.txt"))
    ALLOWED_IDS = utils.file_to_list(
        os.path.join(settings['list_loc'],
                     "Allowed Users.txt"))
    PATREON_IDS = utils.file_to_list(
        os.path.join(settings['list_loc'],
                     "Patreon Users.txt"))
    IGNORE_WORDS = utils.file_to_list(
        os.path.join(settings['list_loc'],
                     "Blocked Words.txt"))

    # Ignore bots and bad boys.
    if user['id_str'] in BLOCKED_IDS:
        return False, False

    # Ignore some messages.
    if any(word.lower() in tweet.lower()
           for word in IGNORE_WORDS):
        return False, False

    # Make sure the message has @Bot in it.
    if not any("@" + a.lower() in tweet.lower()
               for a in settings['twitter_track']):
        return False, False

    # If the user @sauce_plz add "source" to the text
    if "sauce" in tweet.lower():
        tweet += " source"

    # Remove extra spaces.
    tweet = re.sub(' +', ' ', tweet).lstrip()

    # Remove @UserNames (usernames could trigger commands alone)
    tweet = tweet.replace("🚢👧", "Shipgirl")
    tweet = ' '.join(
            re.sub('(^|\n| )(@[A-Za-z0-9_🚢👧.+-]+)', ' ', tweet).split())
    tweet = tweet.replace("#", "")

    # Find the command they used.
    command = utils.get_command(tweet)
    if command == "WaifuRegister" or command == "HusbandoRegister" \
            or command == "DiscordConnect":
        # Cut the text off after the command word.
        reg = "({0})(?i)".format(command)
        if len(tweet) > (len(command) +
                         len(settings['twitter_track'][0]) + 2):
            tweet = re.split(reg, tweet)[2].lstrip()

    # No command is found see if acceptable for a random waifu.
    if not command:
        # Ignore quote ReTweets only in this case.
        if tweet.startswith('"@'):
            return False, False
        # Ignore if it doesn't mention the main bot only.
        if settings['twitter_track'][0].lower() not in status['text'].lower():
            return False, False
        # Last case, check if they're not replying to a tweet.
        if status['in_reply_to_status_id_str'] is None:
            command = "Waifu"
        else:
            return False, False

    if command == "Reroll" or command == "Another One":
        try:
            tweet = USER_LAST_COMMAND[user['id_str']]
            command = utils.get_command(tweet)
            if not command:
                return False, False
            if "Register" in command:
                return False, False
            elif command is False:
                return False, False
        except (ValueError, KeyError):
            return False, False
    else:
        USER_LAST_COMMAND[user['id_str']] = tweet
        if len(USER_LAST_COMMAND) > 30:
            USER_LAST_COMMAND = (OrderedDict(
                islice(USER_LAST_COMMAND.items(),
                       20, None)))

    # Stop someone limiting the bot on their own.
    rate_time = datetime.datetime.now()
    rate_limit_secs = 10800
    rate_limit_user = 15
    if user['id_str'] in PATREON_IDS:
        # Still a limit just in case
        rate_limit_user = 35
    if user['id_str'] in RATE_LIMIT_DICT:
        # User is now limited (3 hours).
        if ((rate_time - RATE_LIMIT_DICT[user['id_str']][0])
                .total_seconds() < rate_limit_secs)\
           and (RATE_LIMIT_DICT[user['id_str']][1] >= rate_limit_user):
            return False, False
        # User limit is over.
        elif ((rate_time - RATE_LIMIT_DICT[user['id_str']][0])
                .total_seconds() > rate_limit_secs):
            del RATE_LIMIT_DICT[user['id_str']]
        else:
            # User found, not limited, add one to the trigger count.
            RATE_LIMIT_DICT[user['id_str']][1] += 1
    else:
        # User not found, add them to RATE_LIMIT_DICT.
        # Before that quickly go through RATE_LIMIT_DICT
        # and remove all the finished unused users.
        for person in list(RATE_LIMIT_DICT):
            if ((rate_time - RATE_LIMIT_DICT[person][0])
               .total_seconds() > rate_limit_secs):
                del RATE_LIMIT_DICT[person]
        RATE_LIMIT_DICT[user['id_str']] = [rate_time, 1]

    # This shouldn't happen but just in case.
    if not isinstance(command, str):
        return False, False

    tweet = tweet.lower().replace(command.lower(), " ", 1).strip()
    return tweet, command


def is_following(user_id, is_allowed=False):
    if not is_allowed:
        try:
            user_info = API.lookup_user(user_id=user_id)
        except twython.exceptions.TwythonAuthError:
            return "Limited"
        if user_info[0]['statuses_count'] < 10:
            return "Not Genuine"
        elif user_info[0]['followers_count'] < 5:
            return "Not Genuine"
    try:
        ship = API.lookup_friendships(user_id='2910211797,{}'.format(user_id))
    except twython.exceptions.TwythonAuthError:
        return "Limited"
    try:
        return 'followed_by' in ship[1]['connections']
    except (TypeError, IndexError):
        # Account doesn't exist anymore.
        # Not Following.
        return False


def status_account(status_api):
    """ Read RSS feeds and post them on the status Twitter account.
    :param status_api: The Tweepy API object for the status account.
    """
    def read_rss(url, name, pre_msg, find_xml):
        recent_id = open(os.path.join(settings['ignore_loc'],
                         name), 'r').read()
        try:
            rss = urllib.request.urlopen(url).read().decode("utf-8")
            xml = etree.fromstring(rss)
        except:
            # Don't need anymore than this for something like this
            print("Failed to read/parse {0} ({1}) RSS".format(name, url))
            return False

        if bool(find_xml['sub_listing']):
            entry = xml[0][find_xml['entries_in']]
        else:
            entry = xml[find_xml['entries_in']]
        current_id = entry.findtext(
            find_xml['entry_id'])

        if current_id == recent_id:
            return False

        with open(os.path.join(settings['ignore_loc'], name), "w") as f:
            f.write(current_id)

        if bool(find_xml['get_href']):
            msg_url = entry.find(find_xml['link_id']).get('href')
        else:
            msg_url = entry.findtext(find_xml['link_id'])

        msg_msg = re.sub('<[^<]+?>', '', entry.findtext(find_xml['msg_id']))
        msg_msg = re.sub(' +', ' ', os.linesep.join(
                         [s for s in msg_msg.splitlines() if s])).lstrip()
        msg = "{0}{1}\n{2}".format(pre_msg,
                                   utils.short_string(msg_msg, 90),
                                   msg_url)
        if not DEBUG:
            print(msg)
            status_api.update_status(status=msg)

    while True:
        url = "https://github.com/ace3df/AcePictureBot/commits/master.atom"
        name = "GitCommit.txt"
        pre_msg = "[Git Commit]\n"
        find_xml = {"sub_listing": False,
                    "entries_in": 5,
                    "entry_id": "{http://www.w3.org/2005/Atom}id",
                    "link_id": "{http://www.w3.org/2005/Atom}link",
                    "get_href": True,
                    "msg_id": "{http://www.w3.org/2005/Atom}content"}
        read_rss(url, name, pre_msg, find_xml)
        time.sleep(3 * 60)


class TwitterStream(TwythonStreamer):
    def on_success(self, data):
        global HAD_ERROR
        global HANG_TIME
        global TWEETS_READ
        tweet_datetime = datetime.datetime.strptime(
                data['created_at'], '%a %b %d %H:%M:%S %z %Y')
        days_past = datetime.datetime.now(datetime.timezone.utc) - tweet_datetime
        if days_past.days > 1:
            return False
        # Fri Apr 15 16:59:09 +0000 2016
        if data['id_str'] in TWEETS_READ:
            return True
        TWEETS_READ.append(data['id_str'])
        HANG_TIME = time.time()
        tweet, command = acceptable_tweet(data)
        if not command:
            return True
        try:
            open(update['is_busy_file'], 'w')
        except PermissionError:
            # This wont happen all the time, the file is probably busy
            pass
        print("[{0}] {1} ({2}): {3}".format(
            time.strftime("%Y-%m-%d %H:%M"),
            data['user']['screen_name'], data['user']['id_str'], data['text']))
        tweet_command(API, data, tweet, command)
        HAD_ERROR = False
        with open(os.path.join(settings['ignore_loc'],
                               "tweets_read.txt"), 'w') as file:
            file.write("\n".join(TWEETS_READ))
        try:
            os.remove(update['is_busy_file'])
        except (PermissionError, FileNotFoundError):
            # Related to above PermissionError.
            pass

    def on_error(self, status_code, data):
        """
        global LAST_STATUS_CODE
        global HANG_TIME
        HANG_TIME = time.time()
        if int(status_code) != int(LAST_STATUS_CODE):
            LAST_STATUS_CODE = status_code
            msg = ("[{0}] Twitter Returning Status Code: {1}.\n"
                   "More Info: "
                   "https://dev.twitter.com/overview/api/response-codes"
                   ).format(time.strftime("%Y-%m-%d %H:%M"), status_code)
            print(msg)
            post_tweet(func.login(status=True), msg)
        return True
        """
        print(status_code)


class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, target, kwargs):
        super(StoppableThread, self).__init__(target=target, kwargs=kwargs)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


def start_stream():
    try:
        stream = TwitterStream(credentials['consumer_key'],
                               credentials['consumer_secret'],
                               credentials['access_token'],
                               credentials['access_token_secret'])
        print("[INFO] Reading Twitter Stream!")
        # TODO: Start Thread here
        stream_thread = StoppableThread(
            target=stream.statuses.filter,
            kwargs={'track': ', '.join(
                [x.lower() for x in settings['twitter_track']])})
        stream_thread.daemon = True
        stream_thread.start()
    except (KeyboardInterrupt, SystemExit, RuntimeError):
        stream_thread.stop()
        stream.disconnect()
        sys.exit(0)
    return stream


def handle_stream(status_api=False):
    stream = start_stream()
    global HANG_TIME
    try:
        while True:
            time.sleep(5)
            elapsed = (time.time() - HANG_TIME)
            if elapsed > 600:
                # TODO: Temp to try and stop crash tweet spam for now
                if os.path.exists(update['last_crash_file']):
                    if time.time() - os.path.getctime(
                            update['last_crash_file']) > 80000:
                        os.remove(update['last_crash_file'])
                        open(update['last_crash_file'], 'w')
                        msg = """[{0}] Restarting!
The bot will catch up on missed messages now!""".format(
                            time.strftime("%Y-%m-%d %H:%M"))
                        if status_api:
                            status_api.update_status(status=msg)
                        else:
                            print(msg)
                stream.disconnect()
                threading.Thread(target=read_notifications,
                                 args=(API, True, TWEETS_READ)).start()
                time.sleep(5)
                stream = start_stream()
                HANG_TIME = time.time()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


def read_notifications(API, reply, tweets_read):
    statuses = API.get_mentions_timeline()
    print("[INFO] Reading late tweets!")
    for status in reversed(statuses):
        if status['id_str'] in TWEETS_READ:
            continue
        tweet, command = acceptable_tweet(status)
        if not command:
            continue
        if reply:
            print("[{0} - Late]: {1} ({2}): {3}".format(
                time.strftime("%Y-%m-%d %H:%M"),
                status['user']['screen_name'], status['user']['id_str'],
                status['text']))
            tweet_command(API, status, tweet, command)
        TWEETS_READ.append(status['id_str'])
        with open(os.path.join(settings['ignore_loc'],
                               "tweets_read.txt"),
                  'w') as file:
            file.write("\n".join(TWEETS_READ))
    print("[INFO] Finished reading late tweets!")

if __name__ == '__main__':
    BLOCKED_IDS = utils.file_to_list(
        os.path.join(settings['list_loc'],
                     "Blocked Users.txt"))
    ALLOWED_IDS = utils.file_to_list(
        os.path.join(settings['list_loc'],
                     "Allowed Users.txt"))
    PATREON_IDS = utils.file_to_list(
        os.path.join(settings['list_loc'],
                     "Patreon Users.txt"))
    IGNORE_WORDS = utils.file_to_list(
        os.path.join(settings['list_loc'],
                     "Blocked Words.txt"))
    LIMITED = False
    HAD_ERROR = False
    LAST_STATUS_CODE = 0
    TWEETS_READ = []
    MOD_IDS = ["2780494890", "121144139"]
    RATE_LIMIT_DICT = {}
    USER_LAST_COMMAND = OrderedDict()
    START_TIME = time.time()
    HANG_TIME = time.time()
    API = None
    STATUS_API = None
    SAPI = None
    TWEETS_READ = utils.file_to_list(
        os.path.join(settings['ignore_loc'],
                     "tweets_read.txt"))
    # TODO: TEMP (Read above)
    open(update['last_crash_file'], 'w')
    API = func.login()
    STATUS_API = func.login(status=True)
    read_notifications(API, False, TWEETS_READ)
    threading.Thread(target=status_account, args=(STATUS_API, )).start()
    threading.Thread(target=func.check_website).start()
    handle_stream(STATUS_API)
