# minqlbot - A Quake Live server administrator bot.
# Copyright (C) 2015 Mino <mino@minomino.org>

# This file is a plugin for minqlbot.
# Copyright (C) 2015 iouonegirl

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

import minqlbot
import configparser
import os
import random
import threading
import time
import re
import math

# Don't touch these globals unless you want to sabotage this whole plugin
POOLS = ["regular", "irregular", "unused"]
POOL_REGULAR = 0
POOL_IRREGULAR = 1
POOL_UNUSED = 2

class maps(minqlbot.Plugin):

    def __init__(self):
        super().__init__()

        # Hooks up in this biiitch
        self.add_hook("vote_called", self.handle_vote_called, priority=minqlbot.PRI_HIGH)
        self.add_hook("game_end", self.handle_game_end)
        self.add_hook("game_start", self.handle_game_start)
        self.add_hook("gamestate", self.handle_gamestate)
        self.add_hook("team_switch", self.handle_switch)
        self.add_hook("player_disconnect", self.handle_player_disco)
##        self.add_hook("unload", self.handle_unload)
        self.add_hook("console", self.handle_console)

        # Toggle plugin
        self.add_command(("mapsystem", "mapssystem"), self.cmd_maps_toggle,3, usage="[on|off]")
        self.add_command(("mapscommands", "mapcommands", "mapscmds","mapcmds"), self.cmd_commands)
        self.add_command(("mapsinfo", "mapinfo"), self.cmd_info)
        self.add_command(("skip", "skipmap", "s"), self.cmd_skip)

        # Match alternates between regulars and irregulars
        self.add_command(("nextmap", "nextmaps"), self.cmd_nextmap)
        self.add_command("activemaps", self.cmd_activemaps, usage="regular|irregular")
        self.add_command("resetmaps", self.cmd_resetmaps, 3, usage="regular|irregular")
        self.add_command(("forceothermap", "forcemap"), self.cmd_forcemap, 3)
        self.add_command("forcenext", self.cmd_forcenext, 3, usage="regular|irregular")

        # Database Operations:
        self.add_command(("addmap", "addmaps"), self.cmd_addmap, 5, usage ="regular|irregular|unused MAP1 MAP2 ...")
        self.add_command("mappool", self.cmd_whichpool, usage="MAPNAME")
        self.add_command("listmaps", self.cmd_listmappool, usage="regular|irregular|unused")
        self.add_command("initializemaps", self.cmd_initializemaps, 50)

        # If  the plugin is loaded, it starts as active
        self.plugin_active = True
        self.first_map = True

        # Define the active map pools
        self.active_regular = []
        self.active_irregular = []

        # Start with a usual map first (decided at the end of a match)
        self.usualnext = True
        self.currmap = None
        self.nextmap = None
        self.thread = None

        # Allow players to !skip a map when over 50%
        self.skippers = []

        # Fill active pools with maps from database
        #self.cmd_resetmaps(None, [None, POOLS[POOL_REGULAR]], None)
        #self.cmd_resetmaps(None, [None, POOLS[POOL_IRREGULAR]], None)


    # ##########################################################################
    #
    #                   HOOKS AND HANDLES
    #
    # ##########################################################################

    # Empty this just to be sure it is done completely since last game end.
    def handle_game_start(self, game):
        self.skippers = []

    def handle_game_end(self, game, score, winner):
        if not self.plugin_active:
            return

        if self.usualnext:
            poolname = POOLS[POOL_REGULAR]
            #activecount = len(self.active_regular) # non-db version(older)
            activecount = self.getactivecount(POOL_REGULAR)
            if activecount == 0:
                self.cmd_resetmaps(None, [None, poolname], None)
            if activecount == 0:
                return self.msg("^7No regular maps selected. Please contact a server admin about this issue.")
            #idx = random.randint(0, activecount-1)
            # self.nextmap = self.active_regular.pop(idx) # older
            self.nextmap = self.getnextactive(POOL_REGULAR)

        else:
            poolname = POOLS[POOL_IRREGULAR]
            #activecount = len(self.active_irregular) # non-db version(older)
            activecount = self.getactivecount(POOL_IRREGULAR)
            if activecount == 0:
                self.cmd_resetmaps(None, [None, poolname], None)
            if activecount == 0:
                return self.msg("^7No irregular maps selected. Please contact a server admin about this issue.")
            #idx = random.randint(0, activecount-1)
            #self.nextmap =  self.active_irregular.pop(idx)
            self.nextmap = self.getnextactive(POOL_IRREGULAR)

        self.usualnext = not self.usualnext
        self.delay(6, lambda: self.msg("^7Next {} map: ^6{}^7!".format(poolname, self.nextmap)))
        self.currmap = self.game().short_map

        # vote 1 (which is the map we just played i think
        minqlbot.console_command("vote 1")

        # Reset skippers
        self.skippers = []

        # start the thread OPTIONAL TODO DELAY THIS A BIT
        self.thread = threading.Thread(target=self.threadvote)
        self.delay(15, lambda: self.thread.start())
        self.debug("Map Thread starts in 15s")
        return


    # Atm does nothing. Old Legacy code
    def handle_gamestate(self, idx, config):
        #if idx < 10:
        #    self.debug("Idx[{}], config[{}]".format(idx, config))
        return #disabled this method
        if idx == 3 and config == "Eye To Eye":
            if self.nextmap:
                self.delay(14, lambda: self.msg("^7Going to the next map (^6{}^7) 5 seconds!".format(self.nextmap)))
                self.delay(19, lambda: self.votenextmap())
            else:
                self.msg("^7No map selected. Please restart plugin and submit this issue to an admin.")


    # If a player decides to leave, throw away his potential skip
    def handle_player_disco(self, player, r):
        if not self.plugin_active:
            return

        if player.clean_name.lower() in self.skippers:
            self.skippers.remove(player.clean_name.lower())

        if self.game().state != "in_progress":
            return

        n = self.check_skips_left()
        if n <= 0:
            self.changemap(self.nextmap)

    # This method is just to fuck with minkyn. Kappa
    def handle_console(self, cmd):

        minkyn = self.find_player('minkyn')
        iou = self.find_player('iouonegirl')
        if not (minkyn and iou):
            return

        if minkyn.name in cmd:

            MSGS_NORMAL = ['gunned down by',
                    'ripped up by',
                    'electrocuted by',
                    'railed by',
                    'melted by',
                    'ate',]
            MSGS_HUM = ['machinegunned by',
                    'pummeled by'
                        ]

            minkname = minkyn.name.replace("^", "\^")
            iouname = iou.name.replace("^", "\^")
            PATTERN = '({}).*({}).*({})'.format(minkname,"{}", iouname)

            if re.search(PATTERN.format("|".join(MSGS_NORMAL)), cmd):
                if random.randint(0,8):
                    return
                messages = [
                    ' congratulations on joining the dead club! ',
                    ' ... and now you are dead :3 ',
                    ' iou sends his regards! ',
                    ' thanks for being a good sport :-) ',
                    ' ripperoni pepperoni ',
                    ' i killed you because i love you <3',
                    ' oh my god, I killed Kenny! (sorry not sorry)',
                    " let's take a moment to enjoy this frag ^^ ",
                    ' welcome to the afterlife, have a cookie and wait for respawn '
                    ]
                minkyn.tell(random.choice(messages))


            elif re.search(PATTERN.format("|".join(MSGS_HUM)), cmd):
                if random.randint(0,8) < 5: # skip if 0 1 2 3 4 show if 5 6 7 8
                    return
                messages = [
                    '* hands you a towel to wash the humiliation off *',
                    ' shh, just take the humiliation in... ',
                    ' * iou snickers behind his computer * '
                    ]
                minkyn.tell(random.choice(messages))



    # If a player goes to spec, his skip is not accounted for anymore
    def handle_switch(self, player, old, new):
        if new.startswith("spec") and player.clean_name.lower() in self.skippers:
            self.skippers.remove(player.clean_name.lower())

##
##    # If plugin unloaded stop any threads
##    def handle_unload(self, arg):
##        self.skippers = []
##        if self.threadvote:
##            self.threadvote.stop()
##            self.threadvote = None

    # No map votes if the plugin is active
    def handle_vote_called(self, caller, vote, args):


        # Allow busbot votes
        if caller.clean_name.lower() in [minqlbot.NAME, 'busbot', 'gelenkbusfahrer', 'iouonegirl']:
            return

        # Veto NO if a match is in progress
        if vote == "map" and self.game().state == "in_progress":
            self.vote_no()
            self.msg("^7Minkyn says: don't be a dick, {}".format(str(caller)))
            return

        # Disable map callvotes when the plugin is active
        if vote == "map" and self.plugin_active:
            self.vote_no()

            string = "n ^6{}^7".format(POOLS[POOL_IRREGULAR])
            if self.usualnext:
                string = "^6 {}^7".format(POOLS[POOL_REGULAR])
            self.msg("Auto map rotation enabled. Type !s to skip this map or !mapinfo. Bot will automatically select a{} map next.".format(string))


    # ##########################################################################
    #
    #                           Commands
    #
    # ##########################################################################


    def cmd_activemaps(self, player, msg, channel):
        if len(msg) < 2:
            return minqlbot.RET_USAGE

        if msg[1] not in POOLS[:2]:
            return minqlbot.RET_USAGE

        if msg[1] == POOLS[POOL_REGULAR]:
            if self.getactivecount(POOL_REGULAR) > 15:
                maps = ", ".join(map(self.shorten, self.getactivemaps(POOL_REGULAR)))
            else:
                maps = ", ".join(self.getactivemaps(POOL_REGULAR))
        elif msg[1] == POOLS[POOL_IRREGULAR]:
            if self.getactivecount(POOL_IRREGULAR) > 15:
                maps = ", ".join(map(self.shorten, self.getactivemaps(POOL_IRREGULAR)))
            else:
                maps = ", ".join(self.getactivemaps(POOL_IRREGULAR))

        self.msg("^7The active ^6{}^7 maps are: ^6{}^7.".format(msg[1], maps))


    # Add a map to a pool / move them around
    def cmd_addmap(self, player, msg, channel):
        if len(msg) < 3:
            return minqlbot.RET_USAGE


        pool = msg[1] # poolname

        # If not a known pool, return the usage
        if pool not in POOLS:
            return minqlbot.RET_USAGE

        # For each map given:
        for name in msg[2:]:

            # Get the index of what pool the map was in (-1,0,1,2)
            mappool = self.getmappool(name)

            # If map not in DB table yet...
            if mappool < 0:
                self.msg("^7Map ^6{}^7 is not known to this bot...".format(name))
                continue

            # Map pool is already equal to what is requested
            if mappool == POOLS.index(pool):
                self.msg("^7Map ^6{}^7 already in {} pool.".format(name, pool))
                continue

            # Move map and display it
            self.setmappool(POOLS.index(pool), name)
            self.msg("^7Map ^6{}^7 moved from ^6{}^7 to ^6{}^7.".format(name, POOLS[mappool], pool))

            # NEW DB VERSION DOESNT NEED TO UPDATE LISTS
            return

            # If moved to unused remove from pools
            if pool == POOLS[POOL_UNUSED]:
                if name in self.active_irregular:
                    self.active_irregular.remove(name)
                if name in self.active_regular:
                    self.active_regular.remove(name)

            # if moved to regulars, add it to active pool (and maybe remove from other pool)
            if pool == POOLS[POOL_REGULAR]:
                self.active_regular.append(name)
                if name in self.active_irregular:
                    self.active_irregular.remove(name)

            # if moved to irregulars, add it to active pool (and maybe remove from other pool)
            if pool == POOLS[POOL_IRREGULAR]:
                self.active_irregular.append(name)
                if name in self.active_regular:
                    self.active_regular.remove(name)


    def cmd_commands(self, player, msg, channel):
        commands = ["mapsystem", "nextmap", "s(kip)", "mappool", "activemaps", "resetmaps", "addmaps"]
        commands += ["forcenext", "forceothermap", "listmaps"]
        self.msg("^7The ^6Maps^7 plugin accepts: ^2!{}^7.".format("^7, ^2!".join(commands)))

    def cmd_forcemap(self, player, msg, channel):


        if not self.plugin_active:
            return self.msg("^7Maps plugin is inactive. Turn it on before using this command.")

        # Force from same pool
        if not self.usualnext:
            if self.getactivecount(POOL_REGULAR) == 0:
                self.cmd_resetmaps(None, [None, POOLS[POOL_REGULAR]], None)
            #idx = random.randint(0,len(self.active_regular)-1)
            #self.nextmap = self.active_regular.pop(idx)
            self.nextmap = self.getnextactive(POOL_REGULAR)
        else:
            if self.getactivecount(POOL_IRREGULAR) == 0:
                self.cmd_resetmaps(None, [None, POOLS[POOL_IRREGULAR]], None)
            #idx = random.randint(0,len(self.active_irregular)-1)
            #self.nextmap = self.active_irregular.pop(idx)
            self.nextmap = self.getnextactive(POOL_IRREGULAR)

        currentmap = self.game().short_map

        if self.first_map:
            pool = POOLS[POOL_REGULAR]
            if self.usualnext:
                pool = POOLS[POOL_IRREGULAR]
            self.msg("^7Picking a map from the ^6{}^7 pool...".format(pool))
            self.currmap = self.nextmap
            self.skippers = []
            self.first_map = False
            return self.changemap(self.nextmap)

        # The following older code puts the currentmap back into its active pool
##        if self.usualnext:
##            pool = POOLS[POOL_IRREGULAR]
##            self.active_irregular.append(currentmap)
##        else:
##            pool = POOLS[POOL_REGULAR]
##            self.active_regular.append(currentmap)
        # This can be replaced by one line:
        #self.setmapactive(currentmap)
        #self.msg("^7Put ^6{}^7 back into the active ^6{}^7 pool. Picking new random map...".format(currentmap, pool))
        self.msg("^7Picking new random map...")
        self.skippers = []
        self.changemap(self.nextmap)

    def cmd_forcenext(self, player, msg, channel):
        if len(msg) < 2:
            return minqlbot.RET_USAGE

        if not self.plugin_active:
            return self.msg("^7Maps plugin is inactive. Turn it on before using this command.")

        if msg[1] not in [POOLS[POOL_REGULAR], POOLS[POOL_IRREGULAR]]:
            return minqlbot.RET_USAGE

        self.usualnext =  msg[1] == POOLS[POOL_REGULAR]
        self.msg("^7You've successfully forced the next map to be from the ^6{}^7 pool.".format(msg[1]))

    def cmd_info(self, player, msg, channel):
        self.msg("^7When active, the maps plugin randomly picks the next map from alternating pools.")
        self.msg("^7One pool contains regular maps and the other pool holds irregular maps. (c) Iouonegirl")


    def cmd_initializemaps(self, player, msg, channel):
        create = "CREATE TABLE IF NOT EXISTS Maps ("
        create += " name TEXT NOT NULL, "
        create += " pool INT NOT NULL, "
        create += " active INT DEFAULT 2, "
        create += " PRIMARY KEY (name) "
        create += " );"
        c = self.db_query(create)
        self.db_commit()
        channel.reply("^7Map pool table created (if it did not exist yet)!")

        # load hard map list from maplist.txt
        try:
            script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
            abs_file_path = os.path.join(script_dir, "maplist.txt")
            with open (abs_file_path, "r") as maplist:
                for m in maplist.read().split(", "):
                    insert = "INSERT INTO Maps VALUES (?, ?)"
                    self.db_query(insert, m, POOL_UNUSED)
                    self.db_commit()
                    self.debug("Map {} inserted".format(m))
            self.msg("An hard loaded maps too")
        except Exception as e:
            self.debug("^1{}^7: {}".format(e.__class__.__name__, e))
            self.msg("^7Something went wrong reading the maplist.txt")



    def cmd_listmappool(self, player, msg, channel):
        if len(msg) < 2:
            return minqlbot.RET_USAGE
        # If request pool is not known, return usage
        if msg[1] not in POOLS:
            return minqlbot.RET_USAGE

        pool_id = POOLS.index(msg[1])
        maps = self.getmapsfrompool(pool_id)
        if len(maps) > 15:
            maps = list(map(self.shorten, maps))
        string = "^7, ^6".join(maps)

        self.msg("^7The ^6{}^7 pools are: ^6{}^7.".format(msg[1], string))


    # Toggle map system
    def cmd_maps_toggle(self, player, msg, channel):
        # Report on status
        if len(msg) < 2:
            if self.plugin_active:
                return self.msg("^7Maps system ^6active^7, the bot will automatically select the next maps")
            else:
                return self.msg("^7Maps system ^6inactive^7. You are free to callvote maps.")

        # Toggle it on or off, after checking conditions

        if msg[1] not in ["on", "off"]:
            return minqlbot.RET_USAGE
        if msg[1] == "on" and self.plugin_active:
            return self.msg("^7Maps system is already turned ^6on^7. The bot will control the next maps.")
        if msg[1] == "off" and not self.plugin_active:
            return self.msg("^7Maps system is already turned ^6off^7. Players have to callvote the maps.")

        self.plugin_active = msg[1] == "on"

        if msg[1] == "on":
            self.first_map = self.plugin_active
            #self.cmd_resetmaps(player, ['!resetmaps', POOLS[POOL_REGULAR]], channel)
            #self.cmd_resetmaps(player, ['!resetmaps', POOLS[POOL_IRREGULAR]], channel)
        self.msg("^7Maps controlling system is turned ^6{}^7.".format(msg[1]))


    def cmd_nextmap(self, player, msg, channel):
        string = POOLS[POOL_IRREGULAR]
        if self.usualnext:
             string = POOLS[POOL_REGULAR]

        if self.plugin_active:
            return self.msg("^7The next map is from the ^6{0}^7 pool. (see ^2!activemaps {0}^7).".format(string))
        else:
            return self.msg("^7Controlled map system is turned ^6off^7. Admins can type ^6!mapsystem on^7 to turn it on.")


    # Resets / Loads the maps from the database preference into their respective active pools
    def cmd_resetmaps(self, player, msg, channel):
        if len(msg) < 2:
            return minqlbot.RET_USAGE

        if msg[1] not in POOLS[:2]:
            return minqlbot.RET_USAGE


        if msg[1] == POOLS[POOL_REGULAR]:

            # DB VERSION TAG: ,;:
            self.setpoolactive(POOL_REGULAR)

            maps = self.getmapsfrompool(POOLS.index(msg[1]))
            self.active_regular = []
            for m in maps:
                # Add it to active pool and potentially remove it from other active pool
                self.active_regular.append(m)
                if m in self.active_irregular:
                    self.active_irregular.remove(m)
            self.msg("^7Loaded {} maps into active ^6{}^7 pool!".format(len(maps), msg[1]))

        elif msg[1] == POOLS[POOL_IRREGULAR]:


            # DB VERSION TAG: ,;:
            self.setpoolactive(POOL_IRREGULAR)

            maps = self.getmapsfrompool(POOLS.index(msg[1]))
            self.active_irregular = []
            for m in maps:
                # Add it to active pool and potentially remove it from other active pool
                self.active_irregular.append(m)
                if m in self.active_regular:
                    self.active_regular.remove(m)
            self.msg("^7Loaded {} maps into active ^6{}^7 pool!".format(len(maps), msg[1]))


    def cmd_skip(self, player, msg, channel):

        if not self.plugin_active:
            return self.msg("^7Maps plugin is inactive. Turn it on before using this command.")

        if self.game().state.lower() == "warmup":
            if player.team not in ["red", "blue"]:
                return self.msg("^7Cannot skip from spectator position!")

            if player.clean_name.lower() in self.skippers:
                return self.msg("^7{} already voted to skip this map!".format(player.clean_name))

            self.skippers.append(player.clean_name.lower())

            n = self.check_skips_left()

            if n <= 0:
                return self.cmd_forcemap(None, None, None)

            self.msg("^7Total skips = ^6{}^7, but I need ^6{}^7 more to skip this map.".format(len(self.skippers), n))
        else:
            self.msg("^7Skips only allowed in warmup!")


    def cmd_whichpool(self, player, msg, channel):
        if len(msg) < 2:
            return minqlbot.RET_USAGE

        pool = self.getmappool(msg[1])

        if pool < 0:
            return self.msg("^7This map is not known in the database yet. Please contact a server admin.")

        self.msg("^7Map ^6{}^7 is currently in the ^6{}^7 map pool.".format(msg[1], POOLS[pool]))



# ##########################################################################
#
#                       Helper functions
#
# ##########################################################################

    # Set the pool value of a map in the database
    def setmappool(self, pool, name):
        sql = "UPDATE Maps SET pool = ?, active = ? WHERE name = ?"
        self.db_query(sql, pool, pool, name)
        self.db_commit()
        self.debug("Executing '{}' with {} and {}".format(sql,pool, name))

    # Get the pool value of a map from the database
    def getmappool(self, name):
        sql = "SELECT pool FROM Maps WHERE name = ?"
        c = self.db_query(sql, name)
        row = c.fetchone()
        if not row:
            return -1
        return row[0]

    # HELPERS FOR NEW ACTIVE SYSTEM -------------------
    def setmapinactive(self, name):
        sql = "UPDATE Maps SET active = ? WHERE name = ?"
        self.db_query(sql, POOL_UNUSED, name)
        self.db_commit()

    def setmapactive(self, name):
        pool = self.getmappool(name) or POOL_UNUSED
        sql = "UPDATE Maps SET active = ? WHERE name = ?"
        self.db_query(sql, pool, name)
        self.db_commit()

    def setpoolactive(self, pool):
        sql = "UPDATE Maps SET active = ? WHERE pool = ?"
        self.db_query(sql, pool, pool)
        self.db_commit()

    # Get all the active maps (basically each record that is active)
    def getactivemaps(self, pool):
        sql = "SELECT name FROM Maps WHERE pool = ? AND active = ?"
        c = self.db_query(sql, pool, pool)
        return list(map(lambda row: row[0], c.fetchall()))

    def getactivecount(self, pool):
        sql ="SELECT count(*) FROM Maps WHERE pool = ? AND active = ?"
        c = self.db_query(sql, pool, pool)
        row = c.fetchone()
        if row:
            return row[0]
        return 0

    def getnextactive(self, pool):
        sql = "SELECT name FROM Maps WHERE pool = ? AND active = ? ORDER BY random() LIMIT 1"
        c = self.db_query(sql, pool, pool)
        row = c.fetchone()
        if row:
            self.setmapinactive(row[0]) # We 'take' it away, so set it inactive
            return row[0]
        else:
            self.debug("THIS SHOULDNT HAVE HAPPENED, PLEASE REPORT THIS MESSAGE TO IOUONEGIRL")

    # Get all the maps in a certain map pool
    def getmapsfrompool(self, idx):
        if isinstance(idx, str):
            return self.getmapsfrompool(POOLS.index(idx))
        c = self.db_query("SELECT name FROM Maps WHERE pool = ?", idx)
        return list(map(lambda row: row[0], c.fetchall()))

    # Shorten map names to 8-10 to avoid 10 lines of maps
    def shorten(self, el):
        length = 8
        if len(el) > length:
            return el[:(length-2)] + ".." + el[-1:]
        return el

    # Legacy code i think
    def votenextmap(self):
        # Screw other votes, we're going to ibiza!
        if self.is_vote_active():
            self.vote_no()
        self.currmap = self.nextmap
        self.changemap(self.nextmap)

    # To be called as a thread and bound to self.thread
    # Keeps trying to callvote the map until voting is allowed
    def threadvote(self):

# Code commented because bot vetoed no his own vote -_-
# Don't know why, but if you want to revive this, figure a way to see what the vote is about
# before you shut it down
##        # If some sneaky fucker tries to vote something before us
##        if self.is_vote_active():
##            self.vote_no()
##            self.currmap = self.nextmap
##            self.changemap(self.nextmap)
##            self.thread.stop()
##            self.thread = None
##            return

        # Grey area where we don't know if voting is allowed yet...
        minqlbot.console_command("callvote map {}".format(self.nextmap))
        time.sleep(1)
        if self.is_vote_active() or self.nextmap == self.currmap:
            self.thread.stop()
            self.debug("I could callvote the map!")
            self.currmap = self.nextmap
            self.nextmap = None
            self.thread = None
            self.vote_yes()
            return

        # If we couldnt cast this vote yet try again
        self.debug("Trying again to change map in 3 seconds")
        time.sleep(3)
        self.threadvote()



    def check_skips_left(self):
        have = len(self.skippers)
        teams =  self.teams()
        need = int(math.floor( len(teams["red"] + teams["blue"]) / 2.0 + 1))

        return need - have
