import discord
import aiohttp
import asyncio
import json
import os

import tweepy as tw

from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

from redbot.core import commands
from redbot.core import Config
from redbot.core import checks
from redbot.core.data_manager import cog_data_path

class QPosts(commands.Cog):
    """Real-time Q drop aggreagation and notification."""

    def __init__(self, bot):
        self.bot = bot
        
        default_data = {
            "twitter": {
                "access_secret": "",
                "access_token": "",
                "consumer_key": "",
                "consumer_secret": "",
                "enabled": False
            },
            "boards": {},
            "channels": [],
            "last_checked": 0,
            "print": True,
            "mention_role": True,
            "mention_role_name": "QPOSTS"
        }

        self.config = Config.get_conf(self, 112444567876)
        self.config.register_global(**default_data)
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        
        self.url = "https://8kun.top"
        self.TORurl = "http://jthnx5wyvjvzsxtu.onion"
        
        self.boards = ["projectdcomms", "qresearch"]
        self.legacy_boards = [
            "cbts", 
            "thestorm", 
            "greatawakening", 
            "patriotsfight", 
            "projectdcomms", 
            "qresearch"
        ]
        
        self.trips = [
            "!UW.yye1fxo", "!ITPb.qbhqo",  "!xowAT4Z3VQ",
            "!4pRcUA0lBE", "!CbboFOtcZs",  "!A6yxsPKia.",
            "!2jsTvXXmX",  "!!mG7VJxZNCI", "!!Hs1Jq13jV6"
        ]

        self.loop = bot.loop.create_task(self.get_q_posts())

