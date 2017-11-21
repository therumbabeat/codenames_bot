"""
Codenames game logic and state.
"""

import random
import enum
import itertools
import math
import json
import os
from typing import List, Tuple, Union, Iterable


import sopel.formatting as irc_format

DEBUG = True

MINIMUM_PLAYERS = 4
REVEALED_CARD_TOKEN = '#####'
BOARD_SIZE = 5
TEAM_CARD_COUNT = 8
BYSTANDER_CARD_COUNT = 7
ASSASSIN_CARD_COUNT = 1


class CardType(enum.Enum):
    red = 'red'
    blue = 'blue'
    bystander = 'bystander'
    assassin = 'assassin'

    def team(self):
        return Team(self.value)


class Team(enum.Enum):
    red = 'red'
    blue = 'blue'

    def other(self):
        """The other team, useful when switching turns."""
        if self is Team.red:
            return Team.blue
        else:
            return Team.red

    def card_type(self):
        """Card type for this team"""
        return CardType(self.color)

    @property
    def color(self):
        return self.value


class GameEvent(enum.Enum):
    """Event as a result of revealing a card."""
    end_game = enum.auto()
    end_turn = enum.auto()
    continue_turn = enum.auto()


class GamePhase(enum.Enum):
    setup = enum.auto()
    in_progress = enum.auto()
    finished = enum.auto()


class GameBoard(object):
    """The game board. Takes care of the mechanics of revealing cards and
    checking win conditions.
    """

    def __init__(self, word_deck: List[str], spy_key: List[List[CardType]]):
        self.validate_deck(word_deck)
        self.word_deck = word_deck
        self.spy_key = spy_key
        self.grid = self.generate_grid(self.word_deck)
        self._cards_remaining = {card_type: self.count_revealed_cards(
            card_type) for card_type in CardType}

    @staticmethod
    def generate_grid(word_deck: List[str]) -> List[List[str]]:
        word_sample = random.sample(word_deck, BOARD_SIZE * BOARD_SIZE)
        board_words = list(map(str.upper, word_sample))
        grid = [board_words[i:i + BOARD_SIZE]
                for i in range(0, BOARD_SIZE * BOARD_SIZE, BOARD_SIZE)]
        return grid

    @staticmethod
    def validate_deck(word_deck: List[str]):
        """Check if the deck is valid. Currently this just checks whether
        it contains any duplicates."""
        if len(word_deck) != len(set(word_deck)):
            raise ValueError('Deck must be composed of unique words.')

    def reveal_card_by_coordinates(self, i: int, j: int) -> CardType:
        if self.is_revealed(i, j):
            raise InvalidMove('This card has already been revealed!')
        self.grid[i][j] = REVEALED_CARD_TOKEN
        revealed_card_type = self.spy_key[i][j]
        self._cards_remaining[revealed_card_type] -= 1
        return revealed_card_type

    def reveal_card_by_word(self, word: str) -> CardType:
        pos = self.get_word_position(word)
        if pos is None:
            raise InvalidMove('Word doesn\'t exist on the board.')
        else:
            i, j = pos
        return self.reveal_card_by_coordinates(i, j)

    def is_revealed(self, i: int, j: int):
        return self.grid[i][j] == REVEALED_CARD_TOKEN

    def team_won(self, team: Team) -> bool:
        team_card_type = team.card_type()
        return self._cards_remaining[team_card_type] == 0

    def count_revealed_cards(self, card_type: CardType) -> int:
        revealed_card_count = 0
        for i, j in self.get_grid_indices():
            if self.spy_key[i][j] is card_type \
                    and self.grid[i][j] != REVEALED_CARD_TOKEN:
                revealed_card_count += 1
        return revealed_card_count

    def cards_remaining(self, card_type: CardType) -> int:
        return self._cards_remaining[card_type]

    def assassin_revealed(self) -> bool:
        return self._cards_remaining[CardType.assassin] == 0

    def get_word_position(self, word: str) -> Union[Tuple[int, int], None]:
        if word == REVEALED_CARD_TOKEN:
            raise ValueError('Searching for the revealed token is not '
                             'supported.')
        word = word.upper()
        for i, j in self.get_grid_indices():
            if self.grid[i][j] == word:
                return i, j
        return None

    @staticmethod
    def get_grid_indices() -> Iterable[Tuple[int, int]]:
        return itertools.product(range(BOARD_SIZE), range(BOARD_SIZE))


