from sopel.module import (
    commands, require_privmsg, require_chanmsg)

from .codenames import (
    IrcCodenamesGame, Team, GamePhase, IrcGameError, REVEALED_CARD_TOKEN, GameEvent)

BOT_MEMORY_KEY = 'codenames_game'
COLUMN_WIDTH = 12


def get_game(bot) -> IrcCodenamesGame:
    return bot.memory[BOT_MEMORY_KEY]


def new_game(bot):
    bot.memory[BOT_MEMORY_KEY] = IrcCodenamesGame()


def check_phase_setup(bot, trigger):
    game = get_game(bot)
    setup_phase = game.phase == GamePhase.setup
    if not setup_phase:
        response = '{player}: Can only do that while setting up the ' \
                   'game.'.format(player=str(trigger.nick))
        bot.say(response, trigger.sender)
    return setup_phase


@commands('print')
def print_board(bot, trigger):
    """Prints the game board"""
    if BOT_MEMORY_KEY not in bot.memory:
        return
    game = get_game(bot)
    bot.say(game.render_board(column_width=COLUMN_WIDTH, include_colors=True),  # maybe not always true? TODO
            trigger.sender)


@commands('teams')
def print_teams(bot, trigger):
    """Prints the team members"""
    if BOT_MEMORY_KEY not in bot.memory:
        return
    game = get_game(bot)
    bot.say("Team {team}:".format(team=Team.red), trigger.sender)
    bot.say(game.teams[Team.red], trigger.sender)
    bot.say("With {spy} as spymaster.".format(spy=game.spymasters[Team.red]), trigger.sender)
    bot.say("~~~ VS ~~~", trigger.sender)
    bot.say("Team {team}:".format(team=Team.blue), trigger.sender)
    bot.say(game.teams[Team.blue], trigger.sender)
    bot.say("With {spy} as spymaster.".format(spy=game.spymasters[Team.blue]), trigger.sender)


@commands('codenames')
def print_tutorial(bot, trigger):
    """Prints all the commands for the codenames game."""
    bot.say('COMMANDS:')
    bot.say('* codenames')
    bot.say('* setup')
    bot.say('* join <team?>')
    bot.say('* leave')
    bot.say('* start')
    bot.say('* spymaster')
    bot.say('* choose <word>')
    bot.say('* pass')
    bot.say('* print')
    bot.say('* teams')


@require_chanmsg
@commands('setup')
def setup_game(bot, trigger):
    """Sets up a game of Codenames. Waits for players and spymasters to join."""
    if BOT_MEMORY_KEY in bot.memory:
        pass  # but need to end last game and restart maybe
    
    new_game(bot)
    bot.say('Setting up Codenames, please !join (optional red|blue) to join a team '
            'and !become_spymaster to become your team\'s spymaster. Say !start to '
            'start the game once teams are decided.', trigger.sender)


@require_chanmsg
@commands('fuck_off')
def suicide(bot, trigger):
    """This kills the bot"""
    bot.say('PEACE OUT!')
    bot.write(('QUIT', 'Goodbye cruel world...'))
    import os
    os._exit(1) # O_O


@require_chanmsg
@commands('join')
def add_player(bot, trigger):
    """Adds a player to the game, to the specified team. Leave empty to get assigned automatically."""
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
        bot.say('You call {this} a team??'.format(this=team_color), trigger.sender)
        return
    game.add_player(trigger.nick, team)
    response = 'Added {player} to {team_color} team.'.format(
        player=trigger.nick, team_color=team.value)
    bot.say(response, trigger.sender)


@require_chanmsg
@commands('leave')
def remove_player(bot, trigger):
    """Removes a player from the game."""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    team = game.remove_player(trigger.nick)
    if team is not None:
        response = 'Removed {player} from {team_color} team.'.format(
            player=trigger.nick, team_color=team.value)
        bot.say(response, trigger.sender)


@require_chanmsg
@commands('spymaster')
def set_spymaster(bot, trigger):
    """Sets a player as a spymaster for their team."""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    team = game.get_player_team(trigger.nick)
    if team is None:
        response = '{player}: You need to join a team before becoming a ' \
                   'spymaster.'.format(player=trigger.nick)
    else:
        game.set_spymaster(team, trigger.nick)
        response = '{player} is now the {team} spymaster.'.format(
            player=trigger.nick, team=team.value)
    bot.say(response, trigger.sender)


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
        bot.say(str(err), trigger.sender)
        return
    bot.say('Codenames game now starting!', trigger.sender)
    print_board(bot, trigger)
    print_tutorial(bot, trigger)
    bot.say('It is now the {team_color} team\'s turn!'.format(
        team_color=game.moving_team.value), trigger.sender)


@require_chanmsg
@commands('touch')
def player_choose(bot, trigger):
    """Choose a card and touch it. Hope you made the right choice!"""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    
    word = trigger.groups(2).strip()  # will ignore extra arguments
    if word == REVEALED_CARD_TOKEN:
        bot.say('You won\'t trick me!')
        return
    word_pos = game.board.get_word_position(word)
    if word_pos is None:
        bot.say('This card is not on the board!', trigger.sender)
        return
    game_event = game.reveal_card_by_coordinates(*word_pos)
    if game_event is GameEvent.continue_turn:
        bot.say('Indeed! {word} belongs to you, team {team}.'.format(word=word, team=game.moving_team), trigger.sender)
        print_board(bot)
        return
    elif game_event is GameEvent.end_turn:
        bot.say('No! Mistake! Bad guess!', trigger.sender)
        bot.say('What an embarrassment.', trigger.sender)
        bot.say('What an embarrassment.', trigger.sender)
        bot.say('{other_team} spymaster, make your move!'.format(team=game.moving_team.value,
                                                                 other_team=str(game.moving_team.other()).upper()),
                trigger.sender)
        print_board(bot)
        game.next_turn()
        return
    elif game_event is GameEvent.end_game:
        bot.say(
            'End of game! This bot is a WIP and cannot say if this is a winning move'
            ' or an accidental assassin pick. Sorry!',
            trigger.sender)
        print_board(bot)
        return
    else:
        bot.say('you found a bug! this event does not compute: {event}'.format(event=game_event), trigger.sender)
        return


@require_chanmsg
@commands('pass')
def team_pass(bot, trigger):
    """Finish your team's turn."""
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    
    bot.say(
        'Team {team} has ended its turn. '
        '{other_team} spymaster, make your move!'.format(team=game.moving_team.value,
                                                         other_team=str(game.moving_team.other()).upper()),
        trigger.sender)
    game.next_turn()