# --------------------------------------------------------------------------- #

    @commands.command()
    @checks.is_owner()
    async def qautotweet(self, ctx, state):
        """
            Turns on and off the auto-tweet-Q-drops functionality.            
            USAGE: [p]tweetq <on:off> OR <true:false>
        """
        api = {
            "consumer_key": await self.config.twitter.consumer_key(),
            "consumer_secret": await self.config.twitter.consumer_secret(),
            "access_token": await self.config.twitter.access_token(),
            "access_secret": await self.config.twitter.access_secret(),
            "enabled": False
        }

        if state.lower() == "true" or state.lower() == "on":
            api["enabled"] = True
            await self.config.twitter.set(api)
            await ctx.send("*auto-tweet-q-drops*  `ON`")
        elif state.lower() == "false" or state.lower() == "off":
            api["enabled"] = False
            await self.config.twitter.set(api)
            await ctx.send("*auto-tweet-q-drops*  `OFF`")
        else:
            await ctx.send("ERROR - please enter on/off or true/false")

    @commands.command()
    @checks.is_owner()
    async def qprint(self, ctx):
        """Toggle printing to the console"""
        if await self.config.print():
            await self.config.print.set(False)
            await ctx.send("*console-printing* `OFF`")
        else:
            await self.config.print.set(True)
            await ctx.send("*console-printing* `ON`")

    @commands.command(name="qtwitterset")
    @checks.is_owner()
    async def set_creds(
        self, ctx, consumer_key: str, consumer_secret: str, access_token: str, access_secret: str
    ):
        """Set automatic twitter updates alongside discord"""
        api = {
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret,
            "access_token": access_token,
            "access_secret": access_secret,
            "enabled": True
        }
        await self.config.twitter.set(api)
        await ctx.send("Twitter access credentials saved.")

    @commands.command()
    @checks.is_owner()
    async def qtest(self, ctx):
        """Q drop formatting test"""
        test_data = {
            "no": 9083042,
            "resto": 9082981,
            "com": "<p class=\"body-line ltr \">SHADOW PRESIDENCY.</p><p class=\"body-line ltr \">SHADOW GOVERNMENT.</p><p class=\"body-line ltr \">INSURGENCY.</p><p class=\"body-line ltr \">IRREGULAR WARFARE.</p><p class=\"body-line ltr \">Q</p>",
            "name": "Q ",
            "trip": "!!Hs1Jq13jV6",
            "time": 1588968542,
            "sticky": 0,
            "locked": 0,
            "cyclical": "0",
            "bumplocked": "0",
            "last_modified": 1588968542,
            "id": "4bfaad",
            "sub": "Q Research General #11627: Q Drops Killin The DS Edition"
        }
        await self.post_q(test_data, "TESTING")

    @commands.command()
    @checks.is_owner()
    async def qinit(self, ctx):
        """
            Check for all posts ever created and store them locally on the bot
            to ensure that future posts aren't re-posted. This only works on the bot
            side and will not re-post messages on discord and should only be used
            when setting up the cog brand new.
        """
        total = 0
        await ctx.send("`Searching threads for Q's tripcode...`")

        board_posts = await self.config.boards()
        for board in self.legacy_boards:
            print("[CHECKING] /{}/".format(board))
            try:
                async with self.session.get(
                    "{}/{}/catalog.json".format(self.url, board)
                ) as resp:
                    data = await resp.json()
            except Exception as e:
                print("[ERROR] {}".format(e))
                await ctx.send("`Error grabbing /{}/ --> SKIPPING.`".format(board))
                continue
            
            Q_posts = []
            for page in data:
                for thread in page["threads"]:
                    if await self.config.print():
                        print("[...] /{}/ {}".format(board, thread["no"]))
                    
                    thread_url = "{}/{}/res/{}.json".format(self.url, board, thread["no"])
                    try:
                        async with self.session.get(thread_url) as resp:
                            data = await resp.json()
                    except Exception as e:
                        print("[ERROR] grabbing THREAD JSON {}:\n{}\n{}".format(thread["no"], e, thread_url))
                        await ctx.send("`Error grabbing /{}/`".format(board))
                        continue
                    
                    for post in data["posts"]:
                        if "trip" in post:
                            if post["trip"] in self.trips:
                                post.update({"sub": thread["sub"]})
                                Q_posts.append(post)
                                print("[Q DROP] /{}/ {} {}".format(board, thread["no"], post["trip"]))

            board_posts[board] = Q_posts
            total += len(Q_posts)
            pl = 'drop' if len(Q_posts) == 1 else 'drops'
            await ctx.send("`Found {} {} in /{}/`".format(len(Q_posts), pl, board))

        await self.config.boards.set(board_posts)
        await ctx.send("`DONE: {} Q drops aggregated.`".format(total))

    @commands.command(name="qrole")
    @checks.is_owner()
    async def qrole(self, ctx, state="true", role_name=""):
        """
            Apply @QPOSTS role to get notified whenever a new 
            Q Post comes in.  The role must be created by you.
        """

        if role_name != "":
            await self.config.mention_role_name.set(role_name)
            await ctx.send("*Q notify role changed to:* **`{}`**".format(role_name))

        if state.lower() == "true" or state.lower() == "on":
            guild = ctx.message.guild
            try:
                resp = await self.config.mention_role_name()
                role = [role for role in guild.roles if role.name == resp][0]
                # role = [role for role in guild.roles if role.name == "QPOSTS"][0]
                await ctx.message.author.add_roles(role)
                await self.config.mention_role.set(True)
                await ctx.send("*mention-role*  `ON`")
            except Exception as e:
                await ctx.send("**Role NOT applied.**```ERROR:\n{}```".format(e))
                await ctx.send("```asciidoc\nTry:\n-----\n- Create the '{}' role.\n- Add 'Manage Roles' permission to bot.```".format(await self.config.mention_role_name()))
                await self.config.mention_role.set(False)
                await self.config.mention_role_name.set("QPOSTS")
                await ctx.send("*Q notify role changed to default:* **`QPOSTS`**")
                print("[ERROR] setting q role\n", e)
                return

        elif state.lower() == "false" or state.lower() == "off":
            await self.config.mention_role.set(False)
            await ctx.send("*mention-role*  `OFF`")

        else:
            await ctx.send("ERROR - please enter on/off or true/false")

# --------------------------------------------------------------------------- #

    @commands.command()
    async def qsettings(self, ctx):
        """
            Prints settings for qposts cog.
        """
        em = discord.Embed(colour=discord.Colour.green())
        em.set_author(name="Qposts Settings")

        for channel_id in await self.config.channels():
            try:
                channel = self.bot.get_channel(id=channel_id)
            except Exception as e:
                print(f"[ERROR] getting the qchannel: {e}")
                continue
            if channel is None:
                continue

        time_string = datetime.fromtimestamp(await self.config.last_checked())
        # temp = "ON" if await self.config.twitter.enabled() else "OFF"

        q_chan      =   "`Q Drop Channel:` #{}\n".format(channel)
        not_role    =   "`Notify Role   :` {}\n".format(await self.config.mention_role_name())
        men_role    =   "`Mention Role  :` {}\n".format(await self.config.mention_role())
        q_print     =   "`Console Print :` {}\n".format(await self.config.print())
        auto_tweet  =   "`Auto Tweet    :` {}\n".format(await self.config.twitter.enabled())
        last_ck     =   "`Last Check    :` {} Z".format(time_string.ctime())
        
        em.description = "{}{}{}{}{}{}".format(q_chan, not_role, men_role, auto_tweet, q_print, last_ck)
        await ctx.send(embed=em)

    @commands.command()
    async def qreset(self, ctx):
        """
            Reset the last time we checked for new posts
        """
        await self.config.last_checked.set(0)
        await ctx.send("Qposts reset.")

    @commands.command(aliases=["qpost"])
    async def qbrowse(self, ctx, board="qresearch"):
        """Display latest qpost from specified board"""
        if board not in await self.config.boards():
            await ctx.send("{} is not an available board!")
            return
        qposts = await self.config.boards()
        qposts = list(reversed(qposts[board]))
        await self.q_menu(ctx, qposts, board)

    @commands.command()
    async def qchannel(self, ctx, channel: discord.TextChannel=None):
        """Set the channel for live qposts"""
        if channel is None:
            channel = ctx.message.channel
        # guild = ctx.message.guild
        cur_chans = await self.config.channels()
        if channel.id in cur_chans:
            await ctx.send("{} is already posting new Q posts!".format(channel.mention))
            return
        else:
            cur_chans.append(channel.id)
        await self.config.channels.set(cur_chans)
        await ctx.send("channel set for qposts: `{}`".format(channel.mention))

    @commands.command()
    async def remqchannel(self, ctx, channel: discord.TextChannel=None):
        """Remove qpost updates from a channel"""
        if channel is None:
            channel = ctx.message.channel
        # guild = ctx.message.guild
        cur_chans = await self.config.channels()
        if channel.id not in cur_chans:
            await ctx.send("{} is not posting new Q posts!".format(channel.mention))
            return
        else:
            cur_chans.remove(channel.id)
        await self.config.channels.set(cur_chans)
        await ctx.send("{} set for qposts!".format(channel.mention))