class IrcCodenamesGame(object):
    """Game flow implementation. Keeps track of players and state. Can
    reveal cards and spit out the appropriate event in response.
    """
    word_deck_fn = 'word_deck.json'
    word_deck_dirpath = os.path.dirname(os.path.abspath(__file__))
    board_column_width = 15

    def __init__(self, red_team: List[str] = None, blue_team: List[str] = None,
                 blue_spymaster: str = None, red_spymaster: str = None):
        self.complete_original_spoiler_rows = None  # updated in codenames.bot.start_game()
        self.teams = dict()
        self.teams[Team.red] = set(red_team or [])
        self.teams[Team.blue] = set(blue_team or [])
        self.players = self.teams[Team.red].union(self.teams[Team.blue])
        self.spymasters = dict()
        self.spymasters[Team.red] = red_spymaster
        self.spymasters[Team.blue] = blue_spymaster
        word_deck_filepath = os.path.join(self.word_deck_dirpath,
                                          self.word_deck_fn)
        with open(word_deck_filepath) as fp:
            self.word_deck = json.load(fp)
        self.board = None
        self.starting_team = random.choice(list(Team))
        self.moving_team = self.starting_team
        self.winning_team = None
        self.phase = GamePhase.setup

    @staticmethod
    def generate_spy_key(starting_team: Team) -> List[List[CardType]]:
        """Generate a random spy key."""
        cards = [starting_team.card_type()] * (TEAM_CARD_COUNT + 1) \
            + [starting_team.other().card_type()] * TEAM_CARD_COUNT \
            + [CardType.bystander] * BYSTANDER_CARD_COUNT \
            + [CardType.assassin] * ASSASSIN_CARD_COUNT
        random.shuffle(cards)
        spy_key = [cards[i:i + BOARD_SIZE]
                   for i in range(0, BOARD_SIZE * BOARD_SIZE, BOARD_SIZE)]
        return spy_key

    def start(self):
        """Start the game. Throw an exception if something is wrong."""
        if not DEBUG:
            for team in Team:
                if len(self.teams[team]) < 2:
                    raise IrcGameError(
                        '{color} team must have at least 2 players.'.format(
                            color=team.color.capitalize()))
                if self.spymasters[team] is None:
                    raise IrcGameError('{color} team must have a spymaster.'
                                       .format(color=team.color.capitalize()))
        self.initialize_board()
        self.phase = GamePhase.in_progress

    def reset(self):
        self.starting_team = random.choice(list(Team))
        self.moving_team = self.starting_team
        self.board = None
        self.phase = GamePhase.setup

    def initialize_board(self):
        spy_key = self.generate_spy_key(self.starting_team)
        self.board = GameBoard(word_deck=self.word_deck,
                               spy_key=spy_key)

    def add_player(self, player: str, team: Team):
        """Add a player. Gracefully handle situation when player is already
        added, even if they're on the opposite team."""
        if player in self.teams[team]:
            return
        if player in self.teams[team.other()]:
            self.teams[team.other()].remove(player)
            if player == self.spymasters[team.other()]:
                self.spymasters[team.other()] = None
        self.teams[team].add(player)

    def remove_player(self, player: str) -> Union[Team, None]:
        if player in self.players:
            self.players.remove(player)
        for team in Team:
            if player in self.teams[team]:
                self.teams[team].remove(player)
                if player == self.spymasters[team]:
                    self.spymasters[team] = None
                return team
        return None

    def set_spymaster(self, team: Team, player: str):
        if player not in self.teams[team]:
            raise ValueError('Player must be in {color} team in order to '
                             'become its spymaster.'
                             .format(color=team.color))
        self.spymasters[team] = player

    def get_player_team(self, player: str) -> Union[Team, None]:
        for team in Team:
            if player in self.teams[team]:
                return team
        return None

    def get_team_members(self, team: Team) -> List[str]:
        return self.teams[team]

    def team_won(self, team: Team) -> bool:
        return self.board.team_won(team)

    def reveal_card_by_coordinates(self, i: int, j: int) -> GameEvent:
        """Reveal a card at given coordinates, update state accordingly,
        and return an event to signify the relevant state change."""
        self._check_in_progress()
        revealed_card_type = self.board.reveal_card_by_coordinates(i, j)
        if revealed_card_type is CardType.assassin:
            self.winning_team = self.moving_team.other()
            self.phase = GamePhase.finished
            return GameEvent.end_game
        elif revealed_card_type is CardType.bystander:
            return GameEvent.end_turn
        else:
            revealed_card_team = revealed_card_type.team()
            if self.board.team_won(revealed_card_team):
                self.winning_team = revealed_card_team
                self.phase = GamePhase.finished
                return GameEvent.end_game
            elif revealed_card_team is not self.moving_team:
                return GameEvent.end_turn
        return GameEvent.continue_turn

    def reveal_card(self, word: str) -> GameEvent:
        word_coordinates = self.board.get_word_coordinates(word)
        return self.reveal_card_by_coordinates(*word_coordinates)

    def next_turn(self):
        self.moving_team = self.moving_team.other()

    def _check_in_progress(self):
        """Check if the game is in progress for the purpose of actions only
        possible in that phase. Throw exception if not the case."""
        if self.phase is GamePhase.setup:
            raise InvalidMove('Game hasn\'t been started yet!')
        if self.phase is GamePhase.finished:
            raise InvalidMove(
                'Game has already concluded, and {team_color} team was '
                'victorious!'.format(team_color=self.winning_team.color))

    def render_board_rows(self, column_width: int = None,
                          spoil_colors: bool = False) -> List[str]:

        column_width = column_width or self.board_column_width

        def pad_word(word: str, width: int) -> str:
            padding_total = width - len(word)
            front_padding_length = int(math.floor(padding_total / 2))
            back_padding_length = int(math.ceil(padding_total / 2))
            front_padding = ''.join([' '] * front_padding_length)
            back_padding = ''.join([' '] * back_padding_length)
            padded_word = front_padding + word + back_padding
            return padded_word

        def card_type_color(card_type: CardType) -> irc_format.colors:
            type_color = {
                CardType.red: irc_format.colors.RED,
                CardType.blue: irc_format.colors.LIGHT_BLUE,
                CardType.bystander: irc_format.colors.LIGHT_GRAY,
                CardType.assassin: irc_format.colors.WHITE
            }
            return type_color[card_type]

        def decorate_word(word: str, card_type: CardType) -> str:
            text_color = card_type_color(card_type)
            if card_type == CardType.assassin:
                bg_color = irc_format.colors.BLACK
            else:
                bg_color = None
            decorated_word = irc_format.color(word, text_color, bg_color)
            if word == REVEALED_CARD_TOKEN:
                decorated_word = irc_format.bold(decorated_word)
            return decorated_word

        def render_row(row: List[str], width: int, card_types: List[CardType]):
            template = '{}' * BOARD_SIZE
            words = []
            for index, word in enumerate(row):
                card_type = card_types[index]
                padded_word = pad_word(word, width)
                if word == REVEALED_CARD_TOKEN or spoil_colors:
                    decorated_word = decorate_word(padded_word, card_type)
                else:
                    decorated_word = padded_word
                words.append(decorated_word)
            return template.format(*[pad_word(word, width) for word in words])

        rendered_rows = []
        for i in range(BOARD_SIZE):
            card_types = self.board.spy_key[i]
            rendered_row = render_row(self.board.grid[i],
                                      column_width, card_types)
            rendered_rows.append(rendered_row)
        return rendered_rows


class InvalidMove(Exception):
    pass


class IrcGameError(Exception):
    pass
