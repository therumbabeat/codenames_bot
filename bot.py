from sopel.module import (
    commands, require_privmsg, require_chanmsg)


from codenames import (
    IrcCodenamesGame, Team, GamePhase, IrcGameError)


BOT_MEMORY_KEY = 'codenames_game'


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
    bot.say('It is now the {team_color} team\'s turn!'.format(
        team_color=game.moving_team.value))

