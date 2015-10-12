# Copyright (C) WalkerY (github) aka WalkerX (ql)

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

"""Displays player info."""

import minqlbot
import plugins.qlprofile as qlprofile
import threading
import datetime

class player_info(minqlbot.Plugin):
    def __init__(self):
        super().__init__()
        self.add_command("info", self.cmd_info, 0, usage="[<name>]")
        
    def cmd_info(self, player, msg, channel):
        playername = ""
        if len(msg) < 2:
            # return minqlbot.RET_USAGE
            playername = player.clean_name.lower()
        elif len(msg) < 3:
            playername = msg[1]
        else:
            return minqlbot.RET_USAGE
            
        player_ = self.find_player(playername)
        if player_:
            name = player_.clean_name.lower()
        else:
            name = self.clean_text(playername).lower()
            
        threading.Thread(target=self.get_profile_thread, args=(name, channel)).start()
        
    def get_profile_thread(self, name, channel):
        try:
            profile = qlprofile.get_profile(name.lower())
            
            created_date = profile.get_date()
            today = datetime.date.today()
            delta = today - created_date
            wins = int(profile.wins.replace(",",""))
            quits = int(profile.quits.replace(",",""))
            losses = int(profile.losses.replace(",",""))
            if wins + losses + quits == 0:
                games_total_p = 1
            else:
                games_total_p = wins + losses + quits
            
            info = ["^7created ^6{} days ago".format(delta.days),
                    "^7total games ^6{}".format(wins + quits + losses),
                    "^7total quit frequency ^6{} percent".format(round(quits/(games_total_p)*100))]
                    
            c = self.db_query("SELECT * FROM Players WHERE name=?", name.lower())
            row = c.fetchone()
            if row:
                completed = row["games_completed"]
                left = row["games_left"]
                if not completed:
                    completed = 0
                if not left:
                    left = 0
                    
                if left + completed == 0:
                    games_here_p = 1
                else:
                    games_here_p = left + completed                                

                info += ["^7games here ^6{}".format(completed + left),
                        "^7quit frequency here ^6{} percent".format(round(left/(games_here_p)*100))]
            else:
                info += ["^7games here ^60",
                        "^7quit frequency here ^60 percent"]

            channel.reply("^7Account ^6{}^7: ".format(name) + "^7, ".join(info))
        except:
            e = traceback.format_exc().rstrip("\n")
            debug("========== ERROR: {}@get_profile_thread ==========".format(self.__class__.__name__))
            for line in e.split("\n"):
                debug(line)
 
        
