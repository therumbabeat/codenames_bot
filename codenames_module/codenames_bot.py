import random

from sopel.module import (
    commands, rule, require_privmsg, require_chanmsg, example)
import sopel.formatting as irc_format
from sopel.tools import Identifier
from sopel import bot as sopelbot

from .codenames_game import (
    IrcCodenamesGame, Team, GamePhase, IrcGameError, REVEALED_CARD_TOKEN,
    GameEvent)

BOT_MEMORY_KEY: str = 'codenames_game'
COLUMN_WIDTH: int = 12
CONTROL_BOLD: str = '\x1d'


def setup(bot):
    """Supposedly, sopel calls this automatically"""
    new_game(bot)
    bot.personality = 1


def get_game(bot) -> IrcCodenamesGame:
    return bot.memory[BOT_MEMORY_KEY]


def new_game(bot):
    bot.memory[BOT_MEMORY_KEY] = IrcCodenamesGame()


def get_arguments(trigger):
    return [arg for arg in trigger.groups() if arg is not None][2:]


def get_decorated_team_name(team: Team) -> str:
    team_name = '{color} team'.format(color=team.color.capitalize())
    if team is Team.red:
        irc_color = irc_format.colors.RED
    else:
        irc_color = irc_format.colors.LIGHT_BLUE
    decorated_name = irc_format.bold(irc_format.color(team_name, irc_color))
    return decorated_name


def get_decorated_name(team: Team, string: str) -> str:
    if team is Team.red:
        irc_color = irc_format.colors.RED
    else:
        irc_color = irc_format.colors.LIGHT_BLUE
    decorated_name = irc_format.bold(irc_format.color(string, irc_color))
    return decorated_name


def white_bold(string: str) -> str:
    return irc_format.bold(irc_format.color(string,
                                            irc_format.colors.LIGHT_GRAY))


def italics(text: str):
    """Return the text, with bold IRC formatting."""
    return ''.join([CONTROL_BOLD, text, CONTROL_BOLD])


def print_team(bot: sopelbot.Sopel, trigger, team: Team):
    game = get_game(bot)
    team_name = get_decorated_team_name(team)
    team_members = list(game.get_team_members(team))
    if game.spymasters[team] is not None:
        team_spymaster = str(game.spymasters[team])
        team_members.remove(team_spymaster)
        team_members.insert(0, irc_format.underline(team_spymaster))
    if bot.personality >= 5 and random.randint(1, 3) == 1:
        team_members += str(bot.nick)
    say(bot, trigger, '{team_name}:'.format(team_name=team_name))
    say(bot, trigger, ', '.join(team_members))


def send_board_to_spymasters(bot):
    game = get_game(bot)
    for team in (Team.red, Team.blue):
        spymaster_name = str(game.spymasters[team])
        rows = game.render_board_rows(column_width=COLUMN_WIDTH,
                                      spoil_colors=True)
        for row in rows:
            bot.write(('PRIVMSG', spymaster_name), row)


def print_end_turn(bot, trigger):
    game = get_game(bot)
    moving_team_name = get_decorated_team_name(game.moving_team)
    spymaster_enemy = get_decorated_name(
        game.moving_team.other(),
        "Spymaster " + str(game.spymasters[game.moving_team.other()]))
    say(bot, trigger,
        '{moving_team_name} have ended their turn. '
        '{spymaster_enemy}, make your move!'.format(
            moving_team_name=moving_team_name,
            spymaster_enemy=spymaster_enemy))


def check_phase_setup(bot, trigger):
    if get_game(bot).phase != GamePhase.setup:
        response = '{player}: Can only do that while setting up the ' \
                   'game.'.format(player=str(trigger.nick))
        say(bot, trigger, response)
        return False
    return True


def say(bot, trigger, text):
    bot.write(('PRIVMSG', trigger.sender), text)


def check_phase_play(bot, trigger):
    if get_game(bot).phase != GamePhase.in_progress:
        response = '{player}: Can only do that while mid-' \
                   'game.'.format(player=str(trigger.nick))
        say(bot, trigger, response)
        return False
    return True


@commands('debug')
def toggle_debug(bot, trigger):
    """>Debug mode<"""
    game = get_game(bot)
    game.DEBUG = not game.DEBUG
    say(bot, trigger, "<BEEP BOOP>" if game.DEBUG else "<beep boop>")


@commands('counts', 'score')
def print_counts(bot, trigger):
    """Print amount of cards of each type"""
    if check_phase_play(bot, trigger):
        game = get_game(bot)

        counts = game.board.count_all_cards()

        say(bot, trigger, irc_format.underline("CURRENT SCORE"))
        say(bot, trigger, "Team {team}: {flp} cards revealed, "
                          "{rem} cards remaining.".format(
            team=Team.red.name,
            flp=counts.revealed_red,
            rem=counts.hidden_red))
        say(bot, trigger, "Team {team}: {flp} cards revealed, "
                          "{rem} cards remaining.".format(
            team=Team.blue.name,
            flp=counts.revealed_blue,
            rem=counts.hidden_blue))
        say(bot, trigger, "Bystanders remaining: {bys}."
                          " Assassins: {ass}".format(
            bys=counts.hidden_white,
            ass=counts.black))


