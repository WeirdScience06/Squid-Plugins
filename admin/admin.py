import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from __main__ import settings, send_cmd_help
from copy import deepcopy
import asyncio
import logging
import os


log = logging.getLogger("red.admin")


class Admin:
    """Admin tools, more to come."""

    def __init__(self, bot):
        self.bot = bot
        self._announce_msg = None
        self._settings = dataIO.load_json('data/admin/settings.json')
        self._settable_roles = self._settings.get("ROLES", {})

    def _get_selfrole_names(self, server):
        if server.id not in self._settable_roles:
            return None
        else:
            return self._settable_roles[server.id]

    def _role_from_string(self, server, rolename, roles=None):
        if roles is None:
            roles = server.roles
        role = discord.utils.find(lambda r: r.name.lower() == rolename.lower(),
                                  roles)
        try:
            log.debug("Role {} found from rolename {}".format(
                role.name, rolename))
        except:
            log.debug("Role not found for rolename {}".format(rolename))
        return role

    def _save_settings(self):
        dataIO.save_json('data/admin/settings.json', self._settings)

    def _set_selfroles(self, server, rolelist):
        self._settable_roles[server.id] = rolelist
        self._settings["ROLES"] = self._settable_roles
        self._save_settings()

    @commands.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def addrole(self, ctx, rolename, user: discord.Member=None):
        """Adds a role to a user, defaults to author

        Role name must be in quotes if there are spaces."""
        author = ctx.message.author
        channel = ctx.message.channel
        server = ctx.message.server

        if user is None:
            user = author

        role = self._role_from_string(server, rolename)

        if role is None:
            await self.bot.say('That role cannot be found.')
            return

        if not channel.permissions_for(server.me).manage_roles:
            await self.bot.say('I don\'t have manage_roles.')
            return

        if author.id == settings.owner:
            pass
        elif not channel.permissions_for(author).manage_roles:
            raise commands.CheckFailure

        await self.bot.add_roles(user, role)
        await self.bot.say('Added role {} to {}'.format(role.name, user.name))

    @commands.group(pass_context=True, no_pm=True)
    async def adminset(self, ctx):
        """Manage Admin settings"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @adminset.command(pass_context=True, name="selfroles")
    @checks.admin_or_permissions(manage_roles=True)
    async def adminset_selfroles(self, ctx, *, rolelist):
        """Set which roles users can set themselves.

        COMMA SEPARATED LIST (e.g. Admin,Staff,Mod)"""
        server = ctx.message.server
        unparsed_roles = list(map(lambda r: r.strip(), rolelist.split(',')))
        parsed_roles = list(map(lambda r: self._role_from_string(server, r),
                                unparsed_roles))
        if len(unparsed_roles) != len(parsed_roles):
            not_found = set(unparsed_roles) - {r.name for r in parsed_roles}
            await self.bot.say(
                "These roles were not found: {}\n\nPlease"
                " try again.".format(not_found))
        parsed_role_set = list({r.name for r in parsed_roles})
        self._set_selfroles(server, parsed_role_set)
        await self.bot.say(
            "Self roles successfully set to: {}".format(parsed_role_set))

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def announce(self, ctx, *, msg):
        """Announces a message to all servers that a bot is in."""
        if self._announce_msg is not None:
            await self.bot.say("Already announcing, wait until complete to"
                               " issue a new announcement.")
        else:
            self._announce_msg = msg

    @commands.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def removerole(self, ctx, rolename, user: discord.Member=None):
        """Removes a role from user, defaults to author

        Role name must be in quotes if there are spaces."""
        server = ctx.message.server
        author = ctx.message.author

        role = self._role_from_string(server, rolename)
        if role is None:
            await self.bot.say("Role not found.")
            return

        if user is None:
            user = author

        if role in user.roles:
            try:
                await self.bot.remove_roles(user, role)
                await self.bot.say("Role successfully removed.")
            except discord.Forbidden:
                await self.bot.say("I don't have permissions to manage roles!")
        else:
            await self.bot.say("User does not have that role.")

    @commands.command(no_pm=True, pass_context=True)
    async def selfrole(self, ctx, *, rolename):
        """Allows users to set their own role.

        Configurable using `adminset`"""
        server = ctx.message.server
        author = ctx.message.author
        role_names = self._get_selfrole_names(server)
        if role_names is None:
            await self.bot.say("I have no user settable roles for this"
                               " server.")
            return

        roles = list(map(lambda r: self._role_from_string(server, r),
                         role_names))

        role_to_add = self._role_from_string(server, rolename, roles=roles)

        try:
            await self.bot.add_roles(author, role_to_add)
        except discord.errors.Forbidden:
            log.debug("{} just tried to add a role but I was forbidden".format(
                author.name))
            await self.bot.say("I don't have permissions to do that.")
        except AttributeError:  # role_to_add is NoneType
            log.debug("{} not found as settable on {}".format(rolename,
                                                              server.id))
            await self.bot.say("That role isn't user settable.")
        else:
            log.debug("Role {} added to {} on {}".format(rolename, author.name,
                                                         server.id))
            await self.bot.say("Role added.")

    @commands.command(no_pm=True, pass_context=True)
    async def say(self, ctx, *, text):
        """Repeats what you tell it.

        Can use `message`, `channel`, `server`, and `discord`
        """
        user = ctx.message.author
        if hasattr(user, 'bot') and user.bot is True:
            return
        try:
            evald = eval(text, {}, {'message': ctx.message,
                                    'channel': ctx.message.channel,
                                    'server': ctx.message.server,
                                    'discord': discord})
        except:
            evald = text
        if len(str(evald)) > 2000:
            evald = str(evald)[-1990:] + " you fuck."
        await self.bot.say(evald)

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def sudo(self, ctx, user: discord.Member, *, command):
        """Runs the [command] as if [user] had run it. DON'T ADD A PREFIX
        """
        new_msg = deepcopy(ctx.message)
        new_msg.author = user
        new_msg.content = self.bot.command_prefix[0] + command
        await self.bot.process_commands(new_msg)

    async def announcer(self, msg):
        server_ids = map(lambda s: s.id, self.bot.servers)
        for server_id in server_ids:
            if self != self.bot.get_cog('Admin'):
                break
            server = self.bot.get_server(server_id)
            if server is None:
                continue
            chan = server.default_channel
            log.debug("Looking to announce to {} on {}".format(chan.name,
                                                               server.name))
            me = server.me
            if chan.permissions_for(me).send_messages:
                log.debug("I can send messages to {} on {}, sending".format(
                    server.name, chan.name))
                await self.bot.send_message(chan, msg)
            await asyncio.sleep(1)

    async def announce_manager(self):
        while self == self.bot.get_cog('Admin'):
            if self._announce_msg is not None:
                log.debug("Found new announce message, announcing")
                await self.announcer(self._announce_msg)
                self._announce_msg = None
            await asyncio.sleep(1)


def check_files():
    if not os.path.exists('data/admin/settings.json'):
        try:
            os.mkdir('data/admin')
        except FileExistsError:
            pass
        else:
            dataIO.save_json('data/admin/settings.json', {})


def setup(bot):
    check_files()
    n = Admin(bot)
    bot.add_cog(n)
    bot.loop.create_task(n.announce_manager())
