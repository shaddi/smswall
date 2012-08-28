from smswall import *

class CommandError(RuntimeError):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class CommandHandler(object):

    """
    The command handler performs authentication and basic syntax checking for
    commands. We dispatch the command to the right handler, then check whether
    or not the issuer of the command is authorized to execute it. We also
    verify the command has the right number of arguments. The semantics of each
    command should be implemented elsewhere -- we'll check whether or not the
    command is semantically valid where it's defined.

    If command handling fails at any point, we raise a CommandError. The value
    of the exception should be sent as a reply by the calling application.

    TODO: we really should validate arguments here (should all be ints).
    """
    def __init__(self, app):
        self.app = app
        self.conf = app.conf
        self.commands = {"create": self.create_list,
                         "delete": self.delete_list,
                         "help": self.cmd_help,
                         "join": self.join,
                         "leave": self.leave,
                         "makepublic": self.makepublic,
                         "makeprivate": self.makeprivate,
                         "makeopen": self.makeopen,
                         "makeclosed": self.makeclosed,
                         "add": self.add,
                         "remove": self.remove,
                         "addowner": self.addowner,
                         "removeowner": self.removeowner,
                         "setname": self.setname,
                         "confirm": self.confirm
                        }

    app_commands = ["confirm", "create", "delete", "setname"]

    def dispatch(self, message, cmd, arguments, confirmed):
        """ Dispatch a command to the appropriate handler. We check to make
        sure the command exists and is directed to a valid number before
        dispatching.
        """
        # case insensitive -- lowercase is impossible in T9-land!
        cmd = cmd.lower()

        # Don't dispatch non-commands
        if not cmd in self.commands:
            e = "The command '%s' doesn't exist. Try sending 'help' to %s, or call 411 for Information." \
                % (cmd, self.conf.app_number)
            raise CommandError(e)

        # Check if an app number command was sent to the right place
        recp = message.recipient
        app_number = str(self.conf.app_number)
        if cmd in CommandHandler.app_commands and not recp == app_number:
            e = "The command '%s' must be sent to %s." % (cmd, app_number)
            raise CommandError(e)
        elif not cmd in CommandHandler.app_commands and recp == app_number:
            e = "The command '%s' must be sent directly to a list." % (cmd, app_number)
            raise CommandError(e)

        if not arguments:
            arguments = []

        handler_func = self.commands[cmd]
        handler_func(message, cmd, arguments, confirmed)

    def looks_like_command(self, message):
        body = message.body
        has_cmd_char = body.startswith(self.conf.cmd_char)
        if has_cmd_char:
            cmd = body[1:].split()[0].lower()
        elif len(body.split()) >= 1:
            cmd = body.split()[0].lower()
        else:
            return False

        # dispatch() will verify the command actually exists and is sent to the
        # proper number. The goal here is to accept anything that looks like it
        # could have been intended as a command, and then deliver an
        # appropriate error to the user if the command turns out to be
        # malformed.
        is_to_app = str(message.recipient) == str(self.conf.app_number)
        return is_to_app or has_cmd_char or cmd in self.commands.keys()

    def invalid_command(self, command):
        if not command:
            e = "Invalid command. Send 'help' to %s for a list of commands." \
                % (self.conf.app_number)
        else:
            e = "Invalid command. Send 'help %s' to %s for info." % \
                (command, self.conf.app_number)
        raise CommandError(e)

    def create_list(self, message, cmd, args, confirmed):
        """
        This command is sent to the application.
        If list creation is enabled, anyone can create lists.
        """
        if not len(args) == 1:
            self.invalid_command("create")

        l = List(args[0], self.app)
        l.create(message.sender)

    def delete_list(self, message, cmd, args, confirmed):
        """
        This command is sent to the application.
        Only list owners may delete lists, and this must be confirmed.
        """
        if not len(args) == 1:
            self.invalid_command("delete")

        l = List(args[0], self.app)

        if not l.is_owner(message.sender):
            e = "Sorry, you have to own a list to delete it."
            raise CommandError(e)

        l.delete(confirmed)

    def cmd_help(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list or to the application.
        Anyone can ask for help. Should return a list of commands, and if
        there's an argument, should show help for specified command.
        """
        help_strings = {
                        "help": "For more info send 'help <command>' to %s. Available commands: %s. More questions? Call 411." % (self.conf.app_number, ", ".join(self.commands.keys())),
                        "create": "Send 'create <number>' to %s to create a new list with specified number." % self.conf.app_number,
                        "delete": "Send 'delete <number>' to %s to delete a list with specified number. Must be an owner of a list to delete it." % self.conf.app_number,
                        "setname": "Send 'setname <name>' to %s to set your name (displayed when you send messages)." % self.conf.app_number,
                        "join": "Send 'join' to any list to join that list.",
                        "leave": "Send 'leave' to any list to leave that list.",
                        "makepublic": "Send 'makepublic' to any list you're an owner of to allow anyone to join; otherwise, list owners must add members.",
                        "makeprivate": "Send 'makeprivate' to any list you're an owner of to disallow people joining without an owner adding them.",
                        "makeopen": "Send 'makeopen' to any list you're an owner of to allow all members to post to the list.",
                        "makeclosed": "Send 'makeclosed' to any list you're an owner of to only let list owners post to the list.",
                        "remove": "Send 'remove <number>' to any list you're an owner of to remove the specified number from the list.",
                        "add": "Send 'add <number>' to any list you're an owner of to add the specified number to the list.",
                        "addowner": "Send 'addowner <number>' to any list you're an owner of to make the specified number a list owner.",
                        "removeowner": "Send 'removeowner <number>' to any list you're an owner of to remove the specified number as a list owner.",
                        "confirm": "Send 'confirm' to %s to confirm a pending action." % self.conf.app_number
                       }
        if cmd == "help":
            if not args or len(args) == 0:
                help_cmd = "help"
            else:
                help_cmd = args[0]
            if help_cmd in help_strings:
                raise CommandError(help_strings[help_cmd])
        raise CommandError(help_strings["help"])

    def join(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        If the list is public, then anyone can join. If false, owners should
        use the "add" command to add a number to the list.
        """
        if not len(args) == 0:
            self.invalid_command("join")
        l = List(message.recipient, self.app)
        if not l.is_public():
            raise CommandError("Sorry, to join the list '%s' a list owner must add you." % l.shortcode)
        l.add_user(message.sender)

    def leave(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        Anyone can leave a list at any time.
        """
        if not len(args) == 0:
            self.invalid_command("leave")
        l = List(message.recipient, self.app)
        l.delete_user(message.sender)

    def makepublic(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        Only owners can make a list public.
        """
        if not len(args) == 0:
            self.invalid_command("makepublic")
        l = List(message.recipient, self.app)
        if not l.is_owner(message.sender):
            raise CommandError("Sorry, only a list owner may do that.")
        l.set_list_public(True)

    def makeprivate(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        Only owners can make a list private.
        """
        if not len(args) == 0:
            self.invalid_command("makeprivate")
        l = List(message.recipient, self.app)
        if not l.is_owner(message.sender):
            raise CommandError("Sorry, only a list owner may do that.")
        l.set_list_public(False)

    def makeopen(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        Only owners can make a list open.
        """
        if not len(args) == 0:
            self.invalid_command("makeopen")
        l = List(message.recipient, self.app)
        if not l.is_owner(message.sender):
            raise CommandError("Sorry, only a list owner may do that.")
        l.set_owner_only_posting(False)

    def makeclosed(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        Only owners can make a list closed.
        """
        if not len(args) == 0:
            self.invalid_command("makeclosed")
        l = List(message.recipient, self.app)
        if not l.is_owner(message.sender):
            raise CommandError("Sorry, only a list owner may do that.")
        l.set_owner_only_posting(True)

    def setname(self, message, cmd, args, confirmed):
        """
        This command is sent to the app. Used to set the username of a user.
        """
        if not len(args) >= 1:
            self.invalid_command("setname")
        self.app.set_username(message.sender, " ".join(args))

    def add(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        Only owners can add a user to the list.
        """
        if not len(args) == 1:
            self.invalid_command("add")
        l = List(message.recipient, self.app)
        if not l.is_owner(message.sender):
            raise CommandError("Sorry, only a list owner may do that.")
        l.add_user(args[0])

    def remove(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        Only owners can remove a user from the list.
        """
        if not len(args) == 1:
            self.invalid_command("delete")
        l = List(message.recipient, self.app)
        if not l.is_owner(message.sender):
            raise CommandError("Sorry, only a list owner may do that.")
        l.delete_user(args[0])

    def addowner(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        Only owners can add an owner to the list.
        """
        if not len(args) == 1:
            self.invalid_command("addowner")
        l = List(message.recipient, self.app)
        if not l.is_owner(message.sender):
            raise CommandError("Sorry, only a list owner may do that.")
        l.make_owner(args[0])

    def removeowner(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list.
        Only owners can remove an owner from the list.
        """
        if not len(args) == 1:
            self.invalid_command("removeowner")
        l = List(message.recipient, self.app)
        if not l.is_owner(message.sender):
            raise CommandError("Sorry, only a list owner may do that.")
        l.unmake_owner(args[0])

    def confirm(self, message, cmd, args, confirmed):
        """
        Confirm a user action.
        Anyone may confirm their own actions.
        """
        self.app.confirm_action(message.sender)
