from sopel.module import (
    commands, require_privmsg, require_chanmsg)

from .codenames import (
    IrcCodenamesGame, Team, GamePhase, IrcGameError, REVEALED_CARD_TOKEN,
    GameEvent)

BOT_MEMORY_KEY = 'codenames_game'
COLUMN_WIDTH = 12


def get_game(bot) -> IrcCodenamesGame:
    return bot.memory[BOT_MEMORY_KEY]


def new_game(bot):
    bot.memory[BOT_MEMORY_KEY] = IrcCodenamesGame()


def check_phase_setup(bot, trigger):
    if BOT_MEMORY_KEY not in bot.memory \
            or get_game(bot).phase != GamePhase.setup:
        response = '{player}: Can only do that while setting up the ' \
                   'game.'.format(player=str(trigger.nick))
        say(bot, trigger, response)
        return False
    return True


def check_phase_play(bot, trigger):
    if BOT_MEMORY_KEY not in bot.memory \
            or get_game(bot).phase != GamePhase.in_progress:
        response = '{player}: Can only do that while mid-' \
                   'game.'.format(player=str(trigger.nick))
        say(bot, trigger, response)
        return False
    return True


def say(bot, trigger, text):
    bot.write(('PRIVMSG', trigger.sender), text)


@commands('print')
def print_board(bot, trigger):
    """Prints the game board"""
    if not check_phase_play(bot, trigger):
        return
    game = get_game(bot)
    rows = game.render_board_rows(column_width=COLUMN_WIDTH,
                                  include_colors=False)
    for row in rows:
        say(bot, trigger, row)


@commands('rules')
def rules(bot, trigger):
    """Prints the rules"""
    say(bot, trigger, 'RULES: https://static1.squarespace.com/static/'
                      '54da1198e4b0e9d26e55b0fc/t/5646752be4b0c85596a66ac7'
                      '/1447458091793/codenames-rules-en.pdf')


@require_privmsg
@commands('print_full')
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
                                  include_colors=True)
    for row in rows:
        say(bot, trigger, row)


@commands('teams')
def print_teams(bot, trigger):
    """Prints the team members"""
    if BOT_MEMORY_KEY not in bot.memory:
        return
    game = get_game(bot)
    say(bot, trigger, "Team {team}:".format(team=Team.red))
    say(bot, trigger, str(game.teams[Team.red]))
    say(bot, trigger, "With {spy} as spymaster.".format(
        spy=game.spymasters[Team.red]))
    say(bot, trigger, "~~~ VS ~~~")
    say(bot, trigger, "Team {team}:".format(team=Team.blue))
    say(bot, trigger, str(game.teams[Team.blue]))
    say(bot, trigger, "With {spy} as spymaster.".format(
        spy=game.spymasters[Team.blue]))


@commands('codenames')
def print_tutorial(bot, trigger):
    """Prints all the commands for the codenames game."""
    say(bot, trigger, 'COMMANDS:')
    say(bot, trigger, '* codenames')
    say(bot, trigger, '* setup')
    say(bot, trigger, '* join <team?>')
    say(bot, trigger, '* leave')
    say(bot, trigger, '* start')
    say(bot, trigger, '* spymaster')
    say(bot, trigger, '* choose <word>')
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
    if BOT_MEMORY_KEY in bot.memory:
        pass  # but need to end last game and restart maybe

    new_game(bot)
    say(bot, trigger, 'Setting up Codenames, please !join (optional red|blue) '
                      'to join a team and !spymaster to become your team\'s '
                      'spymaster. Say !start to start the game once teams are '
                      'decided.')


@require_chanmsg
@commands('fuck_off')
def suicide(bot, trigger):
    """This kills the bot"""
    say(bot, trigger, 'PEACE OUT!')
    bot.write(('QUIT', 'Goodbye cruel world...'))
    import os
    import signal
    pid = os.getpid()
    os.kill(pid, signal.SIGTERM)


@require_chanmsg
@commands('join')
def add_player(bot, trigger):
    """Adds a player to the game, to the specified team. Leave empty to get
    assigned automatically."""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    if trigger.group(2) is None:
        if len(game.teams[Team.red]) > len(game.teams[Team.blue]):
            team_color = Team.blue
        else:
            team_color = Team.red
    else:
        team_color = trigger.group(2).strip()
    try:
        team = Team(team_color)
    except ValueError:
        say(bot, trigger, 'You call {this} a team??'.format(this=team_color))
        return
    game.add_player(str(trigger.nick), team)
    response = 'Added {player} to {team_color} team.'.format(
        player=str(trigger.nick), team_color=team.color)
    say(bot, trigger, response)


@require_chanmsg
@commands('leave')
def remove_player(bot, trigger):
    """Removes a player from the game."""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    team = game.remove_player(str(trigger.nick))
    if team is not None:
        response = 'Removed {player} from {team_color} team.'.format(
            player=str(trigger.nick), team_color=team.color)
        say(bot, trigger, response)


@require_chanmsg
@commands('spymaster')
def set_spymaster(bot, trigger):
    """Sets a player as a spymaster for their team."""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    team = game.get_player_team(str(trigger.nick))
    if team is None:
        response = '{player}: You need to join a team before becoming a ' \
                   'spymaster.'.format(player=str(trigger.nick))
    else:
        game.set_spymaster(team, str(trigger.nick))
        response = '{player} is now the {team} spymaster.'.format(
            player=str(trigger.nick), team=team.color)
    say(bot, trigger, response)


@commands('hug')
def hug(bot, trigger):
    response = "*hugs {player}*".format(player=str(trigger.nick))
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
    say(bot, trigger, 'Codenames game now starting!')
    print_board(bot, trigger)
    # print_tutorial(bot, trigger)
    say(bot, trigger, 'It is now the {team_color} team\'s turn!'.format(
        team_color=str(game.moving_team.color)))


@require_chanmsg
@commands('touch')
def player_choose(bot, trigger):
    """Choose a card and touch it. Hope you made the right choice!"""
    if not check_phase_play(bot, trigger):
        return
    game = get_game(bot)

    word = trigger.groups(17)[2].strip()  # first argument, default 17
    if word == 17:
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
        say(bot, trigger, 'Indeed! {word} belongs to you, team {team}.'.format(
            word=word, team=game.moving_team))
        print_board(bot, trigger)
        return
    elif game_event is GameEvent.end_turn:
        say(bot, trigger, 'No! Mistake! Bad guess!')
        say(bot, trigger, 'What an embarrassment.')
        say(bot, trigger, '{other_team} spymaster, make your move!'.format(
            team=game.moving_team.color,
            other_team=str(game.moving_team.other()).upper()))
        print_board(bot, trigger)
        game.next_turn()
        return
    elif game_event is GameEvent.end_game:
        say(bot, trigger,
            'End of game! This bot is a WIP and cannot say if this is a '
            'winning move or an accidental assassin pick. Sorry!')

        rows = game.render_board_rows(column_width=COLUMN_WIDTH,
                                      include_colors=True)
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

    say(bot, trigger,
        'Team {team} has ended its turn. '
        '{other_team} spymaster, make your move!'.format(
            team=game.moving_team.color,
            other_team=str(game.moving_team.other()).upper()))
    game.next_turn()
