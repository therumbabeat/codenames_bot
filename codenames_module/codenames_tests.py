import pytest
import unittest
import random
import os
import json

from .codenames_game import (
    Team, CardType, GameBoard, IrcCodenamesGame, TEAM_CARD_COUNT,
    BYSTANDER_CARD_COUNT, ASSASSIN_CARD_COUNT)

random.seed(0)


@pytest.fixture
def starting_team():
    return Team.red

@pytest.fixture
def spy_key(starting_team):
    return IrcCodenamesGame.generate_spy_key(starting_team)


@pytest.fixture
def word_deck():
    word_deck_fn = IrcCodenamesGame.word_deck_fn
    word_deck_dirpath = IrcCodenamesGame.word_deck_dirpath
    word_deck_filepath = os.path.join(word_deck_dirpath, word_deck_fn)
    with open(word_deck_filepath) as fp:
        return json.load(fp)


@pytest.fixture
def game_board(word_deck, spy_key):
    return GameBoard(word_deck, spy_key)


@pytest.fixture
def card_type_example_coordinates(spy_key):
    coordinates = dict()
    unfound_card_types = list(CardType)
    indices = GameBoard.get_grid_indices()
    while unfound_card_types:
        i, j = next(indices)
        card_type = spy_key[i][j]
        if card_type in unfound_card_types:
            unfound_card_types.remove(card_type)
            coordinates[card_type] = (i, j)
    return coordinates


def card_type_all_coordinates(spy_key, card_type):
    coordinates = []
    indices = GameBoard.get_grid_indices()
    for i, j in indices:
        if spy_key[i][j] is card_type:
            coordinates.append((i, j))
    return coordinates


def test_board_setup(game_board, starting_team):
    assert game_board.cards_remaining(starting_team.card_type()) \
        == TEAM_CARD_COUNT + 1
    assert game_board.cards_remaining(starting_team.other().card_type()) \
        == TEAM_CARD_COUNT
    assert game_board.cards_remaining(CardType.bystander) == \
        BYSTANDER_CARD_COUNT
    assert game_board.cards_remaining(CardType.assassin) == ASSASSIN_CARD_COUNT


def test_reveal(game_board, starting_team, card_type_example_coordinates):
    cards_remaining_before = game_board.cards_remaining(
        starting_team.card_type())
    i, j = card_type_example_coordinates[starting_team.card_type()]
    card_type = game_board.reveal_card_by_coordinates(i, j)
    cards_remaining_after = game_board.cards_remaining(
        starting_team.card_type())
    assert cards_remaining_before == cards_remaining_after + 1
    assert card_type == starting_team.card_type()


def test_game_over(game_board, starting_team, spy_key):
    card_type_coordinates = card_type_all_coordinates(
        spy_key, starting_team.card_type())
    for i, j in card_type_coordinates:
        game_board.reveal_card_by_coordinates(i, j)
    assert(game_board.team_won(starting_team))


if __name__ == '__main__':
    unittest.main()
