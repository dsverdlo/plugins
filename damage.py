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
import threading
import time

# View all damages in BOT console? 1-yes, 0-no
LIST_ALL_CONSOLE = 1
# Perm lvl to (un)set this for other players
OVERRIDE_PERM_LVL = 5
# Length of the TOP list (max 5)
TOP = 5
CHANGE_TOP_PERM_LVL = 5
# Show least dmg and most dmg of last round?
SHOW_LAST_ROUND = True
# Amount of matches needed to be completed on server before top damages are recorded
COMPLETED_MATCHES = 10

class damage(minqlbot.Plugin):
    def __init__(self):
        super().__init__()
        self.add_command("dmg", self.cmd_tellme, usage="[<username>]")
        self.add_command("nodmg", self.cmd_donttellme, usage ="[<username>]")
        self.add_command(("initializedamage", "initdmg"), self.cmd_initialize, 3)
        self.add_command("topsize", self.cmd_list_size)
        self.add_command(("damageinfo", "dmginfo"), self.cmd_dmg_info)
        self.add_command("topinfo", self.cmd_top_info)
        self.add_command("topdmg", self.cmd_top_damage, usage="[NAME]")
        self.add_command(("wipetopdmg", "removetopdmg"), self.cmd_remove_top, 5, usage="NAME MAP|all")
        self.add_command("maptopdmg", self.cmd_maptopdmg, usage="[MAPNAME]") # needs perm?
        self.add_command("alltopdmg", self.cmd_alltopdmg) # needs perm?
        self.add_command("dmgcmds", self.cmd_dmg_cmds)
        self.add_command("hc", self.cmd_set_handicap, 3, usage="[NAME [AMOUNT(0-200)]")
        self.add_command("hcs", self.cmd_list_handicaps, 3)
        self.add_command("wipehc", self.cmd_clear_handicaps, 3)
        self.add_hook("team_switch", self.handle_team_switch)
        self.add_hook("scores", self.handle_scores)
        self.add_hook("round_end", self.handle_round_end)
        self.add_hook("game_start", self.handle_game_start)
        self.add_hook("game_end", self.handle_game_end)

        # This will keep track of the latest scores updates
        self.scores_live = []

        # A frozen snapshot of the damages until the round ends
        # Format example: { 'iouonegirl':['red', 200], 'minkyn':['blue',50] }
        self.scores_snapshot = {}

        # Accumulate usefull damage counters for top 3
        self.scores_usefull = {}

        # When a round ends this flag will be set to the winner
        # It indicates that we have invoked the last score update of a round
        self.flag = ''

        # Cache of amount of completed games on the server
        self.cache_completed = {}

        # Dictionary of handicaps for the match {NAME: HC, NAME: HC, ...}
        self.handicaps = {}

        # At the start of a game these values will be loaded from the DB
        # or when the plugin is (re)loaded during a match
        try:
            self.top_damages = self.db_get_top_damages(self.game().short_map)
        except:
            pass


    def handle_game_start(self, game):
        self.scores_live = []
        self.scores_snapshot = {}
        self.scores_usefull = {}
        self.flag = ''
        self.cache_completed = {}
        self.top_damages = self.db_get_top_damages(self.game().short_map)


    def handle_game_end(self, game, score, winner):

        self.msg("^7Top {} useful damages:".format(min(len(self.scores_usefull), TOP)))

        strings = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th", "11th", "12th", "13th", "14th"]

        says = []

        # List the minimum of the topsize and the amount of players
        for i in range(min(len(self.scores_usefull), TOP)):

            # If there are no more players left, break
            if len(self.scores_usefull) == 0:
                break

            # Otherwise pop the next name with highest damage
            name = max(self.scores_usefull, key=lambda el: self.scores_usefull[el][1])
            team, dmg = self.scores_usefull.pop(name)
            tc = self.get_team_color(team)

            # Tell players how many more matches they need to play before recording top scores
            games_completed = self.get_completed_matches(name) + 1 # cached is 1 match behind
            if games_completed == COMPLETED_MATCHES:
                player_ = self.find_player(name)
                if player_:
                    player_.tell("You've completed enough matches to contest for highest damage! Good luck!")
                else:
                    minqlbot.console_command("Tell {} You've completed enough matches to contest for highest damage! Good luck!".format(name))
            elif games_completed < COMPLETED_MATCHES:
                left = COMPLETED_MATCHES - games_completed
                player_ = self.find_player(name)
                if player_:
                    player_.tell("You need to complete {} more matches before your top scores are recorded.".format(left))
                else:
                    minqlbot.console_command("Tell {} You need to complete {} more matches before your top scores are recorded.".format(name, left))
            # Wipe the match caches because they wouldnt be accurate anymore
            self.cache_completed.clear()

            # Append name and damage in color of team
            say = "^2{} place^7: {} (^{}{}^7)".format(strings[i], name, tc, dmg)

            # Say the messages with a small delay to get the order right
            says.append(say)
            self.delay(i*1.5, self.msg, args=(say,))

