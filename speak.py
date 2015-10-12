# minqlbot - A Quake Live server administrator bot.
# Copyright (C) 2015 Mino <mino@minomino.org>

# This file is part of minqlbot.

# minqlbot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# minqlbot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with minqlbot. If not, see <http://www.gnu.org/licenses/>.

import random
import minqlbot

class speak(minqlbot.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("chat", self.handle_chat)
        self.add_command("iou", self.cmd_iou, usage="<item>")
        self.add_command("sing", self.cmd_sing)
        self.add_command("joke", self.cmd_joke)
        self.add_command("dance", self.cmd_dance)
        self.add_command("why7", self.cmd_why)
        self.add_command("bbf", self.cmd_bbf)
        self.add_command("minkyn", self.cmd_minkyn)
        self.add_command("debug", self.cmd_debug)





    def cmd_debug(self, player, msg, channel):
        if player.clean_name.lower() != 'iouonegirl':
            return


        listt = ['p1', 'p2', 'p3', 'p4', 'p5']
        for n in range(len(listt)):
            string = "Delay {} for player: {}".format(n*2, listt[n])
            self.debug(string)
            self.delay(n*2, lambda: self.msg(string))
        return
        if self.score_backup is None:
            minqlbot.console_print("<none>")
            return

        minqlbot.console_print(str(dir(self.score_backup[0])))
        minqlbot.console_print("\n\ngot it?\n\n")
        for cascore in self.score_backup:
            minqlbot.console_print(str(cascore.player.clean_name))
            minqlbot.console_print("\n")
            minqlbot.console_print(str(cascore.score))

    def cmd_iou(self, player, msg, channel):
        if len(msg) < 2:
            # return minqlbot.RET_USAGE
            channel.reply("^7stands for: I owe you one girl")
        else:
            channel.reply("^5I owe you one ^4{}^5.".format(' '.join(msg[1:])))

    def handle_chat(self, player, msg, channel):
        message = msg

        if player.clean_name.lower() == 'iouonegirl':
            return #minqlbot.console_command("print i'll ignore waht u said")

        if self.contains(msg, "shit"):
            minqlbot.console_print("'{}'\n".format(msg))
            channel.reply("^7Do you need a SHEET of paper, {}?".format(player.clean_name.lower()))

        elif self.contains(msg, "bitch"):
            strings = ["^7Perhaps you meant to say 'female dog'?",
                "^7I'd love to go to the BEACH right now! How about you, {}?"]
            idx = random.randrange(0, len(strings))
            formatted = strings[idx].format(player.clean_name.lower())
            channel.reply(formatted)

        elif self.contains(msg, "fuck"):
            minqlbot.console_command("print " + player)
            channel.reply("^7Watch your language! GOD sees everything!")

        elif self.contains(msg, "rape"):
            strings = ["^7You call that ^1RAPE^7? Where I come from we call that tickling!",
                "^7There are NO breaks on the ^1RAPE ^7train!"]
            idx = random.randrange(0, len(strings))
            channel.reply(strings[idx])

    def cmd_sing(self, player, msg, channel):
        funs = [lambda: channel.reply("^7I am programmed to keep balance, not to sing >.>"),
            lambda: channel.reply("^7I wanna stream, I want to (auto)jump for joy and I want everyone to know!"),
            lambda: channel.reply("^7Face it, no one wants to hear either of us sing..."),
            lambda: channel.reply("^7And I would frag 500 lives, and I would frag 500 more ^^"),
            lambda: channel.reply("^7Estos son Reeboks o son Nikes? ...o son Nikes? Oh yeah!"),
            lambda: channel.reply("^7I'm gonna strafe, strafe, strafe as fast as I can, 'cause I don't wanna be with you again"),
            lambda: channel.reply("^7Mamaa, just fragged a man... Put a railgun against his head, pulled my trigger now he's dead"),
            lambda: channel.reply("^7Ha- I just died by your arms tonight, must have been something you shot."),
            lambda: channel.reply("^7Shot(gunned) through the heart, and you're to blame, honey you give Quake a bad name."),
            ]
        funs[random.randrange(0, len(funs))]()

    def cmd_dance(self, player, msg, channel):
        minqlbot.console_print("'good game!'\n") # komt in console
        minqlbot.console_command("print good game!") # komt in text fields
        if self.score_backup is None:
            return
        min_score = 999
        min_player = "999"

        minqlbot.console_print("--{}!".format(self.score_backup)) # komt in text fields
        for score in self.score_backup:
            if score.score > min_score:
                continue
            min_score = score.score
            min_player = score.player.clean_name

        #minqlbot.console_print("[*] dudududududu!") # komt in text fields
        channel.reply("^7.{} has lowest score: {}".format(score.player.clean_name, score.score))

        #channel.reply("^7I am programmed to keep balance, not to dance -_-")

    def cmd_joke(self, player, msg, channel):
        channel.reply("^7I am programmed to keep balance, not to tell jokes -.-")
        channel.reply("^7Want a joke? Look in the mirror, {}".format(player.clean_name.lower()))

    def cmd_why(self, player, msg, channel):
        channel.reply("^7Because round limit 10 games last too long...")
        channel.reply("^7Shorter games; more maps; more team combinations; less rape; more fun.")

    def cmd_bbf(self, player, msg, channel):
        channel.reply("^7BBF stands for ^3Beer^7, ^5Boobs ^7and ^2Frags^7. PM iouonegirl for an invite!")

    def cmd_minkyn(self, player, msg, channel):
        channel.reply("^7Shut up, M^1i^7nk^1y^7n!")
# helpers
    def contains(self, msg, key):
        return msg.find(key) > -1