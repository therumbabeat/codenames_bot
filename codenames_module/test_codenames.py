import pytest
import random
import os
import json
import re
from typing import List, Dict, Callable, Union

import sopel.tools
import sopel.trigger
from sopel.test_tools import (MockSopel, MockSopelWrapper)
from sopel.formatting import (CONTROL_BOLD, CONTROL_COLOR, CONTROL_NORMAL,
                              CONTROL_UNDERLINE)

from .codenames_game import (
    Team, CardType, GameBoard, GamePhase, GameEvent, IrcCodenamesGame,
    TEAM_CARD_COUNT, BYSTANDER_CARD_COUNT, ASSASSIN_CARD_COUNT, BOARD_SIZE)
from .codenames_bot import (
    get_game, setup, rules, setup_game, add_player
)

random.seed(0)


def card_type_all_words(game_board: GameBoard, card_type: CardType) \
        -> List[str]:
    words = []
    indices = GameBoard.get_grid_indices()
    for i, j in indices:
        if game_board.spy_key[i][j] is card_type:
            words.append(game_board.grid[i][j])
    return words


def card_type_example_words(game_board: GameBoard) -> Dict[CardType, str]:
    words = dict()
    unfound_card_types = list(CardType)
    indices = GameBoard.get_grid_indices()
    while unfound_card_types:
        i, j = next(indices)
        card_type = game_board.spy_key[i][j]
        if card_type in unfound_card_types:
            unfound_card_types.remove(card_type)
            words[card_type] = game_board.grid[i][j]
    return words


class TestBoard:

    @pytest.fixture
    def starting_team(self) -> Team:
        return Team.red

    @pytest.fixture
    def spy_key(self, starting_team: Team) -> List[List[CardType]]:
        return IrcCodenamesGame.generate_spy_key(starting_team)

    @pytest.fixture
    def word_deck(self) -> List[str]:
        word_deck_fn = IrcCodenamesGame.word_deck_fn
        word_deck_dirpath = IrcCodenamesGame.word_deck_dirpath
        word_deck_filepath = os.path.join(word_deck_dirpath, word_deck_fn)
        with open(word_deck_filepath) as fp:
            return json.load(fp)

    @pytest.fixture
    def game_board(self, word_deck: List[str], spy_key: List[List[CardType]]) \
            -> GameBoard:
        return GameBoard(word_deck, spy_key)

    def test_board_setup(self, game_board: GameBoard, starting_team: Team):
        assert game_board.cards_remaining(starting_team.card_type()) \
            == TEAM_CARD_COUNT + 1
        assert game_board.cards_remaining(starting_team.other().card_type()) \
            == TEAM_CARD_COUNT
        assert game_board.cards_remaining(CardType.bystander) \
            == BYSTANDER_CARD_COUNT
        assert game_board.cards_remaining(CardType.assassin) \
            == ASSASSIN_CARD_COUNT

    def test_board_reveal(self, game_board: GameBoard, starting_team: Team):
        cards_remaining_before = game_board.cards_remaining(
            starting_team.card_type())
        example_words = card_type_example_words(game_board)
        team_word = example_words[starting_team.card_type()]
        card_type = game_board.reveal_card_by_word(team_word)
        cards_remaining_after = game_board.cards_remaining(
            starting_team.card_type())
        assert cards_remaining_before == cards_remaining_after + 1
        assert card_type == starting_team.card_type()

    def test_board_game_over(self, game_board: GameBoard, starting_team: Team):
        card_type_words = card_type_all_words(
            game_board, starting_team.card_type())
        for word in card_type_words:
            game_board.reveal_card_by_word(word)
        assert(game_board.team_won(starting_team))


class TestCodenamesGame:

    @pytest.fixture
    def red_spymaster(self) -> str:
        return 'red_spymaster'

    @pytest.fixture
    def red_agent(self) -> str:
        return 'red_agent'

    @pytest.fixture
    def red_team(self, red_spymaster: str, red_agent: str) -> List[str]:
        return [red_spymaster, red_agent]

    @pytest.fixture
    def blue_spymaster(self) -> str:
        return 'blue_spymaster'

    @pytest.fixture
    def blue_agent(self) -> str:
        return 'blue_agent'

    @pytest.fixture
    def blue_team(self, blue_spymaster: str, blue_agent: str) -> List[str]:
        return [blue_spymaster, blue_agent]

    @pytest.fixture
    def game(self, red_team: List[str], blue_team: List[str], red_spymaster:
             str, blue_spymaster: str) -> IrcCodenamesGame:
        return IrcCodenamesGame(red_team, blue_team, red_spymaster,
                                blue_spymaster)

    def test_phases(self, game: IrcCodenamesGame):
        assert game.phase == GamePhase.setup
        game.start()
        assert game.phase == GamePhase.in_progress
        assassin_word = card_type_all_words(game.board, CardType.assassin)[0]
        game.reveal_card(assassin_word)
        assert game.phase == GamePhase.finished

        game.reset()
        assert game.phase == GamePhase.setup

    def test_player_add_remove(self, game: IrcCodenamesGame, red_agent: str,
                               red_spymaster: str, blue_agent: str,
                               blue_spymaster: str, red_team: List[str],
                               blue_team: List[str]):
        game.set_spymaster(Team.red, red_agent)
        assert game.get_spymaster(Team.red) == red_agent

        game.add_player(blue_agent, Team.red)
        assert game.get_team_members(Team.red) == set(red_team + [blue_agent])
        assert game.get_team_members(Team.blue) == {blue_spymaster}

        game.add_player(red_agent, Team.blue)
        assert game.get_spymaster(Team.red) is None

        game.remove_player(blue_spymaster)
        assert game.get_spymaster(Team.blue) is None

        with pytest.raises(ValueError):
            game.set_spymaster(Team.blue, blue_spymaster)

    def test_events(self, game: IrcCodenamesGame):
        game.start()
        example_words = card_type_example_words(game.board)
        moving_team_word = example_words[game.moving_team.card_type()]
        other_team_word = example_words[game.moving_team.other().card_type()]
        assassin_word = example_words[CardType.assassin]
        bystander_word = example_words[CardType.bystander]

        event = game.reveal_card(moving_team_word)
        assert event is GameEvent.continue_turn

        event = game.reveal_card(other_team_word)
        assert event is GameEvent.end_turn_enemy

        event = game.reveal_card(bystander_word)
        assert event is GameEvent.end_turn_bystander

        event = game.reveal_card(assassin_word)
        assert event is GameEvent.end_game

    def test_render_board(self, game: IrcCodenamesGame):
        """Only check if the general shape of the output is correct."""
        game.start()
        rows = game.render_board_rows()
        assert len(rows) == BOARD_SIZE
        for i in range(BOARD_SIZE):
            words = game.board.grid[i]
            for word in words:
                assert word.upper() in rows[i]


class MockBot(MockSopel):

    def __init__(self, nick, admin=False, owner=False):
        super().__init__(nick, admin, owner)
        self.config.parser.set('core', 'prefix', '!')
        self.prefix: str = self.config.core.prefix

    def send_message(self, msg: str, func: Callable, author: str = None,
                     privmsg: bool = False, single_output: bool = True) \
            -> Union[List[str], str]:
        """Send message to the bot with the intent of triggering the provided
        callable."""
        match = None
        if hasattr(func, 'commands'):
            for command in func.commands:
                regexp = sopel.tools.get_command_regexp(self.prefix, command)
                match = regexp.match(msg)
                if match:
                    break
        assert match, 'Function did not match any command.'

        sender = self.nick if privmsg else "#channel"
        author = author or self.nick
        hostmask = "%s!%s@%s" % (author, "UserName", "example.com")
        full_message = ':{} PRIVMSG {} :{}'.format(hostmask, sender, msg)

        pretrigger = sopel.trigger.PreTrigger(self.nick, full_message)
        trigger = sopel.trigger.Trigger(self.config, pretrigger, match)
        wrapper = MockWriteWrapper(self, trigger)
        func(wrapper, trigger)
        if single_output:
            assert len(wrapper.output) == 1, 'Command returned multiple lines.'
            return wrapper.output[0]
        return wrapper.output


class MockWriteWrapper(MockSopelWrapper):
    """We use bot.write instead of bot.say, and MockSopelWrapper doesn't
    override the write method, so we do it ourselves here."""
    def write(self, args, text=None):
        self.say(text)


class TestBot:

    @staticmethod
    def undecorate(bot_response: str) -> str:
        matcher = re.compile('[{}{}{}]|{}\d\d'.format(CONTROL_UNDERLINE,
                                                      CONTROL_NORMAL,
                                                      CONTROL_BOLD,
                                                      CONTROL_COLOR))
        response = matcher.sub('', bot_response)
        response = response.replace(CONTROL_COLOR, '')
        return response

    @pytest.fixture
    def bot(self) -> MockBot:
        bot = MockBot(nick='Testuvorov')
        setup(bot)
        return bot

    def test_rules(self, bot: MockBot):
        output = bot.send_message('!rules', rules)
        assert output == 'RULES: https://static1.squarespace.com/static/' \
                         '54da1198e4b0e9d26e55b0fc/t/5646752be4b0c85596a66'\
                         'ac7/1447458091793/codenames-rules-en.pdf'

    def test_setup_game(self, bot: MockBot):
        output = bot.send_message('!setup', setup_game)
        assert output == 'Setting up Codenames, please !join (optional ' \
                         'red|blue) to join a team and !spymaster to become ' \
                         'your team\'s spymaster. Say !start to start the ' \
                         'game once teams are decided.'
        game = get_game(bot)
        assert game.phase == GamePhase.setup

    def test_add_player(self, bot: MockBot):
        bot.send_message('!setup', setup_game)

        output = bot.send_message('!join red', add_player, 'tester1')
        assert self.undecorate(output) == 'Added tester1 to Red team.'

        output = bot.send_message('!join blue', add_player, 'tester1')
        assert self.undecorate(output) == 'Added tester1 to Blue team.'

        output = bot.send_message('!join GRU', add_player, 'tester1')
        assert self.undecorate(output) == 'You call GRU a team??'