##        threading.Thread(target=self.print_top_list, args=(self, says)).start()
##
##    def print_top_list(self, this, messages):
##        for m in messages:
##            this.msg(str(m))
##            time.sleep(1)


    def cmd_list_size(self, player, msg, channel):
        global TOP

        # Get the list size
        if len(msg) < 2:
            return channel.reply("^7{}, the current damage list is a ^6TOP {}^7.".format(player.clean_name.lower(), str(TOP)))

        # Set it (needs permission)
        perm = self.get_permission(player.clean_name.lower())
        if perm == None or perm < CHANGE_TOP_PERM_LVL:
            if perm == None:
                perm = 0
            return channel.reply("^7Player ^6{}^7 only has permission level ^6{}^7 when level ^6{}^7 is needed.".format(player.clean_name.lower(), str(perm), CHANGE_TOP_PERM_LVL))

        newTOP = int(msg[1])

        if TOP == newTOP:
            return channel.reply("^The damage list already is a ^6TOP {}^7.".format(str(TOP)))

        if newTOP < 1:
            return channel.reply("^7Problem: the damage list must be at least a ^6TOP 1^7.")

        if newTOP > 14:
            return channel.reply("^7Problem: the damage list can be at most a ^6TOP 14^7.")

        TOP = newTOP
        channel.reply("^7Damage list changed to a ^6TOP {}^7.".format(str(TOP)))


    # Continuously updated scores are stored in self.scores_live.
    # If a flag was raised because of the end of a round, calculate the differences
    def handle_scores(self, scores):

        # Update scores
        self.scores_live = scores

        # If there is no flag set, it's not the end of a round yet
        if not self.flag:
            return

        winner = self.flag
        losers = 'redblue'.replace(winner, '')

        self.flag = '' # Reset flag for next time

        # Calculate if we are in a special case
        amount_of_rounds = (self.game().red_score + self.game().blue_score)
        special_case =  (self.scores_snapshot == {}) and (amount_of_rounds > 1)
        # After the loop that creates the snapshot is done, end the calculations

        if LIST_ALL_CONSOLE:
            minqlbot.console_print("^7> Round ended. Here are the damage results:\n")

        # Store the current damage differences from this round in this dict
        round_diffs = []

        # Store the messages for personal damages, so we can display it after the lowest-highest message
        personal_messages = []

        # This loop will create the snapshot of the round scores/damages for next round
        for s in self.scores_live:

            # ignore players that are not actively playing
            if s.team not in ['red', 'blue']:
                continue

            # Iteration variables
            name = s.player.clean_name.lower()
            team = s.team
            prev_dmg = self.get_player_score(name)
            curr_dmg = s.damage_done
            diff = curr_dmg - prev_dmg
            tc = self.get_team_color(team)
            matches_completed = self.get_completed_matches(name)
            bool_matches_required = matches_completed >= COMPLETED_MATCHES

            if LIST_ALL_CONSOLE:
                minqlbot.console_print("^7> ^{}{}^7: {} damage\n".format(tc, name, diff))

            # Make sure the player is known in the usefull damages counter, starting with 0.
            # Partly to evade a try/catch statement, partly so 0 damages can be shown
            if not self.scores_usefull.get(name):
                self.scores_usefull[name] = [team, 0]

            # If the player is in the winning team, count the usefull damage for after the game
            # and it's not the special case, because it wouldnt be fair to the players
            # that won the round just after the plugin was restarted
            if team == winner and not special_case:
                val = self.scores_usefull[name]
                previous_usefull_damage = val[1]

                # Note that this sets the team to where the user is in now.
                # If he switched teams, the usefull damage will be switched with him
                self.scores_usefull[name] = [winner, previous_usefull_damage + diff]

            # Store the difference for calculations after the iteration
            # Handicapped people need to have their differences recalculated
            if self.handicaps.get(name):
                diff = self.calculate_handicap(diff, self.handicaps[name])
            round_diffs.append([name, team, diff, bool_matches_required])
            # Add it to the snapshot to compare it to the next time.
            self.scores_snapshot[name] = [team, curr_dmg]


        # SPECIAL CASE: plugin was reloaded during a game:
        # scores snapshot would have been empty, but it wasn't be the first round
        if special_case:
            # Ignore this round because the game is on and plugin was reloaded
            self.msg("^7Skipping damage calculations since plugin was restarted mid-game...")
            # But do save the current scores for the next end of round:
            return

        # Now iterate over differences to find greatest and lowest values
        lowest_names = []
        lowest_dmg = 9000
        highest_names = []
        highest_dmg = -1

        round_diffs.sort(key=lambda el: el[2], reverse = True) # sort on damage high>low

        # Find highest damage doers for winning team
        for record in round_diffs:
            name, team, diff, bool_matches_required = record
            tc = self.get_team_color(team)

            # Highest damage doer for winning team:
            if team == winner and diff > highest_dmg:
                highest_names = [[tc,name]]
                highest_dmg = diff
            elif team == winner and diff == highest_dmg:
                highest_names.append([tc,name])

            # Lowest from losing team
            if team == losers and diff < lowest_dmg:
                lowest_names = [[tc,name]]
                lowest_dmg = diff
            elif team == losers and diff == lowest_dmg:
                lowest_names.append([tc,name])

            # Also check if the highest damage is a top record for the map
            curr_map = self.game().short_map
            bool_still_space = len(self.top_damages) < 10
            # If there isnt still space, we are able to always get index [-1] (lowest one)
            if (team == winner) and bool_matches_required and (bool_still_space or (diff > self.top_damages[-1]['dmg'])):


                # If we are only here because we are filling this map up (<10)
                # Just insert it and make no big deal about it
                if bool_still_space:
                    self.db_insert_top_damage(name, curr_map, diff)
                    self.top_damages = self.db_get_top_damages(curr_map)
                else:

                    lowest_top = self.top_damages[-1]

                    # Insert into database. If False then not inserted, but continue
                    if not self.db_insert_top_damage(name, curr_map, diff):
                        continue
                    # Remove lowest value
                    # commented out because we'll just accumulate these values in the DB
                    # self.db_remove_top_damage(lowest_top['name'], curr_map, lowest_top['dmg'])
                    # Update the top damages for this map
                    self.top_damages = self.db_get_top_damages(curr_map)

                    for el in self.top_damages:
                        if el['name'] == name and el['dmg'] == diff:
                            pos = self.top_damages.index(el)
                            #self.msg("^7Player ^2{}^7's damage (^3{}^7) earned position ^2{}^7 in the top list for this map!".format(name, diff, pos+1))
                            personal_messages.append("^7Player ^2{}^7's damage (^3{}^7) earned position ^2{}^7 in the top list for this map!".format(name, diff, pos+1))
                            break

            # If winning team (and completed matches required), check if this is a personal best:
            if team == winner and bool_matches_required:
                player_prev_top, mapname = self.db_get_top_damage_for_players(name)
                if player_prev_top > 0 and  diff > player_prev_top:
                    #self.msg("^7New ^2personal^7 record for ^6{}^7: ^3{}^7 useful damage!".format(name, diff))
                    personal_messages.append("^7New ^6personal^7 record for ^2{}^7: ^3{}^7 useful damage!".format(name, diff))


            if self.get_tell_preference(name) == 1:
                self.debug("Trying to tell {} his score({}) ".format(name,diff))
                player_ = self.find_player(name)
                if player_:
                    player_.tell("You have done {} damage this round.".format(diff))
                else:
                    minqlbot.console_command("tell {} You have done {} damage this round.".format(name, diff))


        # If SHOW_LAST_ROUND is turned off and we hit last round, we don't display last message
        if  not SHOW_LAST_ROUND and self.game().roundlimit in self.game().scores:
            return

        # Shame/Praise those people:
        say = "^7Least dmg: {} ({})  --  Most dmg: {} ({})"
        self.msg(say.format(self.pretty_print(lowest_names), lowest_dmg, self.pretty_print(highest_names), highest_dmg))

        # Then display the (personal) messages
        personal_messages.reverse()
        for record in personal_messages:
            self.delay(0.8, self.msg, args=(record,))



    # At the end of a round, set flag compare the scores
    def handle_round_end(self, round, winner):
        self.flag = winner
        # Remind bot to update scores
        minqlbot.Plugin.scores()


    # Set the record to 1 in the database. If they are not in the db yet, add them
    def cmd_tellme(self, player, msg, channel):
        name = player.clean_name.lower()

        # If an admin wants to set this for an other player:
        if len(msg) > 1:
            targetname = msg[1] # TODO: substring findplayer

            # if player redundantly calls this for himself: redirect
            if targetname == name:
                return self.cmd_tellme(player, [], channel)

            # Otherwise check if source user has permission to do this
            n = self.return_permission(player.clean_name.lower())
            if (n >= OVERRIDE_PERM_LVL) or (name == minqlbot.NAME.lower()):
                name = targetname
            else:
                return channel.reply("^7Sorry, but you need a permission level ^6{}^7 or higher to perform this action.".format(OVERRIDE_PERM_LVL))


        pref = self.get_tell_preference(name)
        if pref < 0:
            self.db_query("INSERT INTO Damages VALUES(?, 1)", name)
            self.db_commit()
            channel.reply("^6{}^7 will now see their damage after every round.".format(name))
        else:
            self.db_query("UPDATE Damages SET dmg = 1 WHERE name = ? ",name)
            self.db_commit()
            channel.reply("^6{}^7 will now see their damage after every round.".format(name))



    # !nodmg
    def cmd_donttellme(self, player, msg, channel):
        name = player.clean_name.lower()

        # If an admin wants to set this for an other player:
        if len(msg) > 1:
            targetname = msg[1] # TODO: substring findplayer

            # if player redundantly calls this for himself: redirect
            if targetname == name:
                return self.cmd_donttellme(player, [], channel)

            # Otherwise check if source user has permission to do this
            n = self.return_permission(player.clean_name.lower())
            if (n >= OVERRIDE_PERM_LVL) or (name == minqlbot.NAME.lower()):
                name = targetname
            else:
                return channel.reply("^7Sorry, but you need a permission level ^6{}^7 or higher to perform this action.".format(OVERRIDE_PERM_LVL))

        pref = self.get_tell_preference(name)
        if pref < 0:
            self.db_query("INSERT INTO Damages VALUES(?, 0)", name)
        else:
            self.db_query("UPDATE Damages SET dmg = 0 WHERE name = ? ",name)
        self.db_commit()
        channel.reply("^6{}^7 will stop seeing their damage after every round.".format(name))


    def cmd_initialize(self, player, msg, channel):
        create = "CREATE TABLE IF NOT EXISTS Damages ("
        create += " name TEXT NOT NULL, "
        create += " dmg INT NOT NULL, "
        create += " PRIMARY KEY (name), "
        create += " FOREIGN KEY(name) REFERENCES Players(name) ON DELETE CASCADE "
        create += " );"
        c = self.db_query(create)
        self.db_commit()

        hiscores = "CREATE TABLE IF NOT EXISTS TopDamages ("
        hiscores += " username TEXT NOT NULL, "
        hiscores += " mapname TEXT NOT NULL, "
        hiscores += " dmg INT NOT NULL, "
        hiscores += " FOREIGN KEY (username) REFERENCES Players(name) ON DELETE CASCADE "
        hiscores += " );"
        c = self.db_query(hiscores)
        self.db_commit()

        channel.reply("^7Done initializing damage plugin!")

    def cmd_dmg_info(self, player, msg, channel):
        channel.reply("^7After rounds, the least damage of the lost team and the most damage of the winner team are shown.")
        self.delay(1, lambda: channel.reply("^7You can choose if I PM you your damage after every round by typing ^6!dmg^7 or ^6!nodmg^7."))

    # List the active known handicapped players
    def cmd_list_handicaps(self, player, msg, channel):
        handicaps = []
        for name in self.handicaps:
            handicaps.append("^2{}^7-^5{}^7".format(name, self.handicaps[name]))
        channel.reply("^7Current handicaps: ^6{}^7.".format(", ".join(handicaps)))

    # Remove all the handicaps!
    def cmd_clear_handicaps(self, player, msg, channel):
        self.handicaps = []
        channel.reply("^7All current handicaps cleared!")

    # Handle a !hc call
    # !hc --> get the handicap of caller
    # !hc 50 --> set the handicap of caller
    # !hc iou --> get the handicap of iou
    # !hc iou 50 --> set the handicap of iou
    #
    def cmd_set_handicap(self, player, msg, channel):
        if len(msg) < 2: # No args, return callers hc
            name = player.clean_name.lower()
            hc = self.handicaps.get(name)
            if hc:
                channel.reply("^7Player ^6{} ^7 is playing with handicap: ^6{}^7.".format(name, hc))
            else:
                channel.reply("^7Player ^6{} ^7does not have a handicap registered.".format(name))
        elif len(msg) < 3:
            try: # Set the handicap of the caller if an int was given
                hc = int(msg[1])

                if hc < 0 or hc > 200:
                    return minqlbot.RET_USAGE

                name = player.clean_name.lower()
                self.handicaps[name] = hc
                channel.reply("^7Player ^6{}^7's handicap has been set to: ^6{} ^7.".format(name, hc))

            except: # Get the handicap of specified player

                player_ = self.find_player(msg[1].lower())
                if player_:
                    name = player_.clean_name.lower()
                else:
                    # If we can't find the player on the server, return
                    return channel.reply("^7No player found with the name: ^6{}^7.".format(msg[1]))

                hc = self.handicaps.get(name)
                if hc:
                    channel.reply("^7Player ^6{} ^7is playing with a handicap of ^6{}^7.".format(name, hc))
                else:
                    channel.reply("^7Player ^6{} ^7 is currently not playing with a handicap.".format(name))
        elif len(msg) < 4:
            # Set the handicap of the caller

            try:
                hc = int(msg[2])

                if hc < 0 or hc > 200:
                    raise

                player_ = self.find_player(msg[1])
                if not player_:
                    raise

                name = player_.clean_name.lower()
                self.handicaps[name] = hc
                channel.reply("^7Player ^6{}^7's handicap has been set to ^6{}^7.".format(name, hc))

            except:
                # If 2nd argument is not an integer, return usage
                return minqlbot.RET_USAGE
        else:
            return minqlbot.RET_USAGE


    def cmd_top_info(self, player, msg, channel):
        channel.reply("^7Only when you win a round, your damage done is considered useful and accumulated.")
        self.delay(1, lambda: channel.reply("^7The top {} list at the end of a match displays the players with the highest useful damages done.".format(TOP)))

    # Show the highest recorded damage for an optionally specified target
    def cmd_top_damage(self, player, msg, channel):
        name = player.clean_name.lower()
        if len(msg) == 2:
            name = msg[1].lower()

        #If a player doesnt have enough completed matches, till him how many more
        games_completed = self.get_completed_matches(name)
        if games_completed < COMPLETED_MATCHES:
            left = COMPLETED_MATCHES - games_completed
            self.msg("^7Player ^2{}^7 needs to complete ^2{}^7 more matches before top scores are recorded.".format(name, left))
            return

        # Get the highest damage for this player
        top_dmg, mapp = self.db_get_top_damage_for_players(name)
        if top_dmg < 0:
            channel.reply("^7Player ^2{}^7 has no entries in the TopDamages database table.".format(name))
        else:
            channel.reply("^7Player ^2{}^7's highest recorded damage is: ^3{}^7 on map ^5{}^7.".format(name, top_dmg, mapp))

    # Remove a player from the top
    def cmd_remove_top(self, player, msg, channel):
        if len(msg) < 3:
            return minqlbot.RET_USAGE

        self.db_remove_player(msg[1], msg[2])

    # Dmg commands
    def cmd_dmg_cmds(self, player, msg, channel):
        cmds = ['dmg', 'nodmg', 'dmginfo', 'topsize', 'topdmg', 'topinfo', 'maptopdmg', 'alltopdmg', 'dmginfo']
        channel.reply("^7Damage commands: ^2!{}^7.".format("^7, ^2!".join(cmds)))

    # Display the top damages for a map
    def cmd_maptopdmg(self, player, msg, channel):
        if len(msg) == 2:
            mapname = msg[1]
        else:
            mapname = self.game().short_map

        top_dmgs = self.db_get_top_damages(mapname)
        self.msg("^7Top damages for ^6{}^7: ^8[^7{}^8]^7.".format(mapname, self.pretty_print_dmgs(top_dmgs)))

    # Display overall best damages:
    def cmd_alltopdmg(self, player, msg,channel):
        tops = self.db_get_top_damages()
        self.msg("^7All-time Bus Station damage records:")
        self.msg("^8[^7{}^8]^7.".format(self.pretty_print_dmgs(tops, True)))