# --------------------------------------------------------------------------- #

    async def authenticate(self):
        """Authenticate with Twitter's API"""
        try:
            auth = tw.OAuthHandler(
                await self.config.twitter.consumer_key(),
                await self.config.twitter.consumer_secret(),
            )
            auth.set_access_token(
                await self.config.twitter.access_token(), await self.config.twitter.access_secret()
            )
            return tw.API(auth)
        except:
            return

    async def send_tweet(self, message: str, file=None):
        """Sends tweets as the bot owners account"""
        try:
            api = await self.authenticate()
            if file is None:
                api.update_status(message)
            else:
                api.update_with_media(file, status=message)
        except:
            return

    async def create_tweet(self, url, text, img_url=None, file_id=None, file_ext=None):
        if await self.config.twitter.enabled():
            if img_url != None:
                try:
                    if await self.config.print():
                        print("sending tweet with image")
                    tw_msg = "{}\n#QAnon\n{}".format(url, text)
                    await self.send_tweet(
                        tw_msg[:280], "data/qposts/files/{}{}".format(file_id, file_ext)
                    )
                except Exception as e:
                    print(f"[ERROR] sending tweet with image: {e}")
                    pass
            else:
                try:
                    if await self.config.print():
                        print("sending tweet")
                    tw_msg = "{}\n#QAnon\n{}".format(url, text)
                    await self.send_tweet(tw_msg[:280])
                except Exception as e:
                    print(f"[ERROR] sending tweet: {e}")
                    pass

    async def get_q_posts(self):
        await self.bot.wait_until_ready()
        print("[START] checking for Q drops")

        while self is self.bot.get_cog("QPosts"):
            board_posts = await self.config.boards()
            for board in self.boards:
                try:
                    async with self.session.get(
                        "{}/{}/catalog.json".format(self.url, board)
                    ) as resp:
                        data = await resp.json()
                except Exception as e:
                    print(f"[ERROR] grabbing /{board}/ CATALOG @")
                    print(f"[URL] {self.url}/{board}/catalog.json")
                    print(e)
                    continue
                Q_posts = []
                if board not in board_posts:
                    board_posts[board] = []
                for page in data:
                    for thread in page["threads"]:
                        thread_time = datetime.utcfromtimestamp(thread["last_modified"])
                        last_checked_time = datetime.fromtimestamp(
                            await self.config.last_checked()
                        )
                        if thread_time >= last_checked_time:
                            try:
                                async with self.session.get(
                                    "{}/{}/res/{}.json".format(self.url, board, thread["no"])
                                ) as resp:
                                    data = await resp.json()
                            except:
                                print("[ERROR] grabbing THREAD {} in board {}".format(thread["no"], board))
                                print(f"{self.url}/{board}/catalog.json")
                                continue
                            for post in data["posts"]:
                                if "trip" in post:
                                    if post["trip"] in self.trips:
                                        post.update({"sub": thread["sub"]})
                                        Q_posts.append(post)
                old_posts = [post_no["no"] for post_no in board_posts[board]]

                for post in Q_posts:
                    if post["no"] not in old_posts:
                        board_posts[board].append(post)
                        # dataIO.save_json("data/qposts/qposts.json", self.qposts)
                        await self.post_q(post, "{}".format(board))
                    for old_post in board_posts[board]:
                        if old_post["no"] == post["no"] and old_post["com"] != post["com"]:
                            if "edit" not in board_posts:
                                board_posts["edit"] = {}
                            if board not in board_posts["edit"]:
                                board_posts["edit"][board] = []

                            board_posts["edit"][board].append(old_post)
                            board_posts[board].remove(old_post)
                            board_posts[board].append(post)
                            await self.post_q(post, "{} {}".format(board, "EDIT"))

            await self.config.boards.set(board_posts)
            if await self.config.print():
                print(str(datetime.now()).split(".")[0] + " [LOOP] checking for Q crumbs...")
            cur_time = datetime.utcnow()
            await self.config.last_checked.set(cur_time.timestamp())
            await asyncio.sleep(60)

    async def get_quoted_post(self, qpost):
        html = qpost["com"]
        soup = BeautifulSoup(html, "html.parser")
        reference_post = []
        for a in soup.find_all("a", href=True):
            try:
                url, post_id = (
                    a["href"].split("#")[0].replace("html", "json"),
                    int(a["href"].split("#")[1]),
                )
            except:
                continue
            async with self.session.get(self.url + url) as resp:
                data = await resp.json()
            for post in data["posts"]:
                if post["no"] == post_id:
                    reference_post.append(post)
        return reference_post

    async def post_q(self, qpost, board):
        em = await self.format_qpost(qpost, board, True)
        reference = await self.get_quoted_post(qpost)
        if reference != []:
            if "tim" in reference[0] and "tim" not in qpost:
                await self.save_q_files(reference[0])
        if "tim" in qpost:
            await self.save_q_files(qpost)
        
        for channel_id in await self.config.channels():
            try:
                channel = self.bot.get_channel(id=channel_id)
            except Exception as e:
                print(f"[ERROR] getting the qchannel: {e}")
                continue
            if channel is None:
                continue
            guild = channel.guild
            if not channel.permissions_for(guild.me).send_messages:
                continue
            if not channel.permissions_for(guild.me).embed_links:
                await channel.send("**ERROR** bot must have permission to embed links")
            try:
                if await self.config.mention_role():
                    msg = "**Q has posted in `/qresearch/` !**"
                    resp = await self.config.mention_role_name()
                    role = [role for role in guild.roles if role.name == resp][0]
                    role = "".join(role.mention for role in guild.roles if role.name == resp)
                    if role != "":
                        await channel.send("{} : {}".format(role, msg), embed=em)
                else:
                    await channel.send("{}".format(msg), embed=em)
                    # await channel.send(embed=em)
            except Exception as e:
                print(f"[ERROR] posting Qpost in {channel_id}: {e}")

    async def q_menu(
        self,
        ctx,
        post_list: list,
        board,
        message: discord.Message = None,
        page=0,
        timeout: int = 30,
    ):
        """menu control logic for this taken from
           https://github.com/Lunar-Dust/Dusty-Cogs/blob/master/menu/menu.py
        """

        qpost = post_list[page]
        em = await self.format_qpost(qpost, board)

        if not message:
            message = await ctx.send(embed=em)
            await message.add_reaction("⬅")
            await message.add_reaction("❌")
            await message.add_reaction("➡")
        else:
            # message edits don't return the message object anymore lol
            try:
                await message.edit(embed=em)
            except discord.errors.HTTPException as e:
                print(e)
                await message.add_reaction("❗")
        check = lambda react, user: user == ctx.message.author and react.emoji in ["➡", "⬅", "❌"]
        try:
            react, user = await self.bot.wait_for("reaction_add", check=check, timeout=timeout)
        except asyncio.TimeoutError:
            await message.remove_reaction("⬅", self.bot.user)
            await message.remove_reaction("❌", self.bot.user)
            await message.remove_reaction("➡", self.bot.user)
            return None
        else:
            numbs = {"back": "⬅", "next": "➡", "exit": "❌"}
            reacts = {v: k for k, v in numbs.items()}
            react = reacts[react.emoji]
            if react == "next":
                next_page = 0
                if page == len(post_list) - 1:
                    # Loop around to the first item
                    next_page = 0
                else:
                    next_page = page + 1
                try:
                    await message.remove_reaction("➡", ctx.message.author)
                except:
                    pass
                return await self.q_menu(
                    ctx, post_list, board, message=message, page=next_page, timeout=timeout
                )
            elif react == "back":
                next_page = 0
                if page == 0:
                    # Loop around to the last item
                    next_page = len(post_list) - 1
                else:
                    next_page = page - 1
                try:
                    await message.remove_reaction("⬅", ctx.message.author)
                except:
                    pass
                return await self.q_menu(
                    ctx, post_list, board, message=message, page=next_page, timeout=timeout
                )
            else:
                return await message.delete()

    async def format_qpost(self, qpost, board, new=False):
        # print(json.dumps(qpost, indent=2))
        max_embed = 1000        
        name = qpost["name"] if "name" in qpost else "Anonymous"
        url = "{}/{}/res/{}.html#{}".format(self.url, board, qpost["resto"], qpost["no"])
        ts = datetime.fromtimestamp(qpost["time"])
        utc = datetime.utcfromtimestamp(qpost["time"])
        tor_url = "{}/{}/res/{}.html#{}".format(self.TORurl, board, qpost["resto"], qpost["no"])     

        utc_time =  '`ZULU:` {}\n'.format(utc)
        time =      '`EST:` {}\n'.format(ts)        
        uid =       '`User ID:` _{}_\n'.format(qpost["id"])
        bread =     '`Bread:` {}\n'.format(qpost["sub"])
        tor =       '`TOR:` {}\n'.format(tor_url)
        link =      '`Link:` {}\n'.format(url)

        em = discord.Embed(colour=discord.Colour.blurple())
        em.set_author(name=name + qpost["trip"], url=url)
        em.set_footer(text="/{}/".format(board))
        em.timestamp = utc
        em.description = '{}{}{}{}{}{}'.format(utc_time, time, uid, bread, tor, link)
        
        html = qpost["com"]
        soup = BeautifulSoup(html, "html.parser")
        text = ""
        for p in soup.find_all("p"):
            if p.get_text() is None:
                text += "paragraph text is NONE"
            if "empty" not in p["class"]:
                text += p.get_text() + "\n"        

        if len(text) > 0:
            if len(text) > max_embed:
                chunks = self.chunks(text, max_embed)
                i = 0
                for chunk in chunks:
                    i += 1
                    em.add_field(name="POST [{}/{}]".format(i, len(chunks)), value="```{}```".format(chunk), inline=False)
            else:
                em.add_field(name="POST", value="```{}```".format(text), inline=False)
        
        if "tim" in qpost:
            file_id = qpost["tim"]
            file_ext = qpost["ext"]
            img_url = "https://media.8kun.top/file_store/{}{}".format(file_id, file_ext)
            em.add_field(name="{}{}".format(qpost["filename"], file_ext), value=img_url)

            if file_ext in [".png", ".jpg", ".jpeg"]:
                em.set_image(url=img_url)
            if new:
                await self.create_tweet(url, text, img_url, file_id, file_ext)
        else:
            if new:
                await self.create_tweet(url, text)

        if "extra_files" in qpost:
            for file in qpost["extra_files"]:
                filename = file["filename"]
                ext = file["ext"]
                tim = file["tim"]
                filename = "{}{}".format(filename, ext)
                file_url = "https://media.8kun.top/file_store/{}{}".format(tim, ext)
                em.add_field(name="{}".format(filename), value=file_url)
        
        reference = await self.get_quoted_post(qpost)
        if reference != []:
            # print(json.dumps(reference, indent=2))
            for post in reference:
                ref_html = post["com"]
                soup_ref = BeautifulSoup(ref_html, "html.parser")
                ref_text = ""
                for p in soup_ref.find_all("p"):
                    if p.get_text() is None:
                        ref_text += "paragraph text is NONE"
                    if "empty" not in p["class"]:
                        ref_text += p.get_text() + "\n"        

                if len(ref_text) > 0:
                    if len(ref_text) > max_embed:
                        chunks = self.chunks(ref_text, max_embed)
                        i = 0
                        for chunk in chunks:
                            i += 1
                            em.add_field(name="{} [{}/{}]".format(str(post["no"]), i, len(chunks)), value="```{}```".format(chunk), inline=False)
                    else:
                        em.add_field(name=str(post["no"]), value="```{}```".format(ref_text), inline=False)
            
            if "tim" in post:
                file_id = post["tim"]
                file_ext = post["ext"]
                img_url = "https://media.8kun.top/file_store/{}{}".format(file_id, file_ext)
                em.add_field(name="{}{}".format(post["filename"], file_ext), value=img_url)

                if "tim" not in qpost:
                    if file_ext in [".png", ".jpg", ".jpeg"]:
                        em.set_image(url=img_url)

            if "extra_files" in post:
                for file in post["extra_files"]:
                    filename = file["filename"]
                    ext = file["ext"]
                    tim = file["tim"]
                    filename = "{}{}".format(filename, ext)
                    file_url = "https://media.8kun.top/file_store/{}{}".format(tim, ext)
                    em.add_field(name="{}".format(filename), value=file_url)

        return em

    async def save_q_files(self, post):
        try:
            file_id = post["tim"]
            file_ext = post["ext"]

            file_path = cog_data_path(self) / "files"
            file_path.mkdir(exist_ok=True, parents=True)
            url = "https://media.8kun.top/file_store/{}{}".format(file_id, file_ext)
            async with self.session.get(url) as resp:
                image = await resp.read()
            with open(str(file_path) + "/{}{}".format(file_id, file_ext), "wb") as out:
                out.write(image)
            if "extra_files" in post:
                for file in post["extra_files"]:
                    file_id = file["tim"]
                    file_ext = file["ext"]
                    url = "https://media.8kun.top/file_store/{}{}".format(file_id, file_ext)
                    async with self.session.get(url) as resp:
                        image = await resp.read()
                    with open(str(file_path) + "/{}{}".format(file_id, file_ext), "wb") as out:
                        out.write(image)
        except Exception as e:
            print(f"Error saving files: {e}")
            pass

# --------------------------------------------------------------------------- #

    def chunks(self, str, n):
        return [str[i:i+n] for i in range(0, len(str), n)]

    def cog_unload(self):
        print("[STOP] checking for Q drops")
        self.bot.loop.create_task(self.session.close())
        print("[CLOSED] session")
