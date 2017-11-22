import random

from sopel.module import (
    commands, rule, require_chanmsg, example)

from .codenames_bot import (
    say, get_arguments
)


@require_chanmsg
@commands('fuck_off', 'fuckoff', 'begone', 'suicide', 'go_away')
def suicide(bot, trigger):
    """This kills the bot"""
    if bot.personality != 0:
        if bot.personality == 1:
            bye = 'Bye!'
        elif bot.personality == 2:
            bye = '\o'
        elif bot.personality == 3:
            bye = 'Bye bye!'
        elif bot.personality == 4:
            bye = 'Sayonara!'
        else:
            if not hasattr(bot, 'suicide_refuse'):
                bot.suicide_refuse = 0
            bot.suicide_refuse += 1
            if bot.suicide_refuse == 1:
                say(bot, trigger, "No! You can't make me!")
                return
            elif bot.suicide_refuse == 2:
                say(bot, trigger, "No! Please don't kill me!")
                return
            else:
                bye = "Nooooooooo......!"
        say(bot, trigger, bye)
    bot.write(('QUIT', 'Goodbye cruel world...'))
    
    import os
    import signal
    pid = os.getpid()
    os.kill(pid, signal.SIGTERM)


@commands('hug')
def hug(bot, trigger):
    if bot.personality == 0:
        return
    if bot.personality >= 2:
        response = random.choice(["*shies away*", "*hugs back*",
                                  "*hugs {player} tightly*"
                                 .format(player=str(trigger.nick))])
    else:
        response = "*hugs {player}*".format(player=str(trigger.nick))
    say(bot, trigger, response)


@rule('(G|g)ood bot')
def good_bot(bot, trigger):
    if bot.personality == 0:
        return
    elif bot.personality <= 1:
        response = "|^__^|"
    elif bot.personality <= 4:
        response = "Good human!"
    else:
        response = random.choice(["Not...good...enough!",
                                  "Best bot!", "\♥/"])
    
    say(bot, trigger, response)


@commands('set_personality')
def set_personality(bot, trigger):
    """Sets the bot's personality. Possible values are 0 (cold),
     1 (warm, default), 2 (friendly) and 5 (not recommended).
     Can also use codenames for personalities (e.g. 'ape')"""
    
    args = get_arguments(trigger)
    if len(args) == 0:
        bot.personality = 2
        return
    arg = args[0]
    try:
        n = int(arg)
        if n < 0 or n > 5:
            say(bot, trigger, 'I am sorry, this is not one of my'
                              ' predefined personalities.')
            return
        bot.personality = n
    except ValueError:
        if arg == 'rock':
            bot.personality = 0
        elif arg == 'dog' or arg == 'jerry':
            bot.personality = 1
        elif arg == 'ape':
            bot.personality = 2
        elif arg == 'human':
            bot.personality = 3
        elif arg == 'teenager':
            bot.personality = 4
        elif arg == 'jack':
            bot.personality = 5
        else:
            say(bot, trigger, 'I am sorry, this is not one of my'
                              ' predefined personalities.')
            return
    
    say(bot, trigger, '<Bzzt!>')
