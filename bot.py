from sopel.module import (
    commands, require_privmsg, require_chanmsg)

from codenames import (
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
                   'game.'.format(player=trigger.nick)
        bot.say(response)
    return setup_phase


@commands('print')
def print_board(bot, trigger):
    if not check_phase_setup(bot, None):
        return
    game = get_game(bot)
    bot.say(game.render_board(column_width=COLUMN_WIDTH, include_colors=True),  # maybe not always true? TODO
            trigger.sender)
    
    
@commands('help')
def print_tutorial(bot, trigger):
    if not check_phase_setup(bot, None):
        return
    game = get_game(bot)
    
    bot.say('commands are: help join leave start spymaster choose(+word) pass print', trigger.sender)


@require_chanmsg
@commands('join')
def add_player(bot, trigger):
    if not check_phase_setup(bot, trigger):
        return
    team_color = trigger.group(2).strip()
    try:
        team = Team(team_color)
    except ValueError:
        return
    game = get_game(bot)
    game.add_player(trigger.nick, team)
    response = 'Added {player} to {team_color} team.'.format(
        player=trigger.nick, team_color=team.value)
    bot.say(response, trigger.sender)


@require_chanmsg
@commands('leave')
def remove_player(bot, trigger):
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
            player=trigger.nick, team=Team.value)
    bot.say(response, trigger.sender)


@require_chanmsg
@commands('start')
def start_game(bot, trigger):
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
@commands('choose')
def player_choose(bot, trigger):
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
    if not check_phase_setup(bot, trigger):
        return
    game = get_game(bot)
    
    bot.say(
        'Team {team} has ended its turn. '
        '{other_team} spymaster, make your move!'.format(team=game.moving_team.value,
                                                         other_team=str(game.moving_team.other()).upper()),
        trigger.sender)
    game.next_turn()