@commands('print', 'print_board', 'board')
def print_board(bot, trigger):
    """Prints the game board"""
    if not check_phase_play(bot, trigger):
        return
    game = get_game(bot)
    rows = game.render_board_rows(column_width=COLUMN_WIDTH,
                                  spoil_colors=False)
    for row in rows:
        say(bot, trigger, row)


@commands('rules', 'link')
def rules(bot, trigger):
    """Prints the rules"""
    say(bot, trigger, 'RULES: https://static1.squarespace.com/static/'
                      '54da1198e4b0e9d26e55b0fc/t/5646752be4b0c85596a66ac7'
                      '/1447458091793/codenames-rules-en.pdf')


@require_privmsg
@commands('print_full', 'secrets')
def print_board_full(bot, trigger):
    """Prints the game board in full technicolor"""
    if not check_phase_play(bot, trigger):
        return
    game = get_game(bot)
    player = str(trigger.nick)
    if player not in game.spymasters.values():
        say(bot, trigger, "You won't fool me!")
        return
    rows = game.render_board_rows(column_width=COLUMN_WIDTH,
                                  spoil_colors=True)
    for row in rows:
        say(bot, trigger, row)


@commands('teams')
def print_teams(bot, trigger):
    """Prints the team members"""
    print_team(bot, trigger, Team.blue)
    say(bot, trigger, "~~~ VS ~~~")
    print_team(bot, trigger, Team.red)


@commands('codenames', 'commands')
def print_tutorial(bot, trigger):
    """Prints all the commands for the codenames game."""
    say(bot, trigger, 'COMMANDS:')
    say(bot, trigger, '* codenames')
    say(bot, trigger, '* setup')
    say(bot, trigger, '* join <team?>')
    say(bot, trigger, '* leave')
    say(bot, trigger, '* start')
    say(bot, trigger, '* finish')
    say(bot, trigger, '* spymaster')
    say(bot, trigger, '* touch <word>')
    say(bot, trigger, '* pass')
    say(bot, trigger, '* print')
    say(bot, trigger, '* teams')
    say(bot, trigger, '* rules')
    say(bot, trigger, '* print_full (only spymasters in PM can use this)')


@require_chanmsg
@commands('setup')
def setup_game(bot, trigger):
    """Sets up a game of Codenames. Waits for players and spymasters to
    join."""
    new_game(bot)
    say(bot, trigger, 'Setting up Codenames, please !join (optional red|blue) '
                      'to join a team and !spymaster to become your team\'s '
                      'spymaster. Say !start to start the game once teams are '
                      'decided.')


@require_chanmsg
@commands('join')
def add_player(bot, trigger):
    """Adds a player to the game, to the specified team. Leave empty to get
    assigned automatically."""
    if not check_phase_setup(bot, trigger):
        return
    add_player_func(bot, trigger, respond=True)


def add_player_func(bot, trigger, respond: bool) -> Team:
    game = get_game(bot)
    auto = False
    team = Team.red  # meaningless

    if trigger.group(2) is None:
        auto = True
    else:
        team_color = trigger.group(2).strip()
        try:
            team = Team(team_color)
        except ValueError:
            if len(team_color) <= 1:  # then it's probably a typo
                auto = True
            else:
                say(bot, trigger,
                    'You call {this} a team??'.format(this=team_color))
                return Team.red
    if auto:
        if len(game.teams[Team.red]) > len(game.teams[Team.blue]):
            team = Team.blue
        else:
            team = Team.red
    game.add_player(str(trigger.nick), team)

    if respond:
        team_name = get_decorated_team_name(team)
        response = 'Added {player} to {team_name}.'.format(
            player=str(trigger.nick), team_name=team_name)
        say(bot, trigger, response)

    return team


@require_chanmsg
@commands('leave')
def remove_player(bot, trigger):
    """Removes a player from the game."""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    team = game.remove_player(str(trigger.nick))
    if team is not None:
        team_name = get_decorated_team_name(team)
        response = 'Removed {player} from {team_name} team.'.format(
            player=str(trigger.nick), team_name=team_name)
        say(bot, trigger, response)


@require_chanmsg
@commands('spymaster', 'master')
def set_spymaster(bot, trigger):
    """Sets a player as a spymaster for their team."""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    team = game.get_player_team(str(trigger.nick))
    if team is None:
        team = add_player_func(bot, trigger, respond=False)
    game.set_spymaster(team, str(trigger.nick))
    team_name = get_decorated_team_name(team)
    response = '{player} is now the {team_name} spymaster.'.format(
        player=str(trigger.nick), team_name=team_name)
    say(bot, trigger, response)


@require_chanmsg
@commands('start')
def start_game(bot, trigger):
    """Starts a game of Codenames, after setup is done."""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    try:
        game.start()
    except IrcGameError as err:
        say(bot, trigger, str(err))
        return

    game.complete_original_spoiler_rows = game.render_board_rows(
        column_width=COLUMN_WIDTH, spoil_colors=True)

    say(bot, trigger, 'Codenames game now starting!')
    print_board(bot, trigger)
    bot.write(('PRIVMSG', str(game.spymasters[Team.red])),
              get_decorated_name(Team.red,
                                 "You are {team}!".format(team=Team.red)))
    bot.write(('PRIVMSG', str(game.spymasters[Team.blue])),
              get_decorated_name(Team.blue,
                                 "You are {team}!".format(team=Team.blue)))
    send_board_to_spymasters(bot)
    team_name = get_decorated_team_name(game.moving_team)
    say(bot, trigger, 'It is now the {team_name}\'s turn!'.format(
        team_name=team_name))


@require_chanmsg
@commands('hint')
@example('!hint artichoke 2')
def spymaster_hint(bot, trigger):
    if not check_phase_play(bot, trigger):
        return

    game = get_game(bot)
    player_team = game.get_player_team(str(trigger.nick))
    if player_team is not game.moving_team:
        return

    if str(trigger.nick) != game.spymasters[player_team]:
        return

    args = get_arguments(trigger)
    if len(args) < 2:
        say(bot, trigger, 'This command requires at least two arguments.')
        return

    words = ' '.join(args[:-1])
    number = args[-1]
    error_msg = 'The second argument must either be a number ' \
                'in the 0-9 range or "unlimited"/"*".'
    try:
        n = int(number)
        if n < 0 or n > 9:
            say(bot, trigger, error_msg)
            return
        if n == 0:
            number = italics('ZERO')
    except ValueError:
        if number.lower == 'unlimited' or number.startswith('*'):
            number = italics('UNLIMITED')
        elif number.lower == 'zero':
            number = italics('ZERO')
        else:
            say(bot, trigger, error_msg)
            return

    team_name = get_decorated_team_name(player_team)
    hint = '{words} {number}'.format(words=words.upper(), number=number)
    decorated_hint = irc_format.bold(irc_format.underline(hint))
    response = '{team_name}\'s hint is {hint}'.format(team_name=team_name,
                                                      hint=decorated_hint)
    if bot.personality >= 5:
        if number >= 5:
            response += random.choice([" (wow!)", " (brave!)", ' (!)'])
    say(bot, trigger, response)


@require_chanmsg
@commands('touch')
def player_choose(bot, trigger):
    """Choose a card and touch it. Hope you made the right choice!"""
    if not check_phase_play(bot, trigger):
        return
    game = get_game(bot)

    # Check if the player is on the currently moving team
    player_team = game.get_player_team(str(trigger.nick))
    if not game.DEBUG and player_team is not game.moving_team:
        return

    # Check if the player is the spymaster
    if (not game.DEBUG) and str(trigger.nick) == game.spymasters[player_team]:
        bot.say('Spymasters aren\'t allowed to touch cards.', trigger.nick)

    player_team_name = get_decorated_team_name(player_team)
    other_team_name = get_decorated_team_name(player_team.other())
    word = trigger.groups(17)[2].strip().upper()  # first argument, default 17
    if word == '17':
        say(bot, trigger, 'Touch what?')
        return
    if word == REVEALED_CARD_TOKEN:
        say(bot, trigger, 'You won\'t trick me!')
        return
    word_pos = game.board.get_word_position(word)
    if word_pos is None:
        say(bot, trigger, 'This card is not on the board!')
        return
    game_event = game.reveal_card_by_coordinates(*word_pos)
    if game_event is GameEvent.continue_turn:
        say(bot, trigger, 'Indeed! {word} belongs to you, {team_name}.'.format(
            word=word, team_name=game.moving_team))
        print_board(bot, trigger)
        return
    elif game_event is GameEvent.end_turn_bystander:

        say(bot, trigger, 'Nope!')
        say(bot, trigger, '{word} was actually {team}.'.format(
            word=word, team=white_bold("WHITE")))

        send_board_to_spymasters(bot)
        print_board(bot, trigger)
        print_end_turn(bot, trigger)
        game.next_turn()
        return
    elif game_event is GameEvent.end_turn_enemy:

        possible_stabs = []
        if bot.personality == 0:
            possible_stabs.extend(["No, bad judgement."])
        if bot.personality >= 1:
            possible_stabs.extend(['What an embarrassment.',
                                   'How typical...',
                                   'Look what you\'ve done!',
                                   'What a twist!',
                                   'LOL!', 'Hahahahaha what?',
                                   'You messed up!'])
        if bot.personality >= 5:
            possible_stabs.extend(['What a poor decision...',
                                   'I mean, come on, really?',
                                   'Even I figured it out... but apparently'
                                   ' you did not.',
                                   'Sorry...'])
        random_stab = random.choice(possible_stabs)
        say(bot, trigger, random_stab)
        say(bot, trigger, '{word} was actually {team}!'.format(
            word=word, team=other_team_name))

        if bot.personality >= 5:
            if random.randint(1, 3) == 1:  # 1 in 3 chance
                say(bot, trigger, random.choice(['(blame the spymaster!)',
                                                 '(sorry)'
                                                 '(even I got that hint...)',
                                                 '(lol)']))

        send_board_to_spymasters(bot)
        print_board(bot, trigger)
        print_end_turn(bot, trigger)
        game.next_turn()
        return
    elif game_event is GameEvent.end_game:
        winning_team_name = get_decorated_team_name(game.winning_team)
        losing_team_name = get_decorated_team_name(game.winning_team.other())
        if game.board.assassin_revealed():
            response = '{losing_team_name} revealed the assassin! ' \
                       '{winning_team_name} wins the game!'.format(
                losing_team_name=losing_team_name,
                winning_team_name=winning_team_name
            )
        else:
            response = '{winning_team_name} has revealed all of their ' \
                       'agents, and are victorious! Congrats!'.format(
                winning_team_name=winning_team_name
            )
        say(bot, trigger, response)

        rows = game.complete_original_spoiler_rows
        for row in rows:
            say(bot, trigger, row)

        return
    else:
        say(bot, trigger, 'you found a bug! this event does not compute: '
                          '{event}'.format(event=game_event))
        return


@require_chanmsg
@commands('pass')
def team_pass(bot, trigger):
    """Finish your team's turn."""
    if not check_phase_play(bot, trigger):
        return
    game = get_game(bot)

    # Check if the player is on the currently moving team
    player_team = game.get_player_team(str(trigger.nick))
    if not game.DEBUG and player_team is not game.moving_team:
        return

    print_end_turn(bot, trigger)
    game.next_turn()


@require_chanmsg
@commands('restart')
def restart_game(bot, trigger):
    """Restart game with the current teams and a new board."""
    game = get_game(bot)
    game.reset()
    say(bot, trigger, 'Restarting game with the current teams.')
    start_game(bot, trigger)


@require_chanmsg
@commands('remix')
def rotate_game(bot, trigger):
    """Restart game with new teams/spymasters and a new board. """
    game = get_game(bot)
    game.reset()
    say(bot, trigger, 'REMIXING TEAMS')

    players = list()
    players.extend(game.teams[Team.red])
    players.extend(game.teams[Team.blue])
    random.shuffle(players)
    middle = len(players) // 2
    game.teams[Team.red] = set(players[:middle])
    game.teams[Team.blue] = set(players[middle:])
    game.spymasters[Team.red] = players[0]
    game.spymasters[Team.blue] = players[middle]

    start_game(bot, trigger)


@require_chanmsg
@commands('finish')
def finish_game(bot, trigger):
    """Finish game, and print the full board."""
    game = get_game(bot)
    say(bot, trigger, 'You have decided to abruptly conclude the game. '
                      'The original board was:')

    rows = game.complete_original_spoiler_rows
    for row in rows:
        say(bot, trigger, row)

    game.reset()


@require_chanmsg
@commands('rename')
@example('!rename player1 player2')
def rename_player(bot, trigger):
    game = get_game(bot)
    args = get_arguments(trigger)
    if not len(args) == 2:
        say(bot, trigger, 'This command requires exactly two arguments.')
        return

    removed_player = args[0]
    added_player = args[1]

    player_team = game.get_player_team(removed_player)
    if player_team is None:
        say(bot, trigger, '{removed_player} is not participating in the '
                          'game.'.format(removed_player=removed_player))
        return

    if game.get_player_team(added_player) is not None:
        say(bot, trigger, '{added_player} is already participating in the '
                          'game.'.format(added_player=added_player))
        return

    channel_users = bot.channels[trigger.sender].users
    if Identifier(added_player) not in channel_users:
        say(bot, trigger, '{added_player} is not in this channel.'.format(
            added_player=added_player))
        return

    game.remove_player(removed_player)
    game.add_player(added_player, player_team)
    team_name = get_decorated_team_name(player_team)
    say(bot, trigger, 'Renamed {removed_player} to {added_player} in '
                      '{team_name}.'.format(removed_player=removed_player,
                                            added_player=added_player,
                                            team_name=team_name))