##        threading.Thread(target=self.thread_list_top, args=(self, tops)).start()

    # If a player enters a team, set his snapshot dmg to 0
    # Otherwise he could get a negative accumulation
    def handle_team_switch(self, player, old_team, new_team):
        if new_team != "spectator":
            name = player.clean_name.lower()
            if self.scores_snapshot.get(name):
                self.scores_snapshot[name] = [new_team, 0]

# ################################
#
# HELPER FUNCTIONS
#
# ################################
    def pretty_print(self, names):
        colored_names = []
        for tc,name in names:
            colored_names.append("^{}{}^7".format(tc,name))
        return ', '.join(colored_names)

    def pretty_print_dmgs(self, top_damages, show_maps = False):
        formatted = []
        for i in range(len(top_damages)):
            dmg = top_damages[i]
            extra = ""
            if show_maps:
                extra = "^8-^5{}^7".format(dmg['map'])
            formatted.append("^7{}^8-^3{}^8-^2{}".format(i+1, dmg['name'], dmg['dmg']) + extra)
##            formatted.append("^7{}^8:^3{}^8(^2{}^8)".format(i+1, dmg['name'], dmg['dmg']) + extra)
        return '^8] [^7'.join(formatted)

    # Displaying colors for teams
    def get_team_color(self, team):
        if team == 'red':
            return 1
        elif team == 'blue':
            return 4
        else:
            return 7

    # Try to get a score from the snapshot. Return 0 if fail
    def get_player_score(self, player):
        try:
            team,dmg = self.scores_snapshot[player]
            return dmg
        except:
            return 0

    def thread_list_top(self, cls, tops):
        self.debug("Arrived in thread")
        for top in tops:
            i = tops.index(top)
            cls.msg("^2{}^7: ^3{}^7 - ^2{} dmg^7 - ^5{}^7.".format(i+1, top['name'], top['dmg'], top['map']))
            time.sleep(1)

    def get_tell_preference(self, name):
        c = self.db_query("SELECT dmg FROM Damages WHERE name = ? ",name)
        row = c.fetchone()
        if not row:
            return -1
        return row[0]

    def return_permission(self, user):
        minqlbot.console_print("User: {}".format(user))
        c = self.db_query("SELECT permission FROM Players WHERE name = ?", user)
        row = c.fetchone()
        if not row:
            return 0
        else:
            return row[0]

    # This method gets the highest dmg of a player's top scores
    def db_get_top_damage_for_players(self, username):
        c = self.db_query("SELECT dmg, mapname FROM TopDamages WHERE username = ? ORDER BY dmg DESC LIMIT 1",username)
        row = c.fetchone()
        if not row:
            return [-1, None]
        return [row[0], row[1]]



    # This method gets the highest 10 damages.
    # A mapname can be specified to get a top 10 from that map
    def db_get_top_damages(self, mapname = ""):
        top_damages = []
        if mapname:
            mapname = " WHERE mapname = '{}' ".format(mapname)
        sql = "SELECT username, mapname, dmg FROM TopDamages{} ORDER BY dmg DESC LIMIT 10"
        c = self.db_query(sql.format(mapname))
        row = c.fetchall()
        for r in row:
            top_damages.append({'name':r[0], 'map':r[1], 'dmg':r[2]})
        return top_damages

    # If an entry for (username, mapname) already exists with a LOWER dmg, UPDATE IT
    # return false if user was already registered with a higher dmg (may not be highest)
    def db_insert_top_damage(self, username, mapname, dmg):
        sql_select = "SELECT dmg FROM TopDamages WHERE username = ? AND mapname = ?"
        c = self.db_query(sql_select, username, mapname)
        row = c.fetchone()
        if row: # record exists
            if row[0] < dmg: # old dmg < new dmg
                sql_update = "UPDATE TopDamages SET dmg = ? WHERE username = ? AND mapname = ?"
                c = self.db_query(sql_update, dmg, username, mapname)
                self.db_commit()
                return True
            else:
                # No insert needed
                return False
        else:
            c = self.db_query("INSERT INTO TopDamages VALUES (?, ?, ?)", username, mapname, dmg)
            self.db_commit()
            return True

    # remove a triple / value from the database records if it has been beat
    def db_remove_top_damage(self, username, mapname, dmg):
        c = self.db_query("DELETE FROM TopDamages WHERE username = ? AND mapname = ? AND dmg = ?", username, mapname, dmg)
        self.db_commit()

    # Remove all records of a player on a map or ALL maps
    def db_remove_player(self, username, mapname):
        if mapname != "all":
            mapname = " AND mapname = '{}'".format(mapname)
        else:
            mapname = ""

        c = self.db_query("DELETE FROM TopDamages WHERE username = ? {}".format(mapname), username)
        self.db_commit()

        self.msg("^7Player succesfully removed from specified map(s)!")

    # Get completed matches, cached
    def get_completed_matches(self, name):
        if name in self.cache_completed:
            return self.cache_completed[name]
        completed = self.db_get_completed_matches(name)
        self.cache_completed[name] = completed
        return completed

    def db_get_completed_matches(self, name):
        c = self.db_query("SELECT games_completed FROM Players WHERE name=?", name)
        row = c.fetchone()
        if row:
            return row[0]
        return 0 # If no records found, they have completed 0 matches...

    # Calculate value of a handicapped person's damage, plus give a small bonus
    # Eg: person with handicap 80% does one direct rocket
    #     - InitDamage = 80 (initdmg)
    #     - Handicap supplied = 160
    #     - Correction translates howmuch that would be if he had no handicap
    #     - A bonus of 5/3 is applied to compensate a little for the health reduction
    #
    #     - 80 * (1.25 + 0.042 ) = 103.3 calculated damage
    def calculate_handicap(dmg, hc):
        # method 1 or 2
        method = 2

        # Method one, better understandable but more individual calculations
        if method == 1:
            handicap_correction = 100.0/(hc/2)
            handicap_bonus = 100.0/((hc/1.666))-1
            return dmg*(handicap_correction + handicap_bonus)

        # Method two, just reformulated the above forumlae
        # This option has less calculations but is harder to modify/understand
        elif method == 2:
            return  dmg * 1100/3.0/hc - dmg